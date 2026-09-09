"""Bounded process counters; no tenant, receipt, notes, or credentials as labels."""
from collections import Counter
from threading import Lock

_lock = Lock()
_counts = Counter()
_ALLOWED = frozenset({'resolution_failure', 'capability_denial', 'command_success', 'command_failure'})


def record_commercial_metric(outcome: str) -> None:
    if outcome not in _ALLOWED:
        return
    with _lock:
        _counts[outcome] += 1


def commercial_metric_snapshot() -> dict[str, int]:
    with _lock:
        return {f'commercial_{name}_total': _counts[name] for name in sorted(_ALLOWED)}
