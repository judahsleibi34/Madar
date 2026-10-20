"""Capture original roles for a fenced backup without granting restore authority.

This is a missing backup input adapter, not a backup executor. Ordinary backup
capture still needs a maintenance-specific object/database path and independent
restore/replica proof before schema150 can be registered. Existing backup formats
and historical receipts are not rewritten by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from deployment.lib.completed_normal_admission import ADMISSIONS, digest, encoded
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.schema150_provider_adapter import Schema150ProviderAdapter
from deployment.lib.schema150_provider_lifecycle import FENCE_STEPS, ProviderMaintenance150, ProtectedProviderJournal, validate_binding

MAX_ROLES_BYTES = 4 * 1024 * 1024


def _capture(path, maximum):
    """Read the protected preimage once; authenticate the captured bytes."""
    checked = protected(path, private=True)
    fd = os.open(checked, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_size > maximum:
            raise RuntimeError('maintenance_roles_private_input_required')
        value = stream.read(maximum + 1)
    if len(value) > maximum:
        raise RuntimeError('maintenance_roles_input_limit')
    return value


@dataclass(frozen=True)
class OriginalRoleArchive:
    """Immutable input snapshot; this object is not operational evidence."""
    metadata_bytes: bytes
    sql_bytes: bytes

    def verify(self, binding, *, expected_schema):
        validate_binding(binding)
        if (type(self.metadata_bytes) is not bytes or type(self.sql_bytes) is not bytes
                or len(self.metadata_bytes) > 16384 or not 0 < len(self.sql_bytes) <= MAX_ROLES_BYTES):
            raise RuntimeError('maintenance_roles_input_limit')
        try:
            metadata = json.loads(self.metadata_bytes)
            self.sql_bytes.decode('utf-8')
        except (ValueError, UnicodeError):
            raise RuntimeError('maintenance_roles_encoding_invalid') from None
        keys = {'version', 'binding_sha256', 'captured_schema', 'preimage_sha256',
                'original_roles_sha256', 'sql_sha256', 'sql_bytes', 'authority_issued'}
        if (not isinstance(metadata, dict) or set(metadata) != keys
                or type(metadata['version']) is not int or metadata['version'] != 1
                or metadata['binding_sha256'] != digest(binding)
                or type(expected_schema) is not int
                or type(metadata['captured_schema']) is not int or metadata['captured_schema'] != expected_schema
                or expected_schema not in (binding['source_schema'], binding['target_schema'])
                or any(not isinstance(metadata[k], str) or not re.fullmatch('[0-9a-f]{64}', metadata[k])
                       for k in ('preimage_sha256', 'original_roles_sha256', 'sql_sha256'))
                or type(metadata['sql_bytes']) is not int or metadata['sql_bytes'] != len(self.sql_bytes)
                or not 0 < len(self.sql_bytes) <= MAX_ROLES_BYTES
                or hashlib.sha256(self.sql_bytes).hexdigest() != metadata['sql_sha256']
                or metadata['authority_issued'] is not False):
            raise RuntimeError('maintenance_roles_binding_invalid')
        return metadata


def capture_original_roles(adapter):
    """Only the concrete protected actor can capture a fresh fenced preimage.

    No caller PASS, alternative transport or supplied role SQL is accepted. A
    returned snapshot still needs the ordinary backup/restore/replica integration;
    it cannot satisfy backup eligibility by itself.
    """
    if type(adapter) is not Schema150ProviderAdapter or os.geteuid() != 0:
        raise RuntimeError('maintenance_roles_protected_actor_required')
    adapter.require_authority(adapter.binding, purpose='backup')
    maintenance = ProviderMaintenance150(adapter.binding,
        ProtectedProviderJournal(adapter.root / 'provider-journal'), adapter)
    with maintenance._locked():
        return _capture_roles_locked(adapter, maintenance)


def _capture_roles_locked(adapter, maintenance):
    binding = adapter.binding
    adapter.require_authority(binding, purpose='backup')
    journal = maintenance.journal
    rows, completed, pending, ready = maintenance._state()
    if pending or ready or completed != list(FENCE_STEPS) or not rows:
        raise RuntimeError('maintenance_roles_complete_fence_required')
    observed = adapter.observe_quiescence(binding)
    schema = observed['schema']
    if schema not in (binding['source_schema'], binding['target_schema']):
        raise RuntimeError('maintenance_roles_backup_boundary_invalid')
    # This method authenticates the original recorded roles while current LOGIN
    # attributes are restricted. Never substitute a current pg_dumpall result.
    sql = adapter.backup_role_archive(binding)
    original = rows[0]['payload']['preimage']
    metadata = {'version': 1, 'binding_sha256': digest(binding), 'captured_schema': schema,
        'preimage_sha256': digest(original), 'original_roles_sha256': digest(original['roles']['original']),
        'sql_sha256': hashlib.sha256(sql).hexdigest(), 'sql_bytes': len(sql), 'authority_issued': False}
    value = OriginalRoleArchive(encoded(metadata), sql)
    value.verify(binding, expected_schema=schema)
    adapter.require_authority(binding, purpose='backup')
    if journal.read() != rows:
        raise RuntimeError('maintenance_roles_preimage_changed')
    return value


def seal_role_input(adapter, *, stage):
    """Publish one original-role input at a fixed append-only admission path.

    An interrupted partial publication is retained and refuses automatic replay.
    The complete marker is written last. Nothing updates ordinary LATEST or a
    backup success receipt; the unfinished backup pipeline must consume these
    captured bytes before its own manifest/checksum sealing.
    """
    if stage not in ('pre-migration', 'post-migration'):
        raise RuntimeError('maintenance_roles_stage_invalid')
    value = capture_original_roles(adapter)
    expected = adapter.binding['source_schema' if stage == 'pre-migration' else 'target_schema']
    value.verify(adapter.binding, expected_schema=expected)
    root = ADMISSIONS / adapter.binding['context_sha256']
    if adapter.root != root:
        raise RuntimeError('maintenance_roles_admission_path_invalid')
    # protected() validates every ancestor before creating the new directory.
    protected(root / 'admission.json')
    destination = root / (stage + '-original-roles')
    destination.mkdir(mode=0o700)
    directory = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        exclusive(destination / 'roles.sql', value.sql_bytes)
        exclusive(destination / 'metadata.json', value.metadata_bytes)
        adapter.require_authority(adapter.binding, purpose='backup')
        exclusive(destination / 'COMPLETE', encoded({'metadata_sha256': hashlib.sha256(value.metadata_bytes).hexdigest()}))
        os.fsync(directory)
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(parent)
        finally: os.close(parent)
    finally:
        os.close(directory)
    return destination


def read_role_input(root, binding, *, stage, expected_metadata_sha256):
    """Return authenticated SQL bytes, never a pathname to reopen later."""
    if stage not in ('pre-migration', 'post-migration') or root != ADMISSIONS / binding['context_sha256']:
        raise RuntimeError('maintenance_roles_admission_path_invalid')
    if not re.fullmatch('[0-9a-f]{64}', str(expected_metadata_sha256)):
        raise RuntimeError('maintenance_roles_expected_digest_required')
    path = root / (stage + '-original-roles')
    marker = json.loads(_capture(path / 'COMPLETE', 4096))
    metadata = _capture(path / 'metadata.json', 16384)
    if marker != {'metadata_sha256': expected_metadata_sha256} or hashlib.sha256(metadata).hexdigest() != expected_metadata_sha256:
        raise RuntimeError('maintenance_roles_input_changed')
    value = OriginalRoleArchive(metadata, _capture(path / 'roles.sql', MAX_ROLES_BYTES))
    value.verify(binding, expected_schema=binding['source_schema' if stage == 'pre-migration' else 'target_schema'])
    return value
