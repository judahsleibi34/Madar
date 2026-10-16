# Sanitized execution evidence

Only synthetic aggregate results are committed. Credentials, TOTP seeds, cookies,
full SQL query text, archives and fixture files remain private on staging.

- performance-initial.json: original0.75CPU PostgreSQL/0.5CPU Auth comparison.
- performance-db1cpu.json: clean1CPU database comparison/count-query experiment.
- performance-db2cpu-count-experiment.json:2CPU database/count-query experiment.
- performance-final.json and performance-final-repeat.json: restored baseline admin
  implementation, app candidate27860bf2; same-stack paired measurements, zero errors.
- native-smoke.txt, tenant-smoke.txt, worker-recovery.txt, redis-failure.txt:
  final native assertion summaries at27860bf2.
- restore-result.json: final component restore (177 tables/21 sequences/four objects/
  three MFA factors) with archive hashes and independent synthetic destination names.
- browser-smoke.json: final real Chromium TLS portal/MFA/cookie/mobile assertions.

Private full-log SHA256 values, retained under
`/home/staging-admin/architecture-hardening-20261016/`:

| Log | SHA256 |
| --- | --- |
| final-tests.log |83eebf4a274fca9a972c3ab0833d12697e3f90b10de8c9189c943c61f9951110 |
| final-sql115.log |c144bcf8311de234b1b8ea9ffc721b336ef91b7bffcc45e2279f4b4b12121b39 |
| final-sql145.log |3c349f54ed8fc63ce3825d39571806bb1bf65a20f4b7e750d0e661996e77bd99 |
| final-sql146.log |45f88527959f33ba62efab1324efeb4f29a1e001a19171ffe72c222518dc1135 |

Hashes identify retained logs; they are not protected production acceptance or
independent attestations. The discarded CI-overlap benchmark is not included as
acceptance evidence. Old failed attempts remain private diagnostic evidence.

- staging-final-status.json: final source/image provenance, ready:true and nine
  running owned services after metadata-only rebuild0c591b8f.

- notification-stale-ack.json: confirmed pre-existing native ownership invariant
  FAIL; fixture transaction rolled back and staging worker resumed.
