"""Bounded isolated storage startup without production access."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import urllib.error
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
SCRIPTS=Path('/scripts') if Path('/scripts').is_dir() else WEB/'scripts'
spec=importlib.util.spec_from_file_location('native_restore_fixture',SCRIPTS/'verify_restored_native_platform.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class NativeRestoreReadinessTests(unittest.TestCase):
    def invoke(self,responses,*,running=True):
        now=[0.0];responses=iter(responses)
        def request(*args,**kwargs):
            response=next(responses,503)
            if isinstance(response,Exception):raise response
            return response,{},b''
        runner.wait_for_storage('http://isolated',{},lambda:{'State':{'Running':running}},
            deadline_seconds=3,clock=lambda:now[0],pause=lambda value:now.__setitem__(0,now[0]+value),request=request)
        return now[0]
    def test_delayed_connection_then_ready(self):
        self.assertEqual(self.invoke([urllib.error.URLError('fixture'),503,200]),2)
    def test_persistent_failure_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError,'readiness_deadline'):self.invoke([503])
    def test_wrong_credentials_are_not_retried(self):
        with self.assertRaisesRegex(RuntimeError,'health_rejected'):self.invoke([401,200])
    def test_exited_container_is_not_a_readiness_delay(self):
        with self.assertRaisesRegex(RuntimeError,'storage_exited'):self.invoke([200],running=False)
