"""Receiver execution/teardown boundaries; not off-host acceptance evidence."""
import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from deployment.lib.migration_inventory import canonical
WEB=Path(os.environ.get('MADAR_TEST_REPOSITORY_ROOT',Path(__file__).resolve().parents[2]))
spec=importlib.util.spec_from_file_location('physical_test_restore',WEB/'staging/integration/offhost_application_restore.py');receiver=importlib.util.module_from_spec(spec);spec.loader.exec_module(receiver)


class RestorationBoundaries(unittest.TestCase):
    def test_resource_budget_leaves_headroom_and_zero_automatic_restarts(self):
        self.assertLessEqual(sum(receiver.ROLE_BUDGET.values()),2800)
        self.assertLessEqual(sum(receiver.ROLE_CPU.values()),2)
        # Structural defaults alone are not the operational acceptance test.

    def test_unenrolled_or_foreign_scope_stops_before_any_docker_effect(self):
        for name in ('../../production','main','madar-staging','codex-unknown'):
            with self.subTest(name=name),patch.object(receiver,'command') as effect,self.assertRaisesRegex(RuntimeError,'root_scope_required'):
                receiver.restore(name)
            effect.assert_not_called()

    def test_wrong_received_manifest_refuses_before_restore_or_container_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'received.json').write_bytes(canonical({'manifest_sha256':'wrong','receiver_id':'own'}))
            with patch.object(receiver,'root_for',return_value=(root,{'manifest_sha256':'expected','receiver_id':'own'})),patch.object(receiver,'protected',side_effect=lambda p,**kw:p),patch.object(receiver,'restore_archive') as restore,patch.object(receiver,'command') as effect,self.assertRaisesRegex(RuntimeError,'received_scope_changed'):
                receiver.restore('enrolled')
            restore.assert_not_called();effect.assert_not_called()

    def test_cleanup_refuses_foreign_labels_or_mount_references_without_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'restore-owned.json').write_bytes(canonical({'run_id':'run','receiver_id':'own','containers':{'backend':'a'*64},'network':None}))
            for actors in ([{'Id':'a'*64,'Name':'/foreign','Config':{'Labels':{'com.madar.test.receiver':'foreign'}}}],
                           [{'Id':'b'*64,'Name':'/unrelated','Config':{'Labels':{}},'Mounts':[{'Source':str(root)+'/postgres'}]}]):
                calls=[]
                def command(args,**kw):
                    calls.append(args)
                    if args[1:3]==['ps','-aq']:return b'actor\n'
                    if args[1]=='inspect':return json.dumps(actors).encode()
                    self.fail('cleanup attempted a mutation')
                with patch.object(receiver,'root_for',return_value=(root,{'receiver_id':'own'})),patch.object(receiver,'protected',side_effect=lambda p,**kw:p),patch.object(receiver,'command',side_effect=command),self.assertRaisesRegex(RuntimeError,'foreign'):
                    receiver.cleanup('run')
                self.assertFalse(any('rm' in cmd or 'stop' in cmd for cmd in calls))


class RestoreConsumptionTests(unittest.TestCase):
    def test_archiving_active_pointer_does_not_make_an_old_authority_replayable(self):
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first={'attempt_id':str(uuid.uuid4())}
            record=receiver.consume_restore_authority(root,first)
            self.assertEqual(record['attempt_id'],first['attempt_id'])
            (root/'restore-consumed.json').rename(root/'archived-active-pointer.json')
            with self.assertRaisesRegex(RuntimeError,'consumed'):receiver.consume_restore_authority(root,first)
            second={'attempt_id':str(uuid.uuid4())};receiver.consume_restore_authority(root,second)
            self.assertTrue((root/'attempts'/first['attempt_id']/'consumed.json').exists())
            self.assertTrue((root/'attempts'/second['attempt_id']/'consumed.json').exists())

    def test_existing_effects_prevent_even_a_fresh_attempt_from_resetting_target(self):
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'restore-owned.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'existing_restore_effects'):receiver.consume_restore_authority(root,{'attempt_id':str(uuid.uuid4())})
            self.assertFalse((root/'attempts').exists())


class ProviderOwnershipTests(unittest.TestCase):
    def test_authenticated_root_and_explicit_numeric_identity_are_preserved(self):
        self.assertEqual(receiver.storage_identity({}), (0,0))
        self.assertEqual(receiver.storage_identity({'User':''}), (0,0))
        self.assertEqual(receiver.storage_identity({'User':'1000:1001'}), (1000,1001))

    def test_named_or_ambiguous_user_cannot_guess_a_storage_group(self):
        for user in ('node','1000','0:root','-1:0','2147483648:0'):
            with self.subTest(user=user),self.assertRaisesRegex(RuntimeError,'requires_review'):
                receiver.storage_identity({'User':user})
