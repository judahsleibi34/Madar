"""Real sealed descriptor/child environment boundary; backup effects are stopped."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from deployment.lib import active_recovery_backup as operation
from scripts import backup_support


class StopBeforeDump(Exception):pass


class FencedBackupEndpointTests(unittest.TestCase):
    def exercise(self,schema):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);backups=root/'backups';backups.mkdir()
        (backups/'LATEST').write_bytes(b'existing-original-marker\n')
        package=root/'package';package.mkdir()
        plan=SimpleNamespace(digest='a'*64,source_sha='b'*40)
        identity=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())
        descriptor=os.memfd_create('test-sealed-backup-endpoint',os.MFD_ALLOW_SEALING)
        os.write(descriptor,json.dumps({'address':'172.19.0.2'}).encode())
        fcntl.fcntl(descriptor,fcntl.F_ADD_SEALS,backup_support.DATABASE_SEALS)
        context=SimpleNamespace(validate=Mock(),guard=Mock(),schema=schema,contract={},provider_adapter=object(),
            stage='pre-migration' if schema==146 else 'post-migration')
        context.artifacts=Mock(return_value={'node1_replica':{'configuration_sha256':'c'*64}})
        observed=[]
        def capture(env,fd,user):
            observed.append(dict(env))
            self.assertEqual(env['PGHOST'],'supabase-db')
            self.assertEqual(env['PGHOSTADDR'],'172.19.0.2')
            self.assertEqual(env[backup_support.LOCAL_DATABASE_FD],str(descriptor))
            self.assertEqual(fd,descriptor);self.assertIs(user,identity)
            self.assertEqual(fcntl.fcntl(fd,fcntl.F_GET_SEALS),backup_support.DATABASE_SEALS)
            self.assertEqual(env['PGOPTIONS'],'-c default_transaction_read_only=on')
            raise StopBeforeDump()
        context.capture_fenced=Mock(side_effect=capture)
        def configuration(path,*,environ,**kwargs):
            if Path(path)==operation.INPUTS['backup_configuration']:
                environ.update(PGHOST='supabase-db',PGHOSTADDR='203.0.113.9',PGUSER='postgres')
                environ.update(MADAR_BACKUP_DIR=str(backups),MADAR_BACKUP_FRESHNESS_MARKER=str(backups/'LATEST'))
        def path(value):
            return backups if str(value)=='/var/lib/madar/backups' else Path(value)
        with patch.object(operation,'Path',side_effect=path),\
                patch.object(operation,'readonly_configuration',side_effect=lambda p,**kw:Path(p)),\
                patch.object(operation,'protected',side_effect=lambda p,**kw:Path(p)),\
                patch.object(operation,'file_digest',return_value='c'*64),\
                patch.object(operation,'load_environment_file',side_effect=configuration),\
                patch.object(operation,'historical_database_options',return_value={}),\
                patch.object(operation,'verify_backup_execution_context') as preflight,\
                patch.object(operation.pwd,'getpwnam',return_value=identity),\
                patch.object(backup_support,'sealed_local_database_binding',return_value=descriptor) as lease:
            with self.assertRaises(StopBeforeDump):
                operation.capture_and_replicate(plan,root,package,Mock(),SimpleNamespace(),completed_context=context)
        self.assertEqual(len(observed),1);lease.assert_called_once_with()
        context.validate.assert_called_once_with(plan,root,package)
        if schema==160:preflight.assert_called_once()
        else:preflight.assert_not_called()
        # The original lease remains single-use for this call, even when the
        # child fails. No descriptor leaks or retry/ordinary fallback occurs.
        with self.assertRaises(OSError):os.fstat(descriptor)

    def test_pre_migration_child_receives_sealed_address_not_caller_override(self):self.exercise(146)
    def test_post_migration_child_receives_same_bound_transport(self):self.exercise(160)


if __name__=='__main__':unittest.main()
