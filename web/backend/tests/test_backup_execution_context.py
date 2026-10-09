"""Least-privilege backup child regressions; root Docker fixtures run separately."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import active_recovery_backup as operation
spec=importlib.util.spec_from_file_location('backup_context_support',WEB/'scripts/backup_support.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)

class BackupExecutionContextTests(unittest.TestCase):
    def test_missing_groups_discovery_is_not_postgresql_failure(self):
        with patch.dict(os.environ,{},clear=True), patch.object(support.subprocess,'run',
                side_effect=subprocess.CalledProcessError(1,['docker'],stderr='permission denied')):
            with self.assertRaisesRegex(support.BackupError,'local_backup_direct_database_unavailable'):
                support.direct_local_database_address()

    def test_binding_creation_requires_root(self):
        with patch.object(support.os,'geteuid',return_value=1000), patch.object(support,'direct_local_database_address') as resolve:
            with self.assertRaisesRegex(support.BackupError,'binding_root_required'):
                support.sealed_local_database_binding()
            resolve.assert_not_called()

    def test_invalid_descriptor_never_falls_back_to_docker(self):
        for value in ('7','not-a-descriptor','999999'):
            with self.subTest(value=value), patch.dict(os.environ,{support.LOCAL_DATABASE_FD:value}), patch.object(support.subprocess,'run') as docker:
                with self.assertRaisesRegex(support.BackupError,'binding_invalid'):
                    support.direct_local_database_address()
                docker.assert_not_called()

    def test_child_preserves_empty_groups_and_no_new_privileges(self):
        with patch.object(operation.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'ok','')) as run:
            self.assertEqual(operation.checked(['/usr/bin/true'],user=1000,pass_fds=(64,)),'ok')
            self.assertEqual(run.call_args.args[0],['/usr/bin/setpriv','--no-new-privs','/usr/bin/true'])
            self.assertEqual(run.call_args.kwargs['extra_groups'],[])
            self.assertEqual(run.call_args.kwargs['group'],1000)
            self.assertEqual(run.call_args.kwargs['pass_fds'],(64,))

    def test_failure_retains_only_fixed_code_not_private_output(self):
        for output,expected in (('ERROR: local_backup_direct_database_unavailable','local_backup_direct_database_unavailable'),
                                ('ERROR: private-customer-content','child_exit_nonzero'),
                                ('permission denied password=private','child_exit_nonzero')):
            with patch.object(operation.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'private',output)):
                with self.assertRaisesRegex(RuntimeError,'normal_backup_command_failed:'+expected) as failure:
                    operation.checked(['/usr/bin/false'],user=1000)
                self.assertNotIn('private',str(failure.exception))

    @unittest.skipUnless(os.geteuid()==0, 'actual root-issued descriptor fixture')
    def test_actual_root_sealed_binding_survives_restricted_child_and_bash(self):
        import json
        with patch.object(support,'direct_local_database_address',return_value='172.19.0.2'):
            descriptor=support.sealed_local_database_binding()
        try:
            code="import json,os; print(json.dumps({'uid':os.getuid(),'groups':os.getgroups(),'payload':json.loads(os.pread(int(os.environ['MADAR_LOCAL_DATABASE_BINDING_FD']),4096,0)),'no_new_privileges':'NoNewPrivs:\\t1' in open('/proc/self/status').read()}))"
            output=operation.checked(['/bin/bash','-c','exec /usr/bin/python3 -I -B -c "$1"','fixture',code],
                env={**operation.ENVIRONMENT,support.LOCAL_DATABASE_FD:str(descriptor)},user=1000,pass_fds=(descriptor,))
            result=json.loads(output)
            self.assertEqual(result['uid'],1000);self.assertEqual(result['groups'],[])
            self.assertEqual(result['payload']['address'],'172.19.0.2');self.assertTrue(result['no_new_privileges'])
            with patch.dict(os.environ,{support.LOCAL_DATABASE_FD:str(descriptor)}):
                self.assertEqual(support.leased_local_database_address(),'172.19.0.2')
        finally:os.close(descriptor)

    def test_two_backup_retention_keeps_the_isolated_current_artifact(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);current=root/'madar-20261009T202313Z';current.mkdir()
            packet={'retention_managed':True,'backup_id':current.name}
            with patch.object(support,'verify',return_value=packet), patch.object(support.shutil,'rmtree') as remove:
                with self.assertRaisesRegex(support.BackupError,'retention_minimum_two'):
                    support.retention(root,current,1)
                self.assertEqual(support.retention(root,current,2),[])
                remove.assert_not_called()

    def test_nonsecret_path_contract_does_not_relax_credentials(self):
        import tempfile
        from deployment.lib.environment_file import load_environment_file
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'production-paths.conf'
            path.write_text('MADAR_STORAGE_ROOT=/var/lib/madar/storage\n');path.chmod(0o644)
            data={};load_environment_file(path,environ=data,require_private=False)
            self.assertEqual(data['MADAR_STORAGE_ROOT'],'/var/lib/madar/storage')
            with self.assertRaisesRegex(RuntimeError,'permissions_too_broad'):
                load_environment_file(path,environ={})

    def test_sealed_binding_expiration_and_unsealed_file_rejected(self):
        import fcntl,json,time
        fd=os.memfd_create('untrusted-backup-fixture',os.MFD_ALLOW_SEALING)
        try:
            descriptor=fcntl.fcntl(fd,fcntl.F_DUPFD_CLOEXEC,64)
            try:
                os.fchmod(descriptor,0o400)
                os.write(descriptor,json.dumps({'version':1,'address':'172.19.0.2','expires':time.monotonic()-1}).encode())
                with patch.dict(os.environ,{support.LOCAL_DATABASE_FD:str(descriptor)}):
                    with self.assertRaisesRegex(support.BackupError,'binding_invalid'):
                        support.direct_local_database_address()
            finally:os.close(descriptor)
        finally:os.close(fd)

if __name__=='__main__':unittest.main()
