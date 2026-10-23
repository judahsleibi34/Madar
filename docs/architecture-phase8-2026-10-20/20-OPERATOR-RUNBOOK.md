# Capability-separated operator toolkit

INSPECT/PREPARE:from a clean reviewed source checkout,discover exact committed
SQL and print the deterministic inventory/plan:

```text
python3 web/scripts/plan_migrations.py --source-sha <full-commit> \
  --history-base-sha <independently-verified-ancestor> --origin-schema <observed-schema>
```

`--inventory-only` emits inventory. Never guess the production origin from the
source tree. The output has no credentials and issues no authority. Current146
origin contains the existing coordinated147–150 chain,not an automatic routine
path. Unknown/historical SQL is not relabeled safe by generated metadata.

Source authoring:use `migration_risk.scaffold(origin,target,payload)` for the
future transactional envelope. Add both matching SQL mirrors. A narrow explicit
pg_catalog built-in-table subset can be A;other statements escalate. Compatibility
intent at the fixed `web/database/migration-intent.json` path must declare exact
runtime range,rolling behavior,delivery/outbox/deletion protocols and a minimum
risk class. This declaration is not evidence or authority and cannot reduce AST
risk. Protocol introduction/change requires coordinated review. Actual runtime
compatibility and grants must independently pass.

REHEARSE:only on verified dedicated staging or a disposable CI runner:

```text
timeout 10m bash web/scripts/rehearse_generic_migrations.sh
timeout 5m bash web/scripts/rehearse_maintenance_role_restore.sh
timeout 2m bash web/scripts/rehearse_migration_policy.sh
```

These create positively labeled networkless PostgreSQL containers with bounded
memory/CPU/PIDs/duration,tmpfs database data and no published ports. Creation,
inspection and cleanup use one fixed local Docker socket. Cleanup checks only
resources it created and exact labels. Existing services/volumes are untouched.
CI sets exact source/base identities for actual newly discovered routine SQL;
manual framework tests without those variables do not claim candidate staging.
Inspect `migration-native.json`:BLOCKED is not PASS or full-provider acceptance.

After an interrupted migration,observe schema through an independently verified
connection and inspect the retained attempt/journal;do not replay it. A committed
schema or lost reply requires explicit forward inspection,new operation evidence
and the existing protected authority. Do not restore an old backup over newer
data,change SQL checksums,mark history applied,reset queues or restart incompatible
workers. READ_ONLY/maintenance barriers must survive until protected acceptance.

EXECUTE:reserved for the existing protected controller and independent issuer.
Schema150 operational admission and generic production dispatch remain disabled.
No new helper is a privileged executor. Do not install a root policy or controller,
merge main,activate CI deployment,issue authority,change roles or run production
SQL based on this runbook without the separately required controlled process.

Status/diagnostics:source plan and typed drift observations are read-only.
Drift requires protected expected history/catalog evidence;it never learns or
repairs a missing baseline. Namespace-safe identity/catalog/marker queries are
mandatory. Private journals,role archives and credentials stay outside Git.
A policy_match or source-controlled PASS field never authorizes execution.
