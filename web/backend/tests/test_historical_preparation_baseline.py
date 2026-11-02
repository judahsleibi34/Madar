"""Root preparation contracts and SQL sharing; not native migration acceptance."""
import os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import completed_normal_database as database
from deployment.lib.completed_normal_profile import profile
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
                ('deployment.lib.provider_recovery_runtime.protected',lambda p,**kw:Path(p)),
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
