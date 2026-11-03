import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = next(p for p in (Path('/scripts'), Path(__file__).resolve().parents[2] / 'scripts') if (p / 'synthetic_postgres.py').is_file())
spec = importlib.util.spec_from_file_location('synthetic_postgres', SCRIPTS / 'synthetic_postgres.py')
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)
OWNER = '03a173db-e934-41f7-9b28-3c66e4538557'
NAME = 'madar-synthetic-' + OWNER
IMAGE = 'postgres@sha256:' + 'a' * 64
CID = 'b' * 64
RECORD = {'Id': CID, 'Name': '/' + NAME, 'Config': {'Image': IMAGE, 'Labels': {
    pg.OWNER_LABEL: OWNER, 'madar.rehearsal': 'unit'}}, 'State': {'Running': True},
    'NetworkSettings': {'Ports': {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '49182'}]}}}


class SyntheticPostgresTests(unittest.TestCase):
    def test_native_readiness_uses_final_tcp_server_and_bounded_sql_round_trip(self):
        spec=importlib.util.spec_from_file_location('native_port_test',SCRIPTS/'test_synthetic_postgres_native.py')
        native=importlib.util.module_from_spec(spec)
        import sys
        with patch.dict(sys.modules,{'synthetic_postgres':pg}):spec.loader.exec_module(native)
        calls=[];attempts=[0]
        def run(*args):
            calls.append(args)
            self.assertIn('-h',args);self.assertEqual(args[args.index('-h')+1],'127.0.0.1')
            if args[2]=='pg_isready':
                attempts[0]+=1
                if attempts[0]==1:raise subprocess.CalledProcessError(2,args)
                return 'accepting connections'
            if attempts[0]==2:raise subprocess.CalledProcessError(2,args)
            return '1\n'
        with patch.object(native,'docker',side_effect=run),patch.object(native.time,'sleep'):
            native.wait_for_postgres(CID)
        self.assertEqual(attempts[0],3)
        with patch.object(native,'docker',side_effect=subprocess.CalledProcessError(2,'docker')),patch.object(native.time,'monotonic',side_effect=[0,61]),self.assertRaises(subprocess.CalledProcessError):
            native.wait_for_postgres(CID)

    def test_loopback_port_is_actual_docker_allocation(self):
        self.assertEqual(pg.port(RECORD), '49182')
        for bindings in (None, [], [{'HostIp': '0.0.0.0', 'HostPort': '49182'}],
                         [{'HostIp': '127.0.0.1', 'HostPort': '65536'}],
                         RECORD['NetworkSettings']['Ports']['5432/tcp'] * 2):
            record = copy.deepcopy(RECORD)
            record['NetworkSettings']['Ports']['5432/tcp'] = bindings
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                pg.port(record)

    def test_foreign_identity_never_accepted(self):
        for section, key, value in [('Config', 'Image', 'foreign'), ('Config', 'Labels', {}),
                                    (None, 'Id', 'c' * 64), (None, 'Name', '/foreign')]:
            record = copy.deepcopy(RECORD)
            (record[section] if section else record)[key] = value
            with self.subTest(key=key), patch.object(pg, 'docker', side_effect=[CID, json.dumps([record])]), self.assertRaises(ValueError):
                pg.observe(NAME, OWNER, 'unit', IMAGE)

    def test_missing_is_idempotent_but_daemon_failure_surfaces(self):
        with patch.object(pg, 'docker', return_value=''):
            self.assertIsNone(pg.observe(NAME, OWNER, 'unit', IMAGE))
        with patch.object(pg, 'docker', side_effect=subprocess.CalledProcessError(1, 'docker')), self.assertRaises(subprocess.CalledProcessError):
            pg.observe(NAME, OWNER, 'unit', IMAGE)

    def shell(self, body, mode='normal', interrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = root / 'docker'
            fake.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys
p=pathlib.Path(os.environ['FAKE_STATE']); args=sys.argv[1:];mode=os.environ['FAKE_MODE'];cid='b'*64
if args[0]=='create':
 labels=dict(a.split('=',1) for i,a in enumerate(args) if i and args[i-1]=='--label')
 record={'Id':cid,'Name':'/'+args[args.index('--name')+1],'Config':{'Image':args[-1],'Labels':labels},'State':{'Running':True},'NetworkSettings':{'Ports':{'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'49182'}]}}}
 if mode=='foreign':record['Config']['Labels']={}
 p.write_text(json.dumps(record));print(cid)
 if mode=='lost-create':sys.exit(125)
elif args[0]=='start':
 if mode=='failed-start':sys.exit(125)
elif args[:2]==['container','ls']:print(cid if p.exists() else '')
elif args[:2]==['container','inspect']:print('['+p.read_text()+']')
elif args[:2]==['container','rm']:
 assert args[-1]==cid
 p.unlink()
else:raise SystemExit('unexpected '+str(args))
''')
            fake.chmod(0o700)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], FAKE_STATE=str(root / 'state'), FAKE_MODE=mode)
            code = 'set -euo pipefail\nSCRIPT_DIR="$1"\nPOSTGRES_IMAGE="$2"\nsource "$SCRIPT_DIR/synthetic_postgres.sh"\nsynthetic_postgres_start unit\n' + body
            process = subprocess.Popen(['bash', '-c', code, 'test', str(SCRIPTS), IMAGE], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if interrupt:
                self.assertEqual(process.stdout.readline().strip(), 'ready')
                process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=15)
            return process.returncode, (root / 'state').exists(), stdout, stderr

    def test_success_and_original_failure_cleanup(self):
        for body, expected in [('test "$SYNTHETIC_POSTGRES_PORT" = 49182', 0), ('exit 42', 42)]:
            status, remains, _, stderr = self.shell(body)
            self.assertEqual(status, expected, stderr)
            self.assertFalse(remains)

    def test_failed_start_and_lost_create_ack_are_cleaned(self):
        for mode in ('failed-start', 'lost-create'):
            status, remains, _, _ = self.shell('exit 0', mode)
            self.assertEqual(status, 125)
            self.assertFalse(remains)

    def test_foreign_container_is_not_removed(self):
        status, remains, _, stderr = self.shell('exit 0', 'foreign')
        self.assertNotEqual(status, 0)
        self.assertTrue(remains)
        self.assertIn('ownership_refused', stderr)

    def test_term_preserves_signal_status_and_cleans(self):
        status, remains, _, stderr = self.shell('echo ready; read -r line', interrupt=True)
        self.assertEqual(status, 143, stderr)
        self.assertFalse(remains)


if __name__ == '__main__':
    unittest.main()
