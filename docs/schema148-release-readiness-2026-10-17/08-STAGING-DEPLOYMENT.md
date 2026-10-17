# Retained native environments and reproducibility

Use `ssh -F /home/madar/.ssh/config madar-staging`; preserve SSH ownership controls.
Host4vCPU/5402MiB, HDD-backed VM. Original project madar-hardening-20261016 and
independent restored project madar-independent-recovery-20261017-attempt3 have
separate DB clusters, networks, queues, object volumes, secrets and ports.
Unrelated madar-staging-data remains untouched. Administrative/provider listeners
are loopback-only. Services have explicit memory/CPU/PID/log bounds and restart=no.

Original stack exposes18080/18443 application,18081 provider. Restore exposes
19080/19443 application,19081 provider. Internal native providers are PG17,
GoTrue2.196, PostgREST14.17, Storage1.74, Redis; no production credential/data used.
The original marker146 identifies fixture ownership, not current schema148.

`manage.py` defaults inspection and requires exact dedicated host, owner and marker.
`independent_recovery.py INSPECT` inspects; `REHEARSE --attempt 1|2|3` creates only
an unused bounded owned target. Attempts1/2 failed and were stopped; archives and
volumes preserved. Attempt3 passed and is retained for review. Private VM runtime
files contain generated synthetic secrets and must not be committed.

Fresh image acceptance uses `fresh_artifact_acceptance.py INSPECT|REHEARSE
--artifacts <private-home-directory> --source-sha <exact-CI-SHA> --attempt 3`.
Only the restored stack is replaced; production and original baseline are not.
The accepted frontend serves its own compiled files/Nginx behind the loopback
TLS utility. Native application smoke is mandatory after import/startup. Source
overlay, fresh CI image, accepted application evidence and privileged release
admission are distinct evidence categories.

Recovery/teardown: inspect owner.json and exact Compose resources first, preserve
private archives/evidence, stop only the exact owned project with its files.
Never use broad prune/down-volume operations. The retained project is useful
review state; no automatic teardown of unrelated data is provided.

The first fresh import refused a config/manifest ID mismatch before service
replacement. The second import accepted exact c3 image IDs, then the loopback TLS
utility failed on read-only fastcgi/uwsgi/scgi temp directories. The source now
uses existing bounded tmpfs paths. An explicit REHEARSE --resume-imported checks
the already selected exact source, owned148 DB, authenticated archive, retained
archive hashes and imported image identities before repeating only synthetic
staging startup/acceptance. This is not an automatic privileged-production retry
or a mechanism to resume a consumed production approval. Wrong selected source
refuses before Compose. The repaired c3 native smoke/browser passes.

The later32c77afd application image includes the newly confirmed send-counter fix;
it requires its own final acceptance evidence for the worker. The original retained
4f stack remains separate. Image archive loading is slow on this HDD-backed VM;
no application latency inference is made from Docker import duration.

Final retained restore source32c77afd01a012c7d21240316d4a46e52c3cbf14,
actual schema148, ten services including the exact compiled production frontend.
Fresh acceptance202.336s PASS, no explicit resume. Original identity/native tenant
read+write/disabled membership and final browser checks also pass. The original
nine-service4f source stack remains healthy/separate; no production operation.
