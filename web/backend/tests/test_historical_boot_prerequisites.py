"""Real durable construction files; modeled systemd/SQL, not native boot proof."""
import copy,json,tempfile,unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import automatic_release_recovery as recovery
from deployment.lib import historical_origin as origin
from deployment.lib.migration_inventory import canonical,digest


class HistoricalBootPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.journal=self.root/'recovery';self.journal.mkdir();self.state=self.root/'state';self.state.mkdir()
        bootstrap={'phase':'bootstrap_adopted','status':'known_good','release_sha':'a'*40,'candidate_slot':'green',
            'traffic_target':'green','schema':{'observed':146},'images':{'backend':'sha256:'+'b'*64}}
        self.known={'sha':'a'*40,'slot':'green','schema':146,'images':bootstrap['images']}
        self.release={'known_good_release':self.known,'active_slot':'green','history':[bootstrap]}
        (self.state/'state.json').write_bytes(canonical(self.release));(self.state/'origin-bootstrap-adopted.json').write_bytes(canonical(bootstrap))
        self.system=SimpleNamespace(state_root=self.state,systemctl_state=Mock(return_value={'enabled':'enabled','active':'inactive'}))
        self.p={'version':1,'environment_id':'isolated-test','guest_uuid':'guest','machine_id':'machine',
            'root_filesystem_uuid':'filesystem','controller_sha':'c'*40,'controller_tree_sha256':'d'*64,
            'expires_at':4000,'control_interface':'ens3','control_mac':'52:54:00:01:02:03',
            'control_address':'10.0.2.15/24','control_gateway':'10.0.2.2'}
        self.host={'database_container_id':'e'*64,'database_system_identifier':'123456789'}
        self.barrier={'fragment':'/etc/systemd/system/madar-isolated-fence.service','dropins':[],
            'state':{'enabled':'enabled','active':'active'}}
        self.enterContext(patch.object(recovery,'BOOT_PREREQUISITES',self.journal/'historical-boot-prerequisites'))
        self.enterContext(patch.object(recovery.admission,'ROOT',self.root/'admissions'))
        self.enterContext(patch.object(recovery,'policy',side_effect=lambda *_:(copy.deepcopy(self.p),copy.deepcopy(self.host))))
        self.enterContext(patch.object(recovery,'readonly_configuration',side_effect=lambda p,**_:Path(p)))
        self.enterContext(patch.object(origin,'bootstrap_record',side_effect=lambda p:json.loads(p.read_bytes())))
        self.enterContext(patch.object(origin,'operation_locks',return_value=nullcontext()))
        self.enterContext(patch('deployment.lib.control_plane_upgrade.require_root_directory',side_effect=lambda p,**kw:Path(p).mkdir(parents=True,exist_ok=True)))
        self.enterContext(patch.object(origin,'network_barrier_control',side_effect=lambda _:copy.deepcopy(self.barrier)))
        self.enterContext(patch.object(recovery,'read',side_effect=lambda p,**_:json.loads(Path(p).read_bytes())))
        units=self.root/'unit';units.write_text('fixed-unit')
        self.enterContext(patch.object(recovery,'protected',return_value=units))
        self.enterContext(patch.object(recovery,'unit_definitions',return_value={'fixed.service':'fixed-unit'}))
        self.installer=self.enterContext(patch.object(recovery,'_install_units',return_value={'unit_sha256':{'fixed.service':__import__('hashlib').sha256(b'fixed-unit').hexdigest()}}))
        self.run=self.enterContext(patch.object(recovery,'run',return_value=canonical(['123456789',146])))
        self.fence=self.enterContext(patch.object(recovery,'verify_fence'))

    def setup(self):return recovery.prepare_historical_boot_prerequisites(self.system)
    def require(self):return recovery.require_historical_boot_prerequisites(self.system)

    def test_ready_units_precede_the_first_signed_inventory_and_issue_no_authority(self):
        with self.assertRaisesRegex(RuntimeError,'not_ready'):self.require()
        ready=self.setup();self.assertEqual(self.require(),ready)
        self.installer.assert_called_once()
        for k in ('deployment_authority_issued','migration_sql_executed','historical_inventory_signed'):self.assertIs(ready[k],False)
        self.assertFalse((self.root/'admissions').exists())
        self.setup();self.installer.assert_called_once() # Verified idempotence before signing.
        self.assertEqual(len(list((recovery.BOOT_PREREQUISITES/'attempts').iterdir())),1)

    def test_enrollment_or_even_an_unconsumed_signed_request_forbids_retroactive_install(self):
        self.known['historical_origin']={'request_id':'already-signed'};(self.state/'state.json').write_bytes(canonical(self.release))
        with self.assertRaisesRegex(RuntimeError,'must_precede_signed_inventory'):self.setup()
        self.known.pop('historical_origin');(self.state/'state.json').write_bytes(canonical(self.release))
        path=self.root/'admissions/historical-origins/retained/bootstrap-origin-request.json';path.parent.mkdir(parents=True);path.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'must_precede_signed_inventory'):self.setup()
        self.installer.assert_not_called();self.assertTrue(path.exists());self.assertEqual(path.read_text(),'{}')

    def test_failed_install_has_durable_intent_and_no_ready_marker_then_exact_retry(self):
        self.installer.side_effect=RuntimeError('controlled installation failure')
        with self.assertRaisesRegex(RuntimeError,'controlled'):self.setup()
        attempts=list((recovery.BOOT_PREREQUISITES/'attempts').iterdir());self.assertEqual(len(attempts),1)
        self.assertTrue((attempts[0]/'intent.json').exists());self.assertTrue((attempts[0]/'failed.json').exists())
        with self.assertRaisesRegex(RuntimeError,'not_ready'):self.require()
        self.installer.side_effect=None;self.setup()
        self.assertTrue((attempts[0]/'failed.json').exists());self.assertEqual(len(list((recovery.BOOT_PREREQUISITES/'attempts').iterdir())),2)

    def test_interruption_retains_intent_and_blocks_signing_until_verified_resume(self):
        self.installer.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.setup()
        attempts=list((recovery.BOOT_PREREQUISITES/'attempts').iterdir());self.assertTrue((attempts[0]/'intent.json').exists())
        self.assertFalse((attempts[0]/'completed.json').exists())
        with self.assertRaisesRegex(RuntimeError,'not_ready'):self.require()
        self.installer.side_effect=None;self.setup();self.assertTrue((attempts[0]/'intent.json').exists())

    def test_changed_policy_database_source_or_controller_cannot_reuse_interrupted_attempt(self):
        self.installer.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.setup()
        self.installer.side_effect=None;self.p['controller_sha']='f'*40
        with self.assertRaisesRegex(RuntimeError,'scope_changed'):self.setup()
        self.assertEqual(self.installer.call_count,1)
        self.p['controller_sha']='c'*40;self.run.return_value=canonical(['987654321',146])
        with self.assertRaisesRegex(RuntimeError,'database_changed'):self.setup()

    def test_reboot_revalidation_requires_exact_barrier_and_recovery_service(self):
        self.setup();self.p.update(version=2,kind='isolated-historical-recovery-policy',historical_origin={'binding':'genuine after enrollment'})
        self.assertEqual(self.require()['operation'],'prepare-historical-boot-prerequisites')
        self.barrier['state']['active']='inactive'
        with self.assertRaisesRegex(RuntimeError,'barrier_changed'):self.require()
        self.barrier['state']['active']='active';self.system.systemctl_state.return_value={'enabled':'disabled','active':'inactive'}
        with self.assertRaisesRegex(RuntimeError,'recovery_unit_changed'):self.require()

    def test_inventory_signing_calls_the_ready_gate_before_observing_or_issuing(self):
        with patch.object(recovery,'require_historical_boot_prerequisites',side_effect=RuntimeError('not_ready')),patch.object(origin,'observe') as observe,patch.object(origin,'journal_lock') as publish:
            with self.assertRaisesRegex(RuntimeError,'not_ready'):origin._prepare(self.system,lambda:None)
        observe.assert_not_called();publish.assert_not_called()

    def test_enrollment_cannot_consume_identity_when_construction_is_not_ready(self):
        with patch.object(recovery,'require_historical_boot_prerequisites',side_effect=RuntimeError('not_ready')),patch.object(origin,'policy') as policy,patch.object(origin,'journal_lock') as consume:
            with self.assertRaisesRegex(RuntimeError,'not_ready'):origin._enroll(self.system,'request','token','confirm',lambda:None)
        policy.assert_not_called();consume.assert_not_called()

    def test_tampered_ready_unit_or_attempt_is_not_repaired(self):
        ready=self.setup();path=recovery.BOOT_PREREQUISITES/'ready.json'
        changed=copy.deepcopy(ready);changed['migration_sql_executed']=True;path.write_bytes(canonical(changed))
        with self.assertRaisesRegex(RuntimeError,'receipt_changed'):self.require()
        path.write_bytes(canonical(ready))
        with patch.object(recovery,'protected',return_value=self.root/'state/state.json'):
            with self.assertRaisesRegex(RuntimeError,'unit_changed'):self.require()
        (recovery.BOOT_PREREQUISITES/'attempts'/ready['attempt_id']/'completed.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'attempt_changed'):self.require()
        self.installer.assert_called_once()

    def test_enrollment_policy_transition_cannot_extend_original_lifetime(self):
        self.setup();self.p.update(version=2,expires_at=4001)
        with self.assertRaisesRegex(RuntimeError,'scope_changed'):self.require()
        self.p['expires_at']=3999;self.require()
