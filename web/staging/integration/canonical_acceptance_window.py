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
    ('request-and-execute-approved-canonical-upgrade.py', 2500),
    ('verify-completed-preserved-business.py', 600),
    ('verify-completed-canonical-reboot.py', 600),
)
RETIREMENT_RESERVE = 180


def require_window(registration, *, now, supervisor_deadline):
    required = sum(seconds for _, seconds in PHASES) + RETIREMENT_RESERVE
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


def execute_steps(run):
    """No pause between completion, preservation verification and real reboot.

    Exceptions stop the sequence; the existing owner supervisor retains cleanup
    responsibility. In particular, a failed execution never triggers reboot.
    """
    for name, timeout in PHASES:
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
    registration = json.loads((root/'canonical-operation-registration.json').read_bytes())['registration']
    if registration['controller_sha'] != manifest['source_current']:
        raise RuntimeError('canonical_acceptance_controller_changed')
    evidence = Path(manifest['evidence'])
    if evidence != Path('/opt/madar-development/evidence/integration')/root.name:
        raise RuntimeError('canonical_acceptance_evidence_scope_changed')
    result = require_window(registration, now=int(time.time()), supervisor_deadline=deadline)
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
        with log.open('xb') as output:
            os.fchmod(output.fileno(), 0o600)
            subprocess.run([sys.executable, '-B', str(script)], stdout=output,
                           stderr=subprocess.STDOUT, timeout=timeout, check=True)
        print(json.dumps({'completed_step': name}), flush=True)
    execute_steps(run)


if __name__ == '__main__':
    main()
