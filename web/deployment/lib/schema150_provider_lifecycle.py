"""Schema150 maintenance ordering model inside the protected coordinator.

No CLI, SQL transport, shell selection, approval issuer or production adapter.
The concrete installed actor is still an independently reviewed boundary. This
model separates private provider recovery from the existing positive write grant,
so provider credential probes need not depend on authority not yet issued.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
import re

from deployment.lib import schema149_provider_lifecycle as retained
from deployment.lib.completed_normal_profile import DELETION, RECONCILED

ProtectedProviderJournal = retained.ProtectedProviderJournal
encoded, digest = retained.encoded, retained.digest
FENCE_STEPS = ('arm_boot_interlock', 'fence_ingress', 'fence_supervisors',
               'fence_objects', 'fence_roles', 'drain_sessions')
PRIVATE_STEPS = ('restore_roles_private', 'resume_providers_private', 'verify_native_acceptance')
ACTIVATE_STEPS = ('resume_accepted_workers', 'restore_ingress', 'clear_boot_interlock')
STEPS = FENCE_STEPS + PRIVATE_STEPS + ACTIVATE_STEPS
COUNTERS = ('prepared_transactions', 'other_client_sessions', 'processing_deliveries',
            'processing_outbox', 'processing_deletions', 'processing_steps', 'legacy_deletion_backlog',
            'queue_locks', 'unknown_writers')
FENCES = ('ingress_fenced', 'supervisors_fenced', 'objects_fenced', 'roles_fenced',
          'boot_interlock_armed', 'candidate_read_only')
PRE_GRANT_GATES = ('migration_receipts', 'preservation', 'accepted_images', 'backup_restore_replica',
                   'worker_ownership', 'boot_recovery', 'private_provider_boundary')


def validate_binding(binding):
    keys = {'operation', 'context_sha256', 'source_sha', 'controller_sha',
            'inventory_sha256', 'system_identifier', 'source_schema', 'target_schema'}
    if (not isinstance(binding, dict) or set(binding) != keys
            or binding['operation'] not in {DELETION.operation, RECONCILED.operation}
            or any(not isinstance(binding[key], str) or not re.fullmatch('[0-9a-f]{64}', binding[key])
                   for key in ('context_sha256', 'inventory_sha256'))
            or any(not isinstance(binding[key], str) or not re.fullmatch('[0-9a-f]{40}', binding[key])
                   for key in ('source_sha', 'controller_sha'))
            or not isinstance(binding['system_identifier'], str)
            or not re.fullmatch('[1-9][0-9]{0,19}', binding['system_identifier'])
            or type(binding['source_schema']) is not int or binding['source_schema'] != 146
            or type(binding['target_schema']) is not int
            or binding['target_schema'] != (150 if binding['operation'] == DELETION.operation else 160)):
        raise RuntimeError('schema150_provider_binding_invalid')
    import json
    return json.loads(encoded(binding))


def binding_profile(binding):
    value = validate_binding(binding)
    return DELETION if value['operation'] == DELETION.operation else RECONCILED


def release_contract(binding):
    """Fixed code-owned dispatch; numbers or caller packets select no module."""
    if binding_profile(binding) is RECONCILED:
        from deployment.lib import schema160_release
        return schema160_release
    from deployment.lib import schema150_release
    return schema150_release


class ProviderMaintenance150:
    """Persistent ordering and refusal semantics, not production acceptance.

    The actor must verify existing protected authority, held deployment locks,
    exact source, inventory, resource identity and actual effects at each call.
    Caller flags and journals are history; they cannot issue authority. Fixed
    effect names are the complete interface; no operator command/RPC is accepted.
    """
    def __init__(self, binding, journal, actor):
        if type(journal) is not ProtectedProviderJournal:
            raise RuntimeError('schema150_protected_journal_required')
        self.binding, self.journal, self.actor = validate_binding(binding), journal, actor

    @contextmanager
    def _locked(self):
        # flock the already protected directory, keeping extra files out of the
        # strict append-only journal. A crashed process releases this lock, but
        # its durable intent survives and cannot be blindly replayed.
        retained.require_root_directory(self.journal.root)
        before = self.journal.root.stat()
        descriptor = os.open(self.journal.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            current = os.fstat(descriptor)
            if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino) or current.st_mode & 0o077:
                raise RuntimeError('schema150_provider_journal_identity_changed')
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('schema150_provider_actor_already_active') from None
            yield
        finally:
            os.close(descriptor)

    def _guard(self, purpose):
        self.actor.require_authority(validate_binding(self.binding), purpose=purpose)

    def _state(self):
        records = self.journal.read()
        completed, pending, private_ready = [], None, False
        if records and (records[0]['event'] != 'prepared'
                        or records[0]['payload'].get('binding') != self.binding):
            raise RuntimeError('schema150_provider_journal_binding')
        for index, row in enumerate(records):
            event, payload = row['event'], row['payload']
            if event == 'prepared':
                if index != 0:
                    raise RuntimeError('schema150_provider_journal_sequence')
            elif event == 'effect_intent':
                if (pending or len(completed) >= len(STEPS)
                        or payload != {'step': STEPS[len(completed)]}):
                    raise RuntimeError('schema150_provider_journal_sequence')
                pending = payload['step']
            elif event == 'effect_complete':
                if (pending is None or payload.get('step') != pending
                        or set(payload) not in ({'step'}, {'step', 'reconciled'})
                        or ('reconciled' in payload and payload['reconciled'] is not True)):
                    raise RuntimeError('schema150_provider_journal_sequence')
                completed.append(pending); pending = None
            elif event == 'quiescence':
                if pending or completed != list(FENCE_STEPS):
                    raise RuntimeError('schema150_provider_journal_sequence')
            elif event == 'private_ready':
                if (private_ready or pending or completed != list(FENCE_STEPS + PRIVATE_STEPS)
                        or payload != {'binding_sha256': digest(self.binding)}):
                    raise RuntimeError('schema150_provider_journal_sequence')
                private_ready = True
            else:
                raise RuntimeError('schema150_provider_journal_sequence')
        return records, completed, pending, private_ready

    def _preimage(self):
        records = self._state()[0]
        if not records:
            raise RuntimeError('schema150_provider_not_prepared')
        import json
        return json.loads(encoded(records[0]['payload']['preimage']))

    def prepare(self):
        with self._locked():
            self._guard('prepare')
            if self._state()[0]:
                raise RuntimeError('schema150_provider_already_prepared')
            proof = self.actor.positive_identity_probes(validate_binding(self.binding))
            if (not isinstance(proof, dict)
                    or set(proof) != {'binding_sha256', 'postgrest', 'auth_scope', 'storage_scope', 'database_scope'}
                    or proof['binding_sha256'] != digest(self.binding)
                    or any(proof[key] is not True for key in ('postgrest', 'auth_scope', 'storage_scope', 'database_scope'))):
                raise RuntimeError('schema150_provider_positive_probes_required')
            preimage = self.actor.capture_preimage(validate_binding(self.binding))
            if (not isinstance(preimage, dict) or set(preimage) != {'ingress', 'supervisors', 'objects', 'roles'}
                    or any(not isinstance(value, dict) or not value for value in preimage.values())):
                raise RuntimeError('schema150_provider_original_preimages_required')
            self._guard('prepare')
            self.journal.append('prepared', {'binding': self.binding, 'proof': proof, 'preimage': preimage})

    def _activation_evidence(self, *, granted):
        value = self.actor.activation_evidence(validate_binding(self.binding), self._preimage())
        expected = {'binding_sha256', 'schema', 'delivery_protocol', 'outbox_protocol', 'deletion_protocol',
                    'target_write_authority', 'write_authority_sha256', *PRE_GRANT_GATES}
        if not isinstance(value, dict) or set(value) != expected:
            raise RuntimeError('schema150_provider_activation_evidence_invalid')
        release_contract(self.binding).require_target_protocols(value['schema'], value['delivery_protocol'], value['outbox_protocol'], value['deletion_protocol'])
        if (value['binding_sha256'] != digest(self.binding)
                or any(value[key] is not True for key in PRE_GRANT_GATES)
                or value['target_write_authority'] is not granted
                or (granted and (not isinstance(value['write_authority_sha256'], str)
                                 or not re.fullmatch('[0-9a-f]{64}', value['write_authority_sha256'])))
                or (not granted and value['write_authority_sha256'] is not None)):
            raise RuntimeError('schema150_provider_activation_not_authorized')
        return value

    def _private_boundary(self):
        value = self.actor.observe_private_boundary(validate_binding(self.binding))
        fences = ('ingress_fenced', 'workers_fenced', 'boot_interlock_armed', 'candidate_read_only')
        counters = ('unknown_writers', 'unknown_client_sessions', 'prepared_transactions')
        if (not isinstance(value, dict) or set(value) != {'binding_sha256', *fences, *counters}
                or value['binding_sha256'] != digest(self.binding)
                or any(value[key] is not True for key in fences)
                or any(type(value[key]) is not int or value[key] != 0 for key in counters)):
            raise RuntimeError('schema150_provider_private_boundary_not_fenced')

    def _effect(self, step):
        self._guard(step)
        _, completed, pending, ready = self._state()
        if pending:
            raise RuntimeError('schema150_provider_interrupted_effect_requires_reconciliation')
        if len(completed) >= len(STEPS) or step != STEPS[len(completed)]:
            raise RuntimeError('schema150_provider_effect_sequence')
        if step in PRIVATE_STEPS:
            self._activation_evidence(granted=False)
            self._private_boundary()
        elif step in ACTIVATE_STEPS:
            if not ready:
                raise RuntimeError('schema150_provider_private_acceptance_required')
            self._activation_evidence(granted=True)
        preimage = self._preimage()
        self.journal.append('effect_intent', {'step': step})
        getattr(self.actor, step)(validate_binding(self.binding), preimage)
        self._guard(step)
        if self.actor.verify_effect(step, validate_binding(self.binding), preimage) is not True:
            raise RuntimeError('schema150_provider_effect_not_proven')
        if step in PRIVATE_STEPS: self._private_boundary()
        self.journal.append('effect_complete', {'step': step})

    def _quiescence(self, schema, *, cursor=None):
        self._guard('observe_quiescence')
        if not binding_profile(self.binding).supports(schema):
            raise RuntimeError('schema150_provider_schema_invalid')
        _, completed, pending, _ = self._state()
        if pending or completed != list(FENCE_STEPS):
            raise RuntimeError('schema150_provider_fence_incomplete')
        observed = (self.actor.observe_quiescence(validate_binding(self.binding)) if cursor is None else
                    self.actor.observe_quiescence(validate_binding(self.binding),cursor=cursor))
        if (not isinstance(observed, dict) or set(observed) != {'system_identifier', 'schema', *COUNTERS, *FENCES}
                or observed['system_identifier'] != self.binding['system_identifier']
                or type(observed['schema']) is not int or observed['schema'] != schema
                or any(type(observed[key]) is not int or observed[key] != 0 for key in COUNTERS)
                or any(observed[key] is not True for key in FENCES)):
            raise RuntimeError('schema150_provider_database_not_quiescent')
        self.journal.append('quiescence', observed)
        return observed

    def fence(self):
        with self._locked():
            self._guard('fence')
            _, completed, pending, _ = self._state()
            if pending:
                raise RuntimeError('schema150_provider_interrupted_effect_requires_reconciliation')
            if completed != list(FENCE_STEPS[:len(completed)]):
                raise RuntimeError('schema150_provider_fence_sequence')
            for step in FENCE_STEPS[len(completed):]: self._effect(step)
            return self._quiescence(self.binding['source_schema'])

    def migration_entry(self, source, target, *, cursor=None):
        with self._locked():
            selected = binding_profile(self.binding)
            if (type(source) is not int or type(target) is not int
                    or (source, target) not in tuple((n-1, n) for n in selected.migrations)):
                raise RuntimeError('schema150_provider_migration_order')
            return self._quiescence(source,cursor=cursor)

    def migration_complete(self,*,cursor):
        """Observe committed150 while the existing executor still owns its lock."""
        with self._locked():
            return self._quiescence(self.binding['target_schema'],cursor=cursor)

    def prepare_private_activation(self):
        """Restore original roles/private providers while target grant is absent.

        Ingress, worker and persistent boot barriers remain enforced by the
        installed actor's measured private_provider_boundary. Positive provider
        probes run here, before the existing write handoff—not after public open.
        """
        with self._locked():
            self._guard('prepare_private_activation')
            _, completed, pending, ready = self._state()
            if pending:
                raise RuntimeError('schema150_provider_interrupted_effect_requires_reconciliation')
            sequence = list(FENCE_STEPS + PRIVATE_STEPS)
            if ready:
                raise RuntimeError('schema150_provider_private_acceptance_already_completed')
            if completed != sequence[:len(completed)] or len(completed) < len(FENCE_STEPS):
                raise RuntimeError('schema150_provider_private_sequence')
            if completed == list(FENCE_STEPS): self._quiescence(self.binding['target_schema'])
            for step in sequence[len(completed):]: self._effect(step)
            self._guard('seal_private_acceptance')
            self._activation_evidence(granted=False)
            self._private_boundary()
            self.journal.append('private_ready', {'binding_sha256': digest(self.binding)})
            return {'schema': self.binding['target_schema'], 'private_provider_acceptance_complete': True,
                    'production_authorization_issued': False}

    def activate_after_grant(self,*,clear_boot=True):
        """Observe existing protected target authority; never issue or replay it."""
        if type(clear_boot) is not bool:raise RuntimeError('schema150_provider_boot_completion_invalid')
        with self._locked():
            self._guard('activate_after_grant')
            _, completed, pending, ready = self._state()
            if pending:
                raise RuntimeError('schema150_provider_interrupted_effect_requires_reconciliation')
            if not ready:
                raise RuntimeError('schema150_provider_private_acceptance_required')
            if completed == list(STEPS):
                raise RuntimeError('schema150_provider_activation_already_completed')
            self._activation_evidence(granted=True)
            sequence=STEPS if clear_boot else STEPS[:-1]
            for step in sequence[len(completed):]: self._effect(step)
            return {'schema': self.binding['target_schema'], 'provider_lifecycle_complete': clear_boot,
                    'production_authorization_issued': False, 'customer_database_restored': False}

    def reconcile_pending(self):
        """Fresh observation of one known effect; never re-execute an intent."""
        with self._locked():
            self._guard('reconcile')
            _, _, pending, ready = self._state()
            if pending not in STEPS:
                raise RuntimeError('schema150_provider_no_reconcilable_intent')
            if pending in PRIVATE_STEPS:
                self._activation_evidence(granted=False)
                self._private_boundary()
            if pending in ACTIVATE_STEPS:
                if not ready: raise RuntimeError('schema150_provider_private_acceptance_required')
                self._activation_evidence(granted=True)
            if self.actor.verify_effect(pending, validate_binding(self.binding), self._preimage()) is not True:
                raise RuntimeError('schema150_provider_uncertain_effect_remains_fenced')
            self.journal.append('effect_complete', {'step': pending, 'reconciled': True})
