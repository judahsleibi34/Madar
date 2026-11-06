"""Bound the existing disposable canonical rehearsal through target reboot.

This parent-side scheduling check issues no authority. Its input is the
observed root registration, not a replacement for the controller's independent
policy, signature, identity and effect-boundary checks. Never renew a record.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

PHASES = (
    ('request-and-execute-approved-canonical-upgrade.py', 2700),
    ('verify-completed-preserved-business.py', 600),
    ('verify-completed-canonical-reboot.py', 600),
)
RETIREMENT_RESERVE = 180
WINDOW_OVERHEAD = 60
WINDOW_TIMEOUT = sum(seconds for _, seconds in PHASES) + WINDOW_OVERHEAD
REMOTE_REQUEST_TIMEOUT = 2500
MIN_PROTECTED_EXECUTION_SECONDS = 2100
REMOTE_COMPLETION_RESERVE = 60
FAULT_RECOVERY_SECONDS = 1800


def phases(fault_boundary=None):
    if fault_boundary not in (None,'ingress_finalization'):
        raise RuntimeError('canonical_fault_scope_unsupported')
    extra=FAULT_RECOVERY_SECONDS if fault_boundary is not None else 0
    return ((PHASES[0][0],PHASES[0][1]+extra),*PHASES[1:])


RECOVERY_PREPARATION_RESERVE = 1800


def fresh_historical_enrollment_expiry(manifest, *, now):
    """Plan new disposable enrollment only, capped by its original owner lifetime."""
    from datetime import datetime
    lifetime=manifest.get('max_lifetime_seconds')
    if type(now) is not int or type(lifetime) is not int or not 0<lifetime<=10800:
        raise RuntimeError('canonical_fresh_enrollment_lifetime_invalid')
    try:
        created=datetime.fromisoformat(manifest['created_at'])
        if created.tzinfo is None:raise ValueError('timezone required')
        start=int(created.timestamp())
    except (KeyError,TypeError,ValueError,OverflowError):
        raise RuntimeError('canonical_fresh_enrollment_lifetime_invalid') from None
    if start>now:raise RuntimeError('canonical_fresh_enrollment_lifetime_invalid')
    boundary=manifest.get('fault_boundary');phases(boundary)
    deadline=min(start+lifetime,now+(10800 if boundary else 7200))
    if boundary:
        fresh_recovery_expiry(now=now,origin_deadline=deadline,
                              supervisor_deadline=deadline,fault_boundary=boundary)
    elif deadline<=now:raise RuntimeError('canonical_fresh_enrollment_expired')
    return deadline


def fresh_recovery_expiry(*, now, origin_deadline, supervisor_deadline, fault_boundary=None):
    """Budget NEW evidence before backup effects, never extend an existing receipt.

    The independently observed origin and original supervisor bound every value.
    F04 includes restoration/package preparation plus the full execution/recovery
    window. Routine callers retain their existing ninety-minute upper bound.
    """
    phases(fault_boundary)  # Reject unknown actions before any evidence is made.
    if any(type(v) is not int for v in (now,origin_deadline,supervisor_deadline)):
        raise RuntimeError('canonical_fresh_recovery_clock_invalid')
    deadline=min(origin_deadline,supervisor_deadline,now+(10800 if fault_boundary else 5400))
    needed=(sum(budget for _,budget in phases(fault_boundary))+WINDOW_OVERHEAD+
            RETIREMENT_RESERVE+RECOVERY_PREPARATION_RESERVE) if fault_boundary else 1
    if deadline-now<needed:
        raise RuntimeError('canonical_fresh_recovery_preparation_window_insufficient')
    return deadline


def protected_execution_timeout(*, started, now):
    """Reserve the actual remaining remote window before consuming approval.

    Preparation/MFA time is charged once, never reset at execution. This does
    not extend any approval or policy. The installed controller still owns all
    authority checks. A slow preparation may leave an unconsumed approval;
    insufficient time refuses before invoking approved-execute.
    """
    import math
    if (type(started) not in (int, float) or type(now) not in (int, float)
            or not math.isfinite(started) or not math.isfinite(now) or now < started):
        raise RuntimeError('canonical_protected_execution_clock_invalid')
    remaining = math.floor(REMOTE_REQUEST_TIMEOUT - (now - started) - REMOTE_COMPLETION_RESERVE)
    if remaining < MIN_PROTECTED_EXECUTION_SECONDS:
        raise RuntimeError('canonical_protected_execution_window_insufficient')
    return remaining


def bounded_child(argv, *, timeout, log, input=None):
    """Run once in a private process group; preserve diagnostics before refusal.

    The caller must supply its locally calculated remaining timeout. No remote
    monotonic timestamp is accepted. This wrapper issues no execution authority.
    """
    import signal
    import math
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError('canonical_child_budget_invalid')
    log = Path(log)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output, os.fdopen(os.open(str(log)+'.stderr',
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as errors:
        child = subprocess.Popen(argv, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                 stdout=output, stderr=errors, start_new_session=True)
        try:
            child.communicate(input=input, timeout=timeout)
        except BaseException:
            # Kill the whole owned group, including descendants retaining pipes.
            # No retry, and no signalling of a controller's independently owned
            # systemd services. Their durable recovery contract remains in force.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=10)
            output.flush(); os.fsync(output.fileno())
            raise
        output.flush(); os.fsync(output.fileno())
    return subprocess.CompletedProcess(argv, child.returncode, log.read_bytes(), Path(str(log)+'.stderr').read_bytes())


def execute_protected_child(argv, *, started, expires_at, log, input=None, clock=time.monotonic, wall_clock=time.time):
    """Shared actual remote adapter: check the remaining local clock, then run once."""
    import math
    timeout = protected_execution_timeout(started=started, now=clock())
    if type(expires_at) is not int:
        raise RuntimeError('canonical_admission_expiry_invalid')
    remaining = math.floor(expires_at - wall_clock() - REMOTE_COMPLETION_RESERVE)
    if remaining < MIN_PROTECTED_EXECUTION_SECONDS:
        raise RuntimeError('canonical_signed_execution_window_insufficient')
    return bounded_child(argv, timeout=min(timeout, remaining), log=log, input=input)


def require_window(registration, *, now, supervisor_deadline, fault_boundary=None):
    required = sum(budget for _,budget in phases(fault_boundary)) + WINDOW_OVERHEAD + RETIREMENT_RESERVE
    if (not isinstance(registration, dict)
            or registration.get('kind') != 'isolated-canonical-controller-acceptance'
            or any(type(v) is not int for v in
                   (now, supervisor_deadline, registration.get('created_at'), registration.get('expires_at')))):
        raise RuntimeError('canonical_acceptance_lifetime_invalid')
    created, expires = registration['created_at'], registration['expires_at']
    if not created <= now < expires <= created + 10800:
        raise RuntimeError('canonical_acceptance_lifetime_expired_or_invalid')
    deadline = min(expires, supervisor_deadline)
    if deadline - now < required:
        raise RuntimeError('canonical_acceptance_recovery_window_insufficient')
    return {'deadline': deadline, 'required_seconds': required,
            'remaining_seconds': deadline - now, 'authority_issued': False}


def execute_steps(run, *, fault_boundary=None):
    """No pause between completion, preservation verification and real reboot.

    Exceptions stop the sequence; the existing owner supervisor retains cleanup
    responsibility. In particular, a failed execution never triggers reboot.
    """
    for name, timeout in phases(fault_boundary):
        run(name, timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args(); root = args.workspace.absolute()
    parent = Path('/opt/madar-development/scratch/codex-runs')
    if (root.parent != parent or not root.name.startswith('codex-') or root.is_symlink()
            or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077):
        raise RuntimeError('canonical_acceptance_owned_scope_required')
    manifest = json.loads((root/'execution-manifest.json').read_bytes())
    if manifest['run_id'] != root.name:
        raise RuntimeError('canonical_acceptance_scope_changed')
    from datetime import datetime
    # The existing supervisor has a fixed three-hour lifetime, never extended.
    deadline = int(datetime.fromisoformat(manifest['created_at']).timestamp()) + 10800
    enrollment = json.loads((root/'canonical-operation-registration.json').read_bytes())
    registration = enrollment['registration']
    if enrollment['exact_approval_policy']['execution_max_seconds'] != REMOTE_REQUEST_TIMEOUT:
        raise RuntimeError('canonical_fresh_execution_policy_window_invalid')
    if registration['controller_sha'] != manifest['source_current']:
        raise RuntimeError('canonical_acceptance_controller_changed')
    evidence = Path(manifest['evidence'])
    if evidence != Path('/opt/madar-development/evidence/integration')/root.name:
        raise RuntimeError('canonical_acceptance_evidence_scope_changed')
    fault=manifest.get('fault_boundary')
    result = require_window(registration, now=int(time.time()), supervisor_deadline=deadline,fault_boundary=fault)
    path = evidence/'preapproval-acceptance-window.json'
    with path.open('x') as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(result, output); output.flush(); os.fsync(output.fileno())
    def run(name, timeout):
        script = root/name
        if (script.is_symlink() or script.stat().st_uid != os.getuid()
                or script.stat().st_mode & 0o022):
            raise RuntimeError('canonical_acceptance_runner_changed')
        log = evidence/('private-window-'+name+'.log')
        result = bounded_child([sys.executable, '-B', str(script)], timeout=timeout, log=log)
        result.check_returncode()
        print(json.dumps({'completed_step': name}), flush=True)
    execute_steps(run,fault_boundary=fault)


if __name__ == '__main__':
    main()
