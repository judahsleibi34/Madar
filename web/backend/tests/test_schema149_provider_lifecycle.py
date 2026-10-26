"""Exercise the lifecycle, real durable journal and injected protected effects.

These are state-machine/transport tests, not production supervisor or provider
acceptance. The concrete adapter must independently prove every observed gate.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.lib import schema149_provider_lifecycle as lifecycle


def binding():
    return {"operation": "completed-normal-schema146-149-coordinated-release",
            "context_sha256": "a" * 64, "source_sha": "b" * 40,
            "controller_sha": "c" * 40, "inventory_sha256": "d" * 64,
            "system_identifier": "123456789", "source_schema": 146, "target_schema": 149}


class MemoryJournal:
    def __init__(self):
        self.records = []

    def read(self):
        return copy.deepcopy(self.records)

    def append(self, event, payload):
        self.records.append(copy.deepcopy({"event": event, "payload": payload}))


class Actor:
    def __init__(self):
        self.calls = []
        self.effects = set()
        self.crash = None
        self.before_effect = False
        self.authorized = True
        self.schema = 146
        self.observed = {"system_identifier": "123456789", "schema": self.schema,
                         **{key: 0 for key in lifecycle.COUNTERS},
                         **{key: True for key in lifecycle.FENCES}}
        self.activation = {"binding_sha256": lifecycle.digest(binding()), "schema": 149,
                           "delivery_protocol": 2, "outbox_protocol": 2,
                           **{key: True for key in lifecycle.ACTIVATION_GATES}}

    def require_authority(self, expected, *, purpose):
        if not self.authorized or expected != binding():
            raise RuntimeError("fixture_fresh_authority_missing")
        self.calls.append(("guard", purpose))

    def positive_identity_probes(self, expected):
        self.calls.append(("positive_probes",))
        return {"binding_sha256": lifecycle.digest(expected), "postgrest": True,
                "auth_scope": True, "storage_scope": True, "database_scope": True}

    def capture_preimage(self, expected):
        self.calls.append(("preimage",))
        return {"ingress": {"route": "old"}, "supervisors": {"unit": "old"},
                "objects": {"store": "old"}, "roles": {"authenticator": {"login": True}}}

    def effect(self, step, expected, preimage):
        self.calls.append(("effect", step))
        if self.crash == step and self.before_effect:
            raise RuntimeError("fixture_process_crash")
        self.effects.add(step)
        if self.crash == step:
            raise RuntimeError("fixture_process_crash")

    def verify_effect(self, step, expected, preimage):
        self.calls.append(("verify", step))
        return step in self.effects

    def observe_quiescence(self, expected):
        return copy.deepcopy(self.observed)

    def activation_evidence(self, expected, preimage):
        return copy.deepcopy(self.activation)


for _step in lifecycle.FENCE_STEPS + lifecycle.RELEASE_STEPS:
    setattr(Actor, _step, lambda self, expected, preimage, step=_step: self.effect(step, expected, preimage))


class LifecycleTests(unittest.TestCase):
    def fixture(self):
        actor, journal = Actor(), MemoryJournal()
        driver = lifecycle.ProviderMaintenance(binding(), journal, actor)
        return driver, actor, journal

    def fenced(self):
        driver, actor, journal = self.fixture()
        driver.prepare()
        driver.fence()
        return driver, actor, journal

    def test_positive_probes_and_preimages_precede_all_mutations(self):
        driver, actor, journal = self.fenced()
        calls = actor.calls
        first_effect = next(i for i, item in enumerate(calls) if item[0] == "effect")
        self.assertLess(calls.index(("positive_probes",)), first_effect)
        self.assertLess(calls.index(("preimage",)), first_effect)
        self.assertEqual(journal.records[0]["payload"]["preimage"]["roles"]["authenticator"]["login"], True)
        events = [(item["event"], item["payload"].get("step")) for item in journal.records]
        for step in lifecycle.FENCE_STEPS:
            self.assertLess(events.index(("effect_intent", step)), events.index(("effect_complete", step)))

    def test_missing_positive_probe_never_fences(self):
        driver, actor, journal = self.fixture()
        actor.positive_identity_probes = lambda expected: {"binding_sha256": lifecycle.digest(expected),
            "postgrest": False, "auth_scope": True, "storage_scope": True, "database_scope": True}
        with self.assertRaisesRegex(RuntimeError, "positive_probes_required"):
            driver.prepare()
        self.assertEqual(journal.records, [])
        self.assertEqual(actor.effects, set())

    def test_all_fence_crashes_require_fresh_observed_reconciliation(self):
        for step in lifecycle.FENCE_STEPS:
            with self.subTest(step=step):
                driver, actor, journal = self.fixture()
                driver.prepare()
                actor.crash = step
                with self.assertRaisesRegex(RuntimeError, "process_crash"):
                    driver.fence()
                self.assertEqual(journal.records[-1], {"event": "effect_intent", "payload": {"step": step}})
                restarted = lifecycle.ProviderMaintenance(binding(), journal, actor)
                with self.assertRaisesRegex(RuntimeError, "interrupted_effect"):
                    restarted.fence()
                actor.authorized = False
                with self.assertRaisesRegex(RuntimeError, "fresh_authority_missing"):
                    restarted.reconcile_pending()
                actor.authorized = True
                restarted.reconcile_pending()
                actor.crash = None
                restarted.fence()
                self.assertEqual(sum(call == ("effect", step) for call in actor.calls), 1)

    def test_unapplied_or_unknown_interruption_never_replays_effect(self):
        for step in lifecycle.FENCE_STEPS:
            with self.subTest(step=step):
                driver, actor, journal = self.fixture()
                driver.prepare()
                actor.crash, actor.before_effect = step, True
                with self.assertRaisesRegex(RuntimeError, "process_crash"):
                    driver.fence()
                with self.assertRaisesRegex(RuntimeError, "uncertain_effect"):
                    driver.reconcile_pending()
                self.assertEqual(sum(call == ("effect", step) for call in actor.calls), 1)
                self.assertEqual(driver._pending(), step)

    def test_reentry_rechecks_every_quiescence_property(self):
        driver, actor, journal = self.fenced()
        original = copy.deepcopy(actor.observed)
        for key in lifecycle.COUNTERS + lifecycle.FENCES + ("schema", "system_identifier"):
            with self.subTest(key=key):
                actor.observed = copy.deepcopy(original)
                actor.observed[key] = False if key in lifecycle.FENCES else 1
                with self.assertRaisesRegex(RuntimeError, "not_quiescent"):
                    driver.migration_entry(146, 147)
        actor.observed = original
        actor.observed["prepared_transactions"] = False
        with self.assertRaisesRegex(RuntimeError, "not_quiescent"):
            driver.migration_entry(146, 147)

    def test_exact_schema_chain_is_required_and_intermediate_activation_denied(self):
        driver, actor, journal = self.fenced()
        for source, target in ((146, 149), (148, 147), (149, 150)):
            with self.assertRaisesRegex(RuntimeError, "migration_order"):
                driver.migration_entry(source, target)
        for source, target in ((146, 147), (147, 148), (148, 149)):
            actor.observed["schema"] = source
            driver.migration_entry(source, target)
            actor.activation["schema"] = target
            actor.observed["schema"] = target
            if target != 149:
                with self.assertRaisesRegex(RuntimeError, "activation_not_authorized"):
                    driver.activate()
                self.assertFalse(any(step in actor.effects for step in lifecycle.RELEASE_STEPS))
        result = driver.activate()
        self.assertFalse(result["production_authorization_issued"])
        self.assertEqual(driver._completed(), list(lifecycle.FENCE_STEPS + lifecycle.RELEASE_STEPS))
        with self.assertRaisesRegex(RuntimeError, "already_completed"):
            driver.activate()

    def test_every_activation_gate_and_protocol_is_mandatory(self):
        driver, actor, journal = self.fenced()
        actor.observed["schema"] = 149
        original = copy.deepcopy(actor.activation)
        for key in lifecycle.ACTIVATION_GATES + ("delivery_protocol", "outbox_protocol", "schema", "binding_sha256"):
            with self.subTest(key=key):
                actor.activation = copy.deepcopy(original)
                actor.activation[key] = False
                with self.assertRaisesRegex(RuntimeError, "activation_not_authorized"):
                    driver.activate()
        self.assertFalse(any(step in actor.effects for step in lifecycle.RELEASE_STEPS))

    def test_activation_crashes_remain_interlocked_until_verified_reentry(self):
        for step in lifecycle.RELEASE_STEPS:
            with self.subTest(step=step):
                driver, actor, journal = self.fenced()
                actor.observed["schema"] = 149
                actor.crash = step
                with self.assertRaisesRegex(RuntimeError, "process_crash"):
                    driver.activate()
                restarted = lifecycle.ProviderMaintenance(binding(), journal, actor)
                with self.assertRaisesRegex(RuntimeError, "interrupted_effect"):
                    restarted.activate()
                restarted.reconcile_pending()
                actor.crash = None
                if step != lifecycle.RELEASE_STEPS[-1]:
                    restarted.activate()
                self.assertEqual(sum(call == ("effect", step) for call in actor.calls), 1)

    def test_schema_or_artifact_change_during_activation_blocks_next_effect(self):
        for changed in ("schema", "accepted_images", "target_write_authority"):
            with self.subTest(changed=changed):
                driver, actor, journal = self.fenced()
                actor.observed["schema"] = 149
                original = actor.restore_roles

                def restore(expected, preimage):
                    original(expected, preimage)
                    actor.activation[changed] = False

                actor.restore_roles = restore
                with self.assertRaisesRegex(RuntimeError, "activation_not_authorized"):
                    driver.activate()
                self.assertIn("restore_roles", actor.effects)
                self.assertNotIn("resume_providers_private", actor.effects)
                self.assertNotIn("restore_ingress", actor.effects)

    def test_exact_binding_cannot_be_replaced_after_prepare(self):
        driver, actor, journal = self.fenced()
        for key in ("source_sha", "controller_sha", "context_sha256", "inventory_sha256", "system_identifier"):
            with self.subTest(key=key):
                changed = binding()
                changed[key] = "2" * len(changed[key])
                alternate = lifecycle.ProviderMaintenance(changed, journal, actor)
                with self.assertRaises(RuntimeError):
                    alternate.require_quiescence(146)
        caller_binding = binding()
        detached = lifecycle.ProviderMaintenance(caller_binding, journal, actor)
        caller_binding["source_sha"] = "9" * 40
        detached.require_quiescence(146)

    def test_valid_receipt_does_not_replace_fresh_authority(self):
        driver, actor, journal = self.fenced()
        actor.authorized = False
        with self.assertRaisesRegex(RuntimeError, "fresh_authority_missing"):
            driver.migration_entry(146, 147)
        with self.assertRaisesRegex(RuntimeError, "fresh_authority_missing"):
            driver.activate()


class ProtectedJournalTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        # Only privileged-path policy is replaced for the owned test directory.
        # Exclusive publication, fsync, JSON parsing and the hash chain are real.
        directory = patch.object(lifecycle, "require_root_directory", lambda path: None)
        file_check = patch.object(lifecycle, "protected", lambda path, **kwargs: Path(path))
        directory.start()
        file_check.start()
        self.addCleanup(directory.stop)
        self.addCleanup(file_check.stop)
        return lifecycle.ProtectedProviderJournal(root), root

    def test_records_survive_new_process_object_and_reject_partial_write(self):
        journal, root = self.fixture()
        journal.append("intent", {"step": "fence_roles"})
        self.assertEqual((root / "0000.json").stat().st_mode & 0o777, 0o600)
        restarted = lifecycle.ProtectedProviderJournal(root)
        self.assertEqual(restarted.read()[0]["event"], "intent")
        (root / "0001.json").write_text('{"sequence":')
        with self.assertRaises(json.JSONDecodeError):
            restarted.read()

    def test_changed_predecessor_and_unexpected_names_block(self):
        journal, root = self.fixture()
        journal.append("first", {})
        journal.append("second", {})
        first = root / "0000.json"
        value = json.loads(first.read_text())
        value["payload"] = {"changed": True}
        first.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, "journal_chain"):
            journal.read()
        (root / "0001.json").unlink()
        (root / "unexpected.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "journal_sequence"):
            journal.read()


if __name__ == "__main__":
    unittest.main()
