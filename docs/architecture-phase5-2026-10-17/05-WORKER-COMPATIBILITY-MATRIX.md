# Actor and protocol boundaries

| Schema | Delivery | Outbox | Deletion successor worker |
| --- | --- | --- | --- |
|146|Legacy origin|Legacy origin|New worker refuses incomplete ownership protocol|
|147|Protocol2 required;legacy denied|Legacy unresolved|Held|
|148|Protocol2|Known stale-owner defect|Held;direct cancellation incompatible|
|149|Protocol2|Protocol2;legacy denied|Held pending separate complete ownership successor|

Version6 inventory verifies notification/deletion/calendar roles, exact images,
specifications, no running/restarting workers and restart=no; unknown/missing
actors reject. Host-process inspection covers manual/docker-exec worker commands
and requires a positive visible process/cgroup identity. These are source gates,
not a complete live production supervisor inventory. Provider/ingress/object
writers are separately fenced. Native actual149 has notification worker active
and deletion worker stopped; full production calendar/deletion activation is not
accepted. No legacy RPC fallback is supplied.
