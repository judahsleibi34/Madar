# Inspected infrastructure and separation

All production commands were read-only. No shared cleanup, restart, installation,
network change, secret rotation, production data write or release action occurred.

| Host | Observed resources | Boundary |
| --- | --- | --- |
| madar-gpu | i5-14400F,16 logical CPUs,38928MiB RAM; roughly25GiB initially available; swap full | Primary production host, inspect only |
| madar-staging | Ubuntu26.04.1/kernel7.0.0-30,4vCPU,5402MiB RAM,72GiB root LV | Dedicated VM, synthetic integration allowed |
| madarserver / madar-node1 |4 CPUs,7335MiB RAM,915GiB HDD root and two1TB HDD data mounts | Read-only observation; unrelated backup/mail services preserved |

Primary `/home` is on SSD `sdb`; `/srv/madar-staging` is on rotational `sda`.
Read-only `virsh domblklist madar-staging` confirms VM image
`/srv/madar-staging/vm-images/madar-staging.qcow2`. VM performance is HDD-backed
and cannot be represented as SSD production behavior. RTX5060 had8151MiB VRAM,
about6050MiB used by existing workloads at observation; AI processes were untouched.
No HA, replication health or off-host recovery is inferred from host count.

Existing VM project `madar-staging-data` and its root-private secrets/backups
were preserved. Its PostgreSQL 17 and Redis have no database port publication.
SSH was the only externally listening TCP service at initial inspection; UFW
inactive. The VM has no default route/resolver: a fresh public-registry build
failed resolving auth.docker.io. The session did not change host/production
routing. Known immutable dependency images were transferred offline without
production volumes, container writable layers or environment files.

## New owned project

Project `madar-hardening-20261016`, owner label
`com.madar.staging.owner=architecture-hardening-20261016`. Private0700 runtime
`/home/staging-admin/madar-hardening-20261016`; environment0600. Generated JWT,
CSRF and database credentials exist only there. No production credentials/data
were used. Native email identities, MFA factors, objects and customer rows are
synthetic fixtures.

| Service | CPU cap | Memory cap |
| --- | ---: | ---: |
| PostgreSQL 17 |2 |768MiB |
| GoTrue |1 |192MiB |
| PostgREST |0.5 |128MiB |
| Storage |0.5 |256MiB |
| Backend |1.5 |1280MiB |
| Notification worker |0.5 |256MiB |
| Gateway / frontend (each) |0.25 |64MiB |
| Redis |0.25 |128MiB |

Caps bound individual consumers; their sum is not a reserved capacity promise.
All services have PID/log limits and no-new-privileges where configured. API,
worker and proxies run non-root/read-only with bounded tmpfs. Database/provider
images retain their required startup permissions. Redis maxmemory48MiB,
noeviction, persistence disabled; real durable work is PostgreSQL-backed.

Data/application services join only an internal project bridge. Proxies also
join a separately owned ingress bridge with IP masquerade disabled. Docker29
suppressed publications on internal-only containers, so this second bridge is
needed for loopback publication. Only127.0.0.1:18080,18443,18081 are published;
DB/Redis have none. Temporary baseline proxy18082 is removed after measurement.
TLS uses a generated seven-day self-signed identity, never production certificates.

Staging-only pg_stat_statements provides bounded aggregate query-cost evidence;
reports exclude SQL text, which can retain credential literals in utility queries.
CPU cgroup counters identify quota pressure. No new monitoring stack competes
with application memory. VM memory remained well below total during final
validation; point observations are not proof of absence of long-term growth.

## Production observations

Release state: active blue, known-good application
`b0fdfe049510724c06a04706390cd174ea57a1d1`, schema146. Checkout HEADc1d03ce3
is not the serving artifact. Protected controller `/opt/madar/control-plane/deployment`
was untouched. Auto-deploy timer was inactive and disabled, unchanged.
Production effective CSRF checks/MFA login enforcement/rate limiting enabled;
missing-origin bypass and rate-limit fail-open disabled; Secure cookies enabled.
Commercial enforcement false remains an explicit unresolved operator policy.
No production readiness statement follows from those few observations.
