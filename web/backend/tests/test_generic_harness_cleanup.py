"""Real generic shell traps against a modeled daemon; never host Docker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
FAKE='''import json,os,sys
from pathlib import Path
path=Path(os.environ['FAKE_DOCKER_STATE']);value=json.loads(path.read_text());args=sys.argv[1:]
if os.environ.get('FAKE_DAEMON_DOWN')=='1':sys.exit(125)
if args[0]=='ps':
 print('\\n'.join(k for k,v in value['resources'].items() if '--filter' not in args or v=='owned-run'))
elif args[0]=='inspect':
 if args[-1] not in value['resources']:sys.exit(1)
 print(value['resources'][args[-1]])
elif args[:2]==['rm','-f']:
 key=args[-1];value['removed'].append(key);value['resources'].pop(key,None);path.write_text(json.dumps(value))
else:sys.exit(2)
'''


class GenericHarnessCleanupTests(unittest.TestCase):
    def run_harness(self,*,foreign=False,unavailable=False,body='exit 0'):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);outer=Path(temp.name);run=outer/'run';run.mkdir(mode=0o700)
        (run/'database.dump').write_bytes(b'synthetic fixture');(run/'manifest.json').write_text('{}')
        (run/'acceptance.cid').write_text('a'*64);(run/'candidate.cid').write_text('b'*64)
        state=outer/'state.json';state.write_text(json.dumps({'resources':{
            'a'*64:'foreign' if foreign else 'owned-run','b'*64:'owned-run','c'*64:'owned-run'},'removed':[]}))
        executable=outer/'docker';executable.write_text('#!'+sys.executable+'\n'+FAKE);executable.chmod(0o755)
        source=(WEB/'scripts/rehearse_generic_migrations.sh').read_text()
        program='set -euo pipefail\n'+source[source.index('cleanup() {'):source.index('container_id="$(docker create')]+body+'\n'
        environment=dict(os.environ,PATH=str(outer)+':'+str(Path(sys.executable).parent)+':'+os.defpath,
            backup_dir=str(run),run_device=str(run.stat().st_dev),run_inode=str(run.stat().st_ino),RUN_ID='owned-run',
            owned='true',container_id='c'*64,FAKE_DOCKER_STATE=str(state),FAKE_DAEMON_DOWN='1' if unavailable else '0')
        result=subprocess.run(['/bin/bash','-c',program],env=environment,capture_output=True,text=True,timeout=10)
        return result,json.loads(state.read_bytes()),run

    def test_child_resources_remove_before_database_and_no_directory_remains(self):
        result,state,run=self.run_harness()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(state['removed'],['b'*64,'a'*64,'c'*64]);self.assertFalse(run.exists())

    def test_term_failure_still_removes_owned_resources(self):
        result,state,run=self.run_harness(body='kill -TERM $$')
        self.assertEqual(result.returncode,143,result.stderr);self.assertFalse(state['resources']);self.assertFalse(run.exists())

    def test_unknown_daemon_state_is_retained_not_misreported_absent(self):
        result,state,run=self.run_harness(unavailable=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(state['removed']);self.assertEqual(len(state['resources']),3)
        self.assertTrue((run/'cleanup-retained.json').is_file());self.assertTrue((run/'database.dump').is_file())

    def test_foreign_actor_is_not_deleted_and_review_record_remains(self):
        result,state,run=self.run_harness(foreign=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(state['resources'],{'a'*64:'foreign'})
        self.assertTrue((run/'cleanup-retained.json').is_file())

    def test_repeated_teardown_is_safe(self):
        result,state,run=self.run_harness(body='cleanup\nexit 0')
        self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(run.exists());self.assertEqual(len(state['removed']),3)

    def test_replaced_directory_never_redirects_filesystem_deletion(self):
        result,state,run=self.run_harness(body='mv "$backup_dir" "$backup_dir-held"; ln -s "$backup_dir-held" "$backup_dir"; exit 0')
        self.assertNotEqual(result.returncode,0);self.assertTrue(Path(str(run)+'-held','database.dump').is_file())


if __name__=='__main__':unittest.main()
