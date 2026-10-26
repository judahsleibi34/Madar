"""Persistent provider maintenance inside the existing protected coordinator.

This module has no command line, credentials, SQL runner or authority issuer.
An installed actor must supply the concrete, independently verified effects and
hold the existing deploy/upgrade/runtime locks. No production adapter is supplied
here. Journal evidence is private history, never operational authorization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from deployment.lib.control_plane_upgrade import require_root_directory
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected


FENCE_STEPS = ("arm_boot_interlock", "fence_ingress", "fence_supervisors",
               "fence_objects", "fence_roles", "drain_sessions")
RELEASE_STEPS = ("restore_roles", "resume_providers_private", "verify_native_acceptance",
                 "restore_ingress", "resume_accepted_workers", "clear_boot_interlock")
COUNTERS = ("prepared_transactions", "other_client_sessions", "processing_deliveries",
            "processing_outbox", "queue_locks", "unknown_writers")
FENCES = ("ingress_fenced", "supervisors_fenced", "objects_fenced", "roles_fenced",
          "boot_interlock_armed", "candidate_read_only")
ACTIVATION_GATES = ("migration_receipts", "preservation", "accepted_images", "backup_restore_replica",
                    "worker_ownership", "boot_recovery", "target_write_authority")


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def validate_binding(binding):
    keys = {"operation", "context_sha256", "source_sha", "controller_sha",
            "inventory_sha256", "system_identifier", "source_schema", "target_schema"}
    if (not isinstance(binding, dict) or set(binding) != keys
            or not re.fullmatch(r"completed-normal-[a-z0-9-]+", str(binding["operation"]))
            or any(not re.fullmatch(r"[0-9a-f]{64}", str(binding[k])) for k in
                   ("context_sha256", "inventory_sha256"))
            or any(not re.fullmatch(r"[0-9a-f]{40}", str(binding[k])) for k in
                   ("source_sha", "controller_sha"))
            or not re.fullmatch(r"[1-9][0-9]{0,19}", str(binding["system_identifier"]))
            or type(binding["source_schema"]) is not int or binding["source_schema"] != 146
            or type(binding["target_schema"]) is not int or binding["target_schema"] != 149):
        raise RuntimeError("provider_maintenance_binding_invalid")
    # Detach from mutable caller objects before any privileged callback.
    return json.loads(encoded(binding))


class ProtectedProviderJournal:
    """Append-only root-private records under an already protected admission.

    The parent coordinator owns locking. Exclusive creation rejects duplicate
    publication; each record and its containing directory are fsynced before an
    external effect can begin. A partial final write blocks instead of replaying.
    """
    def __init__(self, root):
        self.root = Path(root)
        require_root_directory(self.root)
        if self.root.stat().st_mode & 0o077:
            raise RuntimeError("provider_maintenance_journal_not_private")

    def read(self):
        require_root_directory(self.root)
        paths = sorted(self.root.iterdir())
        if len(paths) > 256:
            raise RuntimeError("provider_maintenance_journal_limit")
        records = []
        for index, path in enumerate(paths):
            if path.name != f"{index:04d}.json":
                raise RuntimeError("provider_maintenance_journal_sequence")
            source = protected(path, private=True)
            if source.stat().st_size > 2 * 1024 * 1024:
                raise RuntimeError("provider_maintenance_journal_record_limit")
            record = json.loads(source.read_bytes())
            if (set(record) != {"sequence", "previous_sha256", "event", "payload"}
                    or type(record["sequence"]) is not int or record["sequence"] != index
                    or record["previous_sha256"] != (digest(records[-1]) if records else None)):
                raise RuntimeError("provider_maintenance_journal_chain")
            records.append(record)
        return records

    def append(self, event, payload):
        records = self.read()
        value = {"sequence": len(records), "previous_sha256": digest(records[-1]) if records else None,
                 "event": event, "payload": payload}
        body = encoded(value)
        if len(records) >= 256 or len(body) > 2 * 1024 * 1024:
            raise RuntimeError("provider_maintenance_journal_limit")
        exclusive(self.root / f"{len(records):04d}.json", body)


class ProviderMaintenance:
    """Fail-closed lifecycle; adapters must remeasure real resources each time.

    ``require_authority`` checks the installed source, exact inventory, held locks
    and the existing fresh protected authorization. ``verify_effect`` observes
    actual resources, not a returned PASS marker. Preimages include role state
    BEFORE fencing so backup/restore cannot mistake NOLOGIN for the original role
    contract. Concrete adapters must stop object-byte writers as well as SQL.
    """
    def __init__(self, binding, journal, actor):
        self.binding = validate_binding(binding)
        self.journal, self.actor = journal, actor

    def _guard(self, purpose):
        self.actor.require_authority(json.loads(encoded(self.binding)), purpose=purpose)

    def _records(self):
        records = self.journal.read()
        if records and (records[0]["event"] != "prepared"
                        or records[0]["payload"].get("binding") != self.binding):
            raise RuntimeError("provider_maintenance_journal_binding")
        return records

    def _preimage(self):
        records = self._records()
        if not records:
            raise RuntimeError("provider_maintenance_not_prepared")
        return json.loads(encoded(records[0]["payload"]["preimage"]))

    def _pending(self):
        records = self._records()
        return records[-1]["payload"]["step"] if records and records[-1]["event"] == "effect_intent" else None

    def prepare(self):
        self._guard("prepare")
        if self._records():
            raise RuntimeError("provider_maintenance_already_prepared")
        proof = self.actor.positive_identity_probes(self.binding)
        required = {"binding_sha256", "postgrest", "auth_scope", "storage_scope", "database_scope"}
        if (not isinstance(proof, dict) or set(proof) != required
                or proof["binding_sha256"] != digest(self.binding)
                or any(proof[k] is not True for k in required - {"binding_sha256"})):
            raise RuntimeError("provider_maintenance_positive_probes_required")
        preimage = self.actor.capture_preimage(self.binding)
        if (not isinstance(preimage, dict) or set(preimage) != {"ingress", "supervisors", "objects", "roles"}
                or any(not isinstance(value, dict) or not value for value in preimage.values())):
            raise RuntimeError("provider_maintenance_preimages_required")
        self._guard("prepare")
        self.journal.append("prepared", {"binding": self.binding, "proof": proof,
                                          "preimage": preimage})

    def _effect(self, step):
        self._guard(step)
        if self._pending():
            raise RuntimeError("provider_maintenance_interrupted_effect_requires_reconciliation")
        preimage = self._preimage()
        if step in RELEASE_STEPS:
            self._require_activation_evidence()
        self.journal.append("effect_intent", {"step": step})
        # Only fixed module-owned step names reach the concrete protected actor.
        getattr(self.actor, step)(self.binding, preimage)
        self._guard(step)
        if self.actor.verify_effect(step, self.binding, preimage) is not True:
            raise RuntimeError("provider_maintenance_effect_not_proven")
        self.journal.append("effect_complete", {"step": step})

    def reconcile_pending(self):
        """Fresh authorized observation only; never repeats an uncertain effect."""
        self._guard("reconcile")
        step = self._pending()
        if step not in FENCE_STEPS + RELEASE_STEPS:
            raise RuntimeError("provider_maintenance_no_reconcilable_intent")
        if step in RELEASE_STEPS:
            self._require_activation_evidence()
        if self.actor.verify_effect(step, self.binding, self._preimage()) is not True:
            raise RuntimeError("provider_maintenance_uncertain_effect_remains_fenced")
        self.journal.append("effect_complete", {"step": step, "reconciled": True})

    def _completed(self):
        return [r["payload"]["step"] for r in self._records() if r["event"] == "effect_complete"]

    def fence(self):
        self._guard("fence")
        completed = self._completed()
        if completed != list(FENCE_STEPS[:len(completed)]) or len(completed) > len(FENCE_STEPS):
            raise RuntimeError("provider_maintenance_fence_sequence")
        for step in FENCE_STEPS[len(completed):]:
            self._effect(step)
        return self.require_quiescence(146)

    def require_quiescence(self, schema):
        """Reobserve immediately before each migration; old receipts do not pass."""
        self._guard("observe_quiescence")
        if type(schema) is not int or schema not in (146, 147, 148, 149):
            raise RuntimeError("provider_maintenance_schema_invalid")
        if self._pending() or self._completed() != list(FENCE_STEPS):
            raise RuntimeError("provider_maintenance_fence_incomplete")
        observed = self.actor.observe_quiescence(self.binding)
        if (not isinstance(observed, dict) or set(observed) != {"system_identifier", "schema", *COUNTERS, *FENCES}
                or observed["system_identifier"] != self.binding["system_identifier"]
                or type(observed["schema"]) is not int or observed["schema"] != schema
                or any(type(observed[k]) is not int or observed[k] != 0 for k in COUNTERS)
                or any(observed[k] is not True for k in FENCES)):
            raise RuntimeError("provider_maintenance_database_not_quiescent")
        self.journal.append("quiescence", observed)
        return observed

    def migration_entry(self, source, target):
        if (source, target) not in ((146, 147), (147, 148), (148, 149)):
            raise RuntimeError("provider_maintenance_migration_order")
        return self.require_quiescence(source)

    def _require_activation_evidence(self):
        evidence = self.actor.activation_evidence(self.binding, self._preimage())
        if (not isinstance(evidence, dict) or set(evidence) != {"binding_sha256", "schema", "delivery_protocol", "outbox_protocol", *ACTIVATION_GATES}
                or evidence["binding_sha256"] != digest(self.binding)
                or type(evidence["schema"]) is not int or evidence["schema"] != 149
                or any(type(evidence[k]) is not int or evidence[k] != 2 for k in ("delivery_protocol", "outbox_protocol"))
                or any(evidence[k] is not True for k in ACTIVATION_GATES)):
            raise RuntimeError("provider_maintenance_target_activation_not_authorized")

    def activate(self):
        """Restore only accepted149; issuance stays in existing write handoff.

        Until the final interlock-clearing effect the durable boot fence remains
        armed. A partially completed activation is NOT quiescent; recovery must
        remeasure and freshly authorize continuation, or explicitly refence using
        a separately reviewed actor. Loss of the final acknowledgement needs
        reconciliation of the already-cleared interlock, never blind replay.
        """
        self._guard("activate")
        completed = self._completed()
        sequence = list(FENCE_STEPS + RELEASE_STEPS)
        if completed == sequence:
            raise RuntimeError("provider_maintenance_activation_already_completed")
        if completed != sequence[:len(completed)] or len(completed) < len(FENCE_STEPS):
            raise RuntimeError("provider_maintenance_activation_sequence")
        if self._pending():
            raise RuntimeError("provider_maintenance_interrupted_effect_requires_reconciliation")
        self._require_activation_evidence()
        if completed == list(FENCE_STEPS):
            self.require_quiescence(149)
        for step in sequence[len(completed):]:
            self._effect(step)
        return {"schema": 149, "provider_lifecycle_complete": True,
                "production_authorization_issued": False, "customer_database_restored": False}
