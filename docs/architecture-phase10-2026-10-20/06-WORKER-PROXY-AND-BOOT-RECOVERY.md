# Worker, proxy and boot activation — incomplete

Current-source worker protocols remain strict delivery2/outbox2/deletion2 at150.
Published SQL is unchanged. Fresh native provider acceptance proves actual worker
consumption,synthetic user/tenant deletion and restart separately from the upgrade.

The full operation still must connect accepted candidate/worker ownership after
independent target authority,verify consumption and readiness,activate the accepted
proxy route and clear the persistent boot barrier last. Actual root boot recovery
must retain restrictions at147/148/149/150 and never restart incompatible workers,
replay SQL or reuse consumed approval. That combined path is not executed here.

The new root lock windows serialize existing coordinator root stages; the native
executor process exits verify PostgreSQL commit observation and advisory-lock
release. They do not verify systemd/Docker restart,proxy handoff or host reboot.
The retained guest is inspected only. No current-source reboot PASS is claimed.
