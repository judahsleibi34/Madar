"""Execute the real shell cleanup/traps with a modeled daemon, never host Docker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])

FAKE_DOCKER = '''import json,os,sys
from pathlib import Path
p=Path(os.environ['FAKE_DOCKER_STATE']);data=json.loads(p.read_text());args=sys.argv[1:]
if os.environ.get('FAKE_DAEMON_DOWN')=='1':sys.exit(125)
if args[0]=='inspect':
    name=args[-1]
    if name not in data['resources']:sys.exit(1)
    if '--format' in args:print(data['resources'][name])
elif args[:2]==['rm','-f']:
    name=args[-1];data['removed'].append(name);data['resources'].pop(name,None);p.write_text(json.dumps(data))
elif args[0]=='ps':
    print('\\n'.join(name+' '+name for name in data['resources'])) if '--format' in args else print('\\n'.join(name for name,owner in data['resources'].items() if owner=='owned-run'))
else:sys.exit(2)
'''


class NativeHarnessCleanupTests(unittest.TestCase):
    def run_harness(self, *, foreign=False, unavailable=False, body='exit 0'):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.outer=Path(temporary.name);run=self.outer/'owned-run';run.mkdir(mode=0o700)
        (run/'source').mkdir();(run/'source/public.py').write_text('public test source')
        (run/'schema136.dump').write_bytes(b'synthetic disposable fixture')
        state=self.outer/'daemon.json';state.write_text(json.dumps({'resources':{
            'owned-child':'foreign' if foreign else 'owned-run','owned-db':'owned-run'},'removed':[]}))
        executable=self.outer/'docker';executable.write_text('#!'+sys.executable+'\n'+FAKE_DOCKER);executable.chmod(0o755)
        source=(WEB/'scripts/rehearse_data_sources_upgrade_136_156.sh').read_text()
        cleanup=source[source.index('cleanup() {'):source.index('# Export indexed public source')]
        program='set -euo pipefail\n'+cleanup+'\n'+body+'\n'
        environment=dict(os.environ,PATH=str(self.outer)+':'+str(Path(sys.executable).parent)+':'+os.defpath,RUN_ROOT=str(run),RUN_ID='owned-run',
            SOURCE_VIEW=str(run/'source'),BACKUP_FILE=str(run/'schema136.dump'),TEST_CONTAINER='owned-child',
            CONTAINER_ID='owned-db',RUN_DEVICE=str(run.stat().st_dev),RUN_INODE=str(run.stat().st_ino),FAKE_DOCKER_STATE=str(state),FAKE_DAEMON_DOWN='1' if unavailable else '0')
        result=subprocess.run(['/bin/bash','-c',program],env=environment,capture_output=True,text=True,timeout=10)
        return result,json.loads(state.read_bytes()),run

    def test_child_is_removed_before_database_and_owned_source_view_is_removed(self):
        result,state,run=self.run_harness()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(state['removed'],['owned-child','owned-db']);self.assertFalse(run.exists())

    def test_term_trap_removes_both_resources_without_claiming_success(self):
        result,state,run=self.run_harness(body='kill -TERM $$')
        self.assertEqual(result.returncode,143,result.stderr)
        self.assertEqual(state['removed'],['owned-child','owned-db']);self.assertFalse(run.exists())

    def test_foreign_resource_is_not_removed_and_retention_is_explicit(self):
        result,state,run=self.run_harness(foreign=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(state['removed'],['owned-db']);self.assertEqual(state['resources'],{'owned-child':'foreign'})
        self.assertTrue((run/'cleanup-retained.json').is_file())

    def test_daemon_failure_does_not_misrepresent_unknown_resources_as_absent(self):
        result,state,run=self.run_harness(unavailable=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(state['removed'],[]);self.assertEqual(len(state['resources']),2)
        self.assertTrue((run/'cleanup-retained.json').is_file())

    def test_repeated_teardown_is_safe(self):
        result,state,run=self.run_harness(body='cleanup\nexit 0')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(state['removed'],['owned-child','owned-db']);self.assertFalse(run.exists())

    def test_replaced_run_directory_cannot_redirect_deletion_into_protected_files(self):
        body='mv "$RUN_ROOT" "$RUN_ROOT-held"; ln -s "$RUN_ROOT-held" "$RUN_ROOT"; exit 0'
        result,state,run=self.run_harness(body=body)
        held=Path(str(run)+'-held')
        self.assertNotEqual(result.returncode,0)
        self.assertTrue((held/'schema136.dump').is_file())
        self.assertTrue((held/'source/public.py').is_file())
