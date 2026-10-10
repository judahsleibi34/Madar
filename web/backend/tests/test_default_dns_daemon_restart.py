"""Real daemon reload using a PRIVATE daemon; never restart the host daemon.

Opt-in root fixture has its own socket, data/exec roots and containerd namespace,
no bridge/firewall changes, no published ports and no production mounts or DB.
Only test-owned resources are retired. No production acceptance is implied.
"""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import default_dns_spec_matches,worker_spec_matches
from deployment.lib.emergency_routing_repair import spec


@unittest.skipUnless(os.getenv('MADAR_PRIVATE_DOCKER_RESTART_TEST')=='1',
                     'requires explicit private-daemon root fixture')
class DefaultDNSDaemonRestartTests(unittest.TestCase):
    def docker(self,*args):
        # Every mutable Docker call names this private socket explicitly.
        return subprocess.check_output(['docker','--host',self.host,*args],text=True,timeout=40).strip()

    def host_bridges(self):
        links=json.loads(subprocess.check_output(['ip','-d','-j','link'],text=True,timeout=10))
        return {x['ifname']:x['ifindex'] for x in links if x.get('linkinfo',{}).get('info_kind')=='bridge'}

    def tearDown(self):
        self.stop()
        self.assertEqual(self.host_bridges(),self.original_host_bridges)

    def launch(self):
        # Daemon bridge housekeeping must not share the production host's netns,
        # even with --bridge=none and firewall programming disabled.
        self.process=subprocess.Popen(['unshare','--net','--','dockerd','--config-file',str(self.root/'daemon.json'),
            '--data-root',str(self.root/'data'),'--exec-root',str(self.root/'exec'),
            '--pidfile',str(self.root/'daemon.pid'),'--host',self.host,
            '--containerd-namespace',self.root.name,'--containerd-plugins-namespace',self.root.name+'-plugins',
            '--bridge','none','--iptables=false','--ip6tables=false','--ip-forward=false',
            '--ip-masq=false','--storage-driver','vfs'],
            stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if self.process.poll() is not None:raise RuntimeError('private_daemon_start_failed')
            try:
                if self.docker('info','--format','{{.DockerRootDir}}')!=str(self.root/'data'):
                    raise RuntimeError('private_daemon_root_changed')
                return
            except subprocess.CalledProcessError:time.sleep(.2)
        raise RuntimeError('private_daemon_start_timeout')

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid,signal.SIGKILL);self.process.wait(timeout=10)

    def setUp(self):
        if os.geteuid()!=0:raise RuntimeError('private_daemon_fixture_requires_root')
        self.original_host_bridges=self.host_bridges()
        parent=WEB.parent/'.incident-response';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='dns-',dir=parent)
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.host='unix://'+str(self.root/'api.sock');self.process=None
        (self.root/'daemon.json').write_text(json.dumps({'features':{'containerd-snapshotter':False}}))
        self.log=open(self.root/'daemon.log','a');self.addCleanup(self.log.close);self.addCleanup(self.stop)
        self.launch()
        # Read-only image export from host; loading occurs only on private socket.
        image=os.environ['MADAR_PRIVATE_DOCKER_TEST_IMAGE']
        payload=subprocess.check_output(['docker','image','save',image],timeout=40)
        subprocess.run(['docker','--host',self.host,'image','load'],input=payload,
                       check=True,stdout=subprocess.DEVNULL,timeout=40)
        self.cid=self.docker('create','--name',self.root.name,'--network','none',
            '--restart','no','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--read-only','--entrypoint','/bin/sh',image,'-c','sleep 300')

    def test_real_created_running_stopped_daemon_reload_preserves_only_default_dns(self):
        original=json.loads(self.docker('inspect',self.cid))[0];expected=spec(original)
        self.assertIsNone(original['HostConfig']['Dns'])
        self.docker('start',self.cid)
        running=json.loads(self.docker('inspect',self.cid))[0]
        self.assertTrue(worker_spec_matches(running,expected,started_worker=True))
        self.docker('stop','--time','1',self.cid)
        stopped=json.loads(self.docker('inspect',self.cid))[0]
        self.assertTrue(worker_spec_matches(stopped,expected,started_worker=True))
        before=spec(stopped)
        self.stop();self.launch()
        reloaded=json.loads(self.docker('inspect',self.cid))[0]
        self.assertFalse(reloaded['State']['Running'])
        self.assertEqual(reloaded['HostConfig']['Dns'],[])
        self.assertNotEqual(spec(reloaded),before)
        self.assertTrue(default_dns_spec_matches(reloaded,before))
        self.assertTrue(worker_spec_matches(reloaded,expected,started_worker=True))
        self.assertFalse(worker_spec_matches(reloaded,expected))
        for field,value in (('Dns',['127.0.0.1']),('Privileged',True)):
            bad=copy.deepcopy(reloaded);bad['HostConfig'][field]=value
            self.assertFalse(worker_spec_matches(bad,expected,started_worker=True))
        self.docker('rm',self.cid)
