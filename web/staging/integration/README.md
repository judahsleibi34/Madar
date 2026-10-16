# Dedicated native integration staging

This separate harness runs **only on `madar-staging`** and never reads production
environment files. It uses native GoTrue, PostgREST and Storage with PostgreSQL17,
Redis and the candidate API/notification worker. It is distinct from the retained
schema81/83 synthetic gateway harness in `web/staging`.

Copy the tracked committed source to the VM. Import the exact images named in
`compose.yaml`, plus the Dockerfile base application image, if the VM remains
offline. Exporting immutable images from another host is read-only; do not copy
container writable layers, production volumes or environment files.

Run as `staging-admin` from that source tree:

```bash
python3 web/staging/integration/manage.py prepare --source-sha <exact-40-character-commit>
python3 web/staging/integration/manage.py up
python3 web/staging/integration/manage.py schema
python3 web/staging/integration/manage.py status
```

Capture the SHA using `git rev-parse HEAD` at the source before transferring it.
The private runtime is `~/madar-hardening-20261016`, with generated credentials,
database marker and ownership record. Never put it in Git. `prepare` refuses an
existing runtime. Native provider ports publish only at127.0.0.1:18081; PostgreSQL
and Redis have no published ports. Every service uses the isolated internal
network and bounded resources/logs. Auto-confirmed synthetic email identities
are staging fixtures; external email, push, OAuth, payments and AI are disabled.
The source-overlay Dockerfile verifies dependency constraints and `pip check`;
it does not replace the regular fresh locked CI build.

`schema` accepts only a fresh marked owned database and rehearses immutable
history to146 via the selected learning143 branch, excluding142. It refuses a
second initialization. Existing shared staging databases are never selected.
Do not use this command for production migrations or claim it grants production
migration/release authority. Private Docker errors can contain generated staging
credentials: inspect them on the VM and sanitize evidence before sharing.

Stop only the owned project, preserving named volumes and credentials:

```bash
python3 web/staging/integration/manage.py down
```

The harness checks labels before teardown and rejects unowned resources. There
is deliberately no broad cleanup or automatic volume deletion command. Full
production parity additionally requires external delivery, OAuth, all workers,
durable application filesystem mounts, TLS/edge routing and governed release
acceptance; those are not implied by successful startup.
