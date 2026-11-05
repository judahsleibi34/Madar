"""Finite Gate A fault boundaries; test orchestration, never recovery authority.

A boundary observation is made by the independently scoped installed-test
adapter. This module never starts SQL, changes grants or clears a fence.
"""
import os
from pathlib import Path
import select
import signal
import time

BOUNDARIES = {
    'before_sql': ('pre_migration_backup_pending', False),
    'committed_sql': ('post_migration_backup_pending', True),
    'worker_handoff': ('accepted_workers_pending', True),
    'ingress_finalization': ('service_adopt_completed', True),
}


def matches(name, observation):
    phase, committed = BOUNDARIES[name]
    if observation.get('phase') != phase or observation.get('normal_completion') is not False:
        return False
    if observation.get('approval_consumed') is not True:
        return False
    if name=='ingress_finalization' and observation.get('normal_acceptance') is not False:
        return False
    if committed:
        return (observation.get('schema') == 160
                and observation.get('committed') == list(range(147, 161))
                and observation.get('executor_status') == 'completed')
    return (observation.get('schema') == 146 and observation.get('committed') == []
            and observation.get('migration_intent') is False)


def process_identity(pid):
    """No command-line contents are returned to logs; caller supplies exact argv."""
    if type(pid) is not int or pid <= 1 or pid == os.getpid():
        raise RuntimeError('fault_target_pid_invalid')
    root = Path('/proc')/str(pid)
    # comm may contain spaces or parentheses; fields after its final ')' start at3.
    fields = (root/'stat').read_text().rsplit(')', 1)[1].split()
    return (int(fields[19]), (root/'cmdline').read_bytes(), os.getpgid(pid))


def interrupt_exact_process(pid, expected, *, boundary, observe, guard, record,
                            timeout=30, clock=time.monotonic):
    """Freeze/reobserve/kill one pinned session, or resume it on changed boundary.

    `guard` must independently authenticate the disposable target, source,
    operation and current policy. `record` must durably publish a private intent
    before any signal. The caller owns reaping/retirement and post-fault evidence.
    No arbitrary timer chooses the fault boundary; timeout only bounds waiting.
    pidfd pins the leader against PID reuse. No host service is signalled here.
    """
    if boundary not in BOUNDARIES or type(timeout) not in (int, float) or not 0 < timeout <= 900:
        raise RuntimeError('fault_scope_or_budget_invalid')
    if not all(callable(x) for x in (observe, guard, record)):
        raise RuntimeError('fault_independent_observers_required')
    deadline = clock()+timeout
    def require_budget():
        if clock() >= deadline:
            raise RuntimeError('fault_boundary_deadline_expired')
    guard()
    require_budget()
    if process_identity(pid) != expected or expected[2] != pid:
        raise RuntimeError('fault_process_identity_changed')
    fd = os.pidfd_open(pid)
    stopped = False
    killed = False
    try:
        if process_identity(pid) != expected:
            raise RuntimeError('fault_process_identity_changed')
        while True:
            guard()
            require_budget()
            if process_identity(pid) != expected:
                raise RuntimeError('fault_process_identity_changed')
            observation = observe()
            require_budget()
            if matches(boundary, observation):
                break
            if clock() >= deadline:
                raise RuntimeError('fault_boundary_not_observed')
            time.sleep(min(.05, max(0, deadline-clock())))
        record('stop_intent', {'boundary': boundary, 'pid': pid, 'start_ticks': expected[0]})
        guard()
        require_budget()
        signal.pidfd_send_signal(fd, signal.SIGSTOP)
        stopped = True
        stop_deadline = clock()+2
        while True:
            if select.select([fd], [], [], 0)[0]:
                raise RuntimeError('fault_target_exited_before_stop')
            state = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()[0]
            if state == 'T':
                break
            if clock() >= stop_deadline:
                raise RuntimeError('fault_target_stop_not_observed')
            time.sleep(.005)
        # The pinned stopped leader cannot exit/reuse its PID before group stop.
        if process_identity(pid) != expected:
            raise RuntimeError('fault_process_identity_changed')
        os.killpg(pid, signal.SIGSTOP)
        guard()
        frozen = observe()
        require_budget()
        if not matches(boundary, frozen):
            raise RuntimeError('fault_boundary_changed_while_stopping')
        record('kill_intent', {'boundary': boundary, 'observation': frozen})
        guard()
        require_budget()
        os.killpg(pid, signal.SIGKILL)
        killed = True
        if not select.select([fd], [], [], 5)[0]:
            raise RuntimeError('fault_target_exit_not_observed')
        record('leader_exited', {'boundary': boundary, 'pid': pid})
        return frozen
    finally:
        if stopped and not killed:
            # Never leave a harmless failed test's exact live group frozen.
            # Do not signal a recycled PID; the original pidfd must still be live.
            if not select.select([fd], [], [], 0)[0]:
                os.killpg(pid, signal.SIGCONT)
        os.close(fd)
