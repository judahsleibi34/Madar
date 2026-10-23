"""Fail-closed integration boundary for the new provider lifecycle.

The state machine and native staging adapter are testable, but the installed
production runtime adapter is NOT yet implemented. No local PASS packet, root
caller attribute, old148 receipt or test adapter can manufacture that capability.
This deliberate refusal happens before controller/boot/network/database effects.
"""


def require_controller_adapter(actor):
    from deployment.lib.completed_normal_profile import profile, OUTBOX
    if profile(actor.contract) is not OUTBOX:
        raise RuntimeError('schema149_operation_required')
    raise RuntimeError('schema149_protected_provider_adapter_not_installed')


def provider_witness(contract, root):
    raise RuntimeError('schema149_protected_provider_adapter_not_installed')


def migration_provider_guard(contract, witness, runtime):
    raise RuntimeError('schema149_protected_provider_adapter_not_installed')


def require_activation(contract, root):
    # Complete deletion state ownership is also absent at149. Holding the old
    # worker does not satisfy a full deletion-compatibility acceptance gate.
    raise RuntimeError('schema149_provider_and_deletion_activation_not_accepted')
