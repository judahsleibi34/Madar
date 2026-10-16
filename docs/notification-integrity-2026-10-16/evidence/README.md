# Sanitized evidence

All results concern synthetic data. No passwords, JWTs, TOTP secrets, cookies,
customer records, environment files or archives are committed.

- test-summary.json: executed counts/times and hosted check identity.
- native-upgrade148.json: source 146→148 preservation,176 tables/21 sequences,
  private backup SHA256; basename identifies a private archive, not its contents.
- native-smoke148.txt: real Auth/MFA/Storage/intent/worker/proxy assertions.
- native-recovery148.txt: protocol 2 lease/reclaim/four-outcome denial and retry.
- native-final-status.json: actual source/schema/bounds/readiness/worker status,
  real PostgREST legacy/direct-write 403 and successful fenced delivery.
- native-restore148.json: actual independent same-cluster component restore hashes,
 177 tables/21 sequences/six objects/four MFA factors and limitations.

Private full logs retained on madar-staging under
`/home/staging-admin/notification-fencing-20261016/`:

| Log | SHA256 |
| --- | --- |
|backend-committed9c.log |560255e81b9aac501f08d387bdbf6fdd94a42708d880427db7eec1b2cfa27899 |
|native-committed9c.log |de2bf55a1b396eed90b1508f461025b671ad92c21d1287d3b4f377b6dc5bb02f |

[Hosted backend run 38927327897](https://github.com/judahsleibi34/Madar/actions/runs/38927327897)
passed fresh locked build, full suite, dependency consistency and all SQL stages.
Hashes/results are development evidence, never protected production authorization.
