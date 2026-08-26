# Auto-deploy retry-storm fix

Tracked auto-deploy code resolves an exact remote SHA, requires initialized known-good state, rejects dirty production source, checks ancestry, delegates to the immutable controller, and suppresses a recorded failed SHA until explicit manual retry/backoff expiry.

The legacy `/home/madar/docker_auto.sh` implementation was backed up and replaced with a compatibility entrypoint that only delegates to the installed user-local immutable controller. It contains no Compose rebuild/recreate or Git reset path.

The root-owned service/timer definitions remain old because non-interactive root authorization is unavailable. A safe no-op execution was not performed because the execution safety layer rejected invoking a production entrypoint that could deploy. Therefore:

- timer remains **inactive**;
- future automatic deployment remains **disabled**;
- a root operator must install the tracked control-plane units, remove the legacy privileged drop-in, daemon-reload, verify a no-op, and only then enable the timer.

The tracked timer uses `OnUnitInactiveSec`, avoiding immediate overlap/retry timing.
