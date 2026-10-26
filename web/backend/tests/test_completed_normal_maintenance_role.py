"""Role binding is preparation, never schema160 execution authority."""
import copy
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from deployment.lib.completed_normal_profile import maintenance_role, profile
from deployment.lib.completed_normal_admission import validate_provider_preparation
from deployment.lib import active_recovery_backup as recovery
from deployment.lib import completed_normal_migration as migration
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_profile import RECONCILED
from scripts import backup_support as backup
from test_schema160_release import reconciled_contract
from test_schema150_admission import deletion_contract


class MaintenanceRoleTests(unittest.TestCase):
    def test_only_exact_canonical_contract_can_select_native_administrator(self):
        original=reconciled_contract()
        self.assertEqual(maintenance_role(original),'postgres')
        contract=copy.deepcopy(original)
        contract['database']['maintenance_role']='supabase_admin'
        self.assertEqual(validate_provider_preparation(contract).target,160)
        self.assertEqual(maintenance_role(contract),'supabase_admin')
        # Preparation must not open the operational registry.
        with self.assertRaises(RuntimeError):profile(contract)
        for role in ('postgres','root','service_role',True,None,{},['supabase_admin']):
            bad=copy.deepcopy(contract);bad['database']['maintenance_role']=role
            with self.subTest(role=role),self.assertRaises(RuntimeError):validate_provider_preparation(bad)
        historical=deletion_contract();historical['database']['maintenance_role']='supabase_admin'
        with self.assertRaises(RuntimeError):validate_provider_preparation(historical)
        contract['version']=True
        with self.assertRaises(RuntimeError):maintenance_role(contract)

    def test_environment_alone_cannot_select_administrator(self):
        env={'PGHOST':'supabase-db','PGPORT':'5432','PGUSER':'supabase_admin',
             'PGDATABASE':'postgres','PGSSLMODE':'disable'}
        with patch.dict(os.environ,env,clear=True):self.assertFalse(backup.direct_local_database_shape())
        with patch.dict(os.environ,{**env,backup.LOCAL_DATABASE_FD:'invalid'},clear=True):
            with self.assertRaises(backup.BackupError):backup.direct_local_database_shape()

    def test_canonical_inventory_fences_postgres_when_administrator_is_maintenance(self):
        from test_schema150_actor_inventory import fixture,repin
        from deployment.lib.schema150_actor_inventory import validate_inventory
        (data,binding),_rows=fixture()
        binding.update(operation=RECONCILED.operation,target_schema=160)
        data['roles']['supabase_admin']=copy.deepcopy(data['roles']['postgres'])
        data['session_scope']['maintenance_role']='supabase_admin'
        data['session_scope']['writer_roles']=sorted(name for name,value in data['roles'].items()
            if value['login'] and name!='supabase_admin')
        data,binding=repin(data,binding)
        validate_inventory(data,binding)
        data['session_scope']['writer_roles'].remove('postgres')
        data,binding=repin(data,binding)
        with self.assertRaises(RuntimeError):validate_inventory(data,binding)

    def test_unrelated_or_conflicting_preflight_contract_refuses_before_transport(self):
        with patch.object(recovery,'checked') as transport:
            with self.assertRaises(RuntimeError):
                recovery.verify_backup_execution_context(Path('/unused'),maintenance_contract=deletion_contract(),expected_schema=146)
            with self.assertRaisesRegex(RuntimeError,'context_conflict'):
                recovery.verify_backup_execution_context(Path('/unused'),completed_context=object(),maintenance_contract=reconciled_contract())
            transport.assert_not_called()

    def test_existing_executor_connection_uses_and_verifies_same_approved_role(self):
        contract=reconciled_contract();contract['database']['maintenance_role']='supabase_admin'
        lease={'context_sha256':digest(contract),'database':contract['database'],
               'address':'172.19.0.2','expires':time.monotonic()+60,'password':'synthetic-test-only'}
        for observed in (('supabase_admin','supabase_admin',True),('postgres','supabase_admin',True),
                         ('supabase_admin','supabase_admin',False)):
            connection=MagicMock();cursor=connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect=[(contract['database']['system_identifier'],146),observed]
            driver=SimpleNamespace(connect=Mock(return_value=connection))
            with patch.dict(sys.modules,{'psycopg':driver}),\
                    patch.object(migration,'require_fresh_authorization'),\
                    patch.object(migration,'require_candidate_authority'),\
                    patch.object(migration,'credential_witness',return_value=lease),\
                    patch.object(migration,'profile',return_value=RECONCILED):
                if observed==('supabase_admin','supabase_admin',True):
                    self.assertIs(migration.connection_factory(contract),connection)
                    connection.rollback.assert_called_once();connection.close.assert_not_called()
                else:
                    with self.assertRaisesRegex(RuntimeError,'maintenance_identity_changed'):
                        migration.connection_factory(contract)
                    connection.close.assert_called_once()
                self.assertEqual(driver.connect.call_args.kwargs['user'],'supabase_admin')
                self.assertIn('session_user',cursor.execute.call_args.args[0])

    @unittest.skipUnless(os.geteuid()==0,'actual root-owned sealed role descriptor')
    def test_root_descriptor_binds_role_address_and_cannot_be_modified(self):
        import fcntl
        for role,version in (('postgres',1),('supabase_admin',2)):
            with patch.object(backup,'direct_local_database_address',return_value='172.19.0.2'):
                fd=backup.sealed_local_database_binding(maintenance_role=role)
            try:
                with patch.dict(os.environ,{backup.LOCAL_DATABASE_FD:str(fd)},clear=True):
                    self.assertEqual(backup.leased_local_database_address(),'172.19.0.2')
                    self.assertEqual(backup.leased_local_database_role(),role)
                    value=json.loads(os.pread(fd,4096,0));self.assertEqual(value['version'],version)
                    with self.assertRaises(OSError):os.pwrite(fd,b'{}',0)
                    self.assertEqual(fcntl.fcntl(fd,fcntl.F_GET_SEALS),backup.DATABASE_SEALS)
            finally:os.close(fd)


if __name__=='__main__':unittest.main()
