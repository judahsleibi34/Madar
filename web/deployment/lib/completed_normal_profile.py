"""Exact operation profiles for the existing completed-NORMAL coordinator.

Profiles select reviewed contracts; they do not issue authority. Historical
115→136 receipts remain bound to their original operation and schema range.
"""
from dataclasses import dataclass

LEGACY_OPERATION = 'completed-normal-schema115-136-upgrade'
MANUAL_OPERATION = 'completed-normal-schema136-144-maintenance-release'
APPLICATION_OPERATION = 'completed-normal-schema144-application-release'
COMMERCIAL_OPERATION = 'completed-normal-schema144-146-maintenance-release'
FENCED_OPERATION = 'completed-normal-schema146-148-coordinated-release'


@dataclass(frozen=True)
class UpgradeProfile:
    operation: str
    version: int
    source: int
    target: int
    excluded: tuple[int, ...]
    metadata: str
    manifest: str
    migrations: tuple[int, ...]
    compatible_min: int | None = None

    @property
    def minimum(self):
        return self.source if self.compatible_min is None else self.compatible_min

    def supports(self, schema):
        return type(schema) is int and self.source <= schema <= self.target and schema not in self.excluded

    @property
    def maintenance(self):
        return self.operation in {MANUAL_OPERATION, COMMERCIAL_OPERATION, FENCED_OPERATION}


LEGACY = UpgradeProfile(LEGACY_OPERATION, 1, 115, 136, (), 'release.json',
    'migrations-116-136.json', tuple(range(116, 137)))
MANUAL = UpgradeProfile(MANUAL_OPERATION, 2, 136, 144, (142,),
    'schema-136-144-learning-bridge.json', 'migrations-137-144-learning.json',
    (137, 138, 139, 140, 141, 143, 144))
APPLICATION = UpgradeProfile(APPLICATION_OPERATION, 3, 144, 144, (142,),
    'schema-144-application-only.json', '', (), compatible_min=136)
COMMERCIAL = UpgradeProfile(COMMERCIAL_OPERATION, 4, 144, 146, (),
    'schema-144-146-commercial-bridge.json', 'migrations-145-146-commercial.json', (145, 146))
FENCED = UpgradeProfile(FENCED_OPERATION, 5, 146, 148, (),
    'schema-146-148-coordinated.json', 'migrations-147-148-coordinated.json', (147, 148))


def profile(contract):
    """Reject unknown operations and version mixing before any side effect."""
    if not isinstance(contract, dict):
        raise RuntimeError('completed_normal_operation_profile_invalid')
    selected = {LEGACY_OPERATION: LEGACY, MANUAL_OPERATION: MANUAL,
        APPLICATION_OPERATION: APPLICATION, COMMERCIAL_OPERATION: COMMERCIAL,
        FENCED_OPERATION: FENCED}.get(contract.get('operation'))
    if selected is None or type(contract.get('version')) is not int or contract['version'] != selected.version:
        raise RuntimeError('completed_normal_operation_profile_invalid')
    return selected


def expected_origin_grant(contract, mode):
    selected = profile(contract)
    value = {'version': 1 if selected is LEGACY else 2,
        'schema': selected.source, 'release_sha': contract['source_roles']['application_sha'],
        'contract_digest': contract['origin']['write_contract_digest'], 'mode': mode}
    if selected is MANUAL:
        # This is the actually completed origin's historical range, not the
        # successor range. It must never be widened to authorize the candidate.
        value.update(compatible_min=115, compatible_max=136)
    elif selected in (APPLICATION, COMMERCIAL):
        value.update(compatible_min=136, compatible_max=144)
    elif selected is FENCED:
        value.update(compatible_min=144, compatible_max=146)
    return value
