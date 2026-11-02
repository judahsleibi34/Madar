"""Root preparation contracts and SQL sharing; not native migration acceptance."""
import os,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import completed_normal_database as database
from deployment.lib.completed_normal_profile import profile,RECONCILED,LEGACY
import test_historical_origin as historical_fixture


class HistoricalPreparationBaselineTests(unittest.TestCase):
    def setUp(self):
        self.contract=historical_fixture.HistoricalPreparationBindingTests().contract()
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);(root/'state.json').write_text('{}')
        self.system=SimpleNamespace(state_root=root)
        self.runtime=Mock();self.runtime.command.return_value='a'*64+'\n'
        for name,value in [('os.geteuid',lambda:0),
                ('deployment.lib.control_plane_upgrade.SystemOperations',lambda:self.system),
                ('deployment.lib.provider_recovery_runtime.readonly_configuration',lambda p,**kw:Path(p)),
                ('deployment.lib.historical_origin.attest',Mock(return_value=self.contract['source_roles']))]:
            self.enterContext(patch(name,value))

    def test_read_only_preparation_does_not_register_execution_or_approve_plan(self):
        snapshot={'schema':146,'columns':{},'roots':{'auth.users':{'count':2},'public.application_schema_state':{'count':1}}}
        with patch.object(database,'_observe_native',return_value=146),patch.object(database,'_customer_snapshot',return_value=snapshot):
            value=database.historical_preparation_baseline(self.contract,self.runtime)
        self.assertEqual(value['database_structure_sha256'],'a'*64)
        self.assertEqual(value['table_roots_sha256'],database.digest(snapshot))
        args=self.runtime.command.call_args.args[0]
        self.assertEqual(args[-1],database.STRUCTURE_SQL)
        self.assertIn('READ ONLY',args[-1])
        with self.assertRaises(RuntimeError):profile(self.contract)
        # Ordinary observers cannot silently inherit the preparation capability.
        self.runtime.reset_mock()
        for observer in (database.observe_native,database.customer_baseline,database.migration_customer_snapshot):
            with self.assertRaises(RuntimeError):observer(self.contract,self.runtime)
        self.runtime.assert_not_called();self.runtime.inspect.assert_not_called();self.runtime.command.assert_not_called()

    def test_nonroot_changed_source_or_native_schema_refuses_before_measurement(self):
        with patch.object(os,'geteuid',return_value=1000),self.assertRaisesRegex(RuntimeError,'preparation_required'):
            database.historical_preparation_baseline(self.contract,self.runtime)
        with patch('deployment.lib.historical_origin.attest',return_value={}),self.assertRaisesRegex(RuntimeError,'origin_changed'):
            database.historical_preparation_baseline(self.contract,self.runtime)
        with patch.object(database,'_observe_native',return_value=160),self.assertRaisesRegex(RuntimeError,'source_schema_changed'):
            database.historical_preparation_baseline(self.contract,self.runtime)
        self.runtime.command.assert_not_called()


class HistoricalProbeSnapshotTests(unittest.TestCase):
    def test_normalization_is_preparation_only_and_keeps_security_columns(self):
        contract=historical_fixture.HistoricalPreparationBindingTests().contract()
        columns={**{'public.table_'+str(i):['id','value','updated_at'] for i in range(96)},
            'auth.users':['id','encrypted_password','last_sign_in_at','updated_at'],
            'auth.identities':['id','provider_id','updated_at'],
            'auth.mfa_factors':['id','secret','last_challenged_at','updated_at'],
            'storage.objects':['id','owner','last_accessed_at','updated_at'],
            'storage.buckets':['id','owner','updated_at']}
        rows=[{'table':n,'count':2,'sha256':'a'*64} for n in sorted(columns)]+[{'schema':146}]
        runtime=Mock();runtime.command.return_value='\n'.join(json.dumps(r) for r in rows)
        normal=database._customer_snapshot(contract,runtime,RECONCILED,columns=columns,native=lambda:146)
        sql=runtime.command.call_args.args[0][-1]
        self.assertIn('t."last_sign_in_at"',sql)
        self.assertNotIn('ignored_preparation_probe_timestamps',normal)
        prepared=database._customer_snapshot(contract,runtime,RECONCILED,columns=columns,native=lambda:146,preparation_probes=True)
        sql=runtime.command.call_args.args[0][-1]
        self.assertNotIn('t."last_sign_in_at"',sql)
        self.assertNotIn('t."last_challenged_at"',sql)
        self.assertNotIn('t."last_accessed_at"',sql)
        for name in ('encrypted_password','secret','owner','provider_id','updated_at'):
            self.assertIn('t."'+name+'"',sql)
        self.assertEqual(prepared['columns'],normal['columns'])
        with self.assertRaisesRegex(RuntimeError,'preparation_snapshot_forbidden'):
            database.verify_migration_customer_preservation(prepared,prepared,contract=contract)
        self.assertEqual(set(prepared['ignored_preparation_probe_timestamps']),{'auth.users','auth.mfa_factors','storage.objects'})
        for changed,selected,schema in (({},RECONCILED,146),(contract,LEGACY,146),(contract,RECONCILED,160)):
            with self.subTest(schema=schema),self.assertRaisesRegex(RuntimeError,'probe_scope_invalid'):
                database._customer_snapshot(changed,runtime,selected,columns=columns,native=lambda:schema,preparation_probes=True)

    def test_preparation_revalidation_still_checks_customer_identity_and_structure(self):
        contract=historical_fixture.HistoricalPreparationBindingTests().contract()
        snapshot={'schema':146,'columns':{},'roots':{'auth.users':{'count':2},'public.customers':{'count':3}},
            'ignored_preparation_probe_timestamps':{}}
        identities=[snapshot['roots']['auth.users']]
        contract.update(customer_table_roots_sha256=database.digest(snapshot),
            customer_identity_roots_sha256=database.digest({'roots':identities}),database_structure_sha256='b'*64)
        with patch.object(database,'profile',return_value=RECONCILED),patch.object(database,'_customer_snapshot',return_value=snapshot),patch.object(database,'database_structure_digest',return_value='b'*64):
            database.verify_preparation_baseline(contract,object(),{})
            for key in ('customer_table_roots_sha256','customer_identity_roots_sha256','database_structure_sha256'):
                changed=dict(contract,**{key:'f'*64})
                with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'current_customer_data_changed'):
                    database.verify_preparation_baseline(changed,object(),{})
