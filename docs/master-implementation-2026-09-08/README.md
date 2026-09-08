# Master implementation work record — 2026-09-08

**Master implementation complete: NO. Authorized production scope ready: NO.**
This change fixes request/session assurance and temporal entitlement defects and
adds a guarded, pinned Supabase rehearsal preparer. It does not deliver the
requested cash ledger, transactional commerce completion, CyberSource provider,
or general bidirectional sync subsystem. It must remain a draft until required
implementation and release gates are complete.

## Implemented and verified

- Privileged AAL2 checks consume the current request's remotely verified Auth
  token and subject, with expiry checks. They no longer authorize from a shared
  SDK client's cached session. MFA operations use isolated request clients.
- Entitlement periods use timezone-aware half-open bounds. Expired, future,
  malformed and inverted periods deny; trial/grace without an end deny. Unknown
  base plans cannot acquire add-on capabilities, and unknown capabilities deny.
  Existing unbounded legacy active rows remain an explicitly unresolved legacy
  case; no records were granted or changed.
- Existing commerce tables are included in the production RLS/grant verifier.
- The isolated preparer reads only tracked blobs of the exact official Supabase
  commit, pins image digests, rejects unsafe targets/mounts and generates private
  synthetic credentials. Ports bind loopback and inherited provider secrets are
  excluded. It prepares and validates; it never starts a stack or changes production.

The actual nine-service rehearsal on Node 2 passed all existing 93 migrations,
RLS/grants, opaque publishable/secret keys, ES256/JWKS, TOTP/AAL2, refresh, private
Storage signed URLs, and a synthetic S3/rclone copy with download/SHA-256 checks.
This is not full managed-source parity, physical PITR or a cutover rehearsal.

## Validation

| Gate | Result |
| --- | --- |
| Authoritative backend workflow | 1,322 tests passed; zero failures/errors; EXTERNAL_ATTEMPTS [] and EXTERNAL_SITES [] |
| Focused Auth/commercial regressions | 101 passed; rehearsal guards 8 passed |
| Actual SDK against synthetic Auth | 32 concurrent checks; AAL2 did not elevate the other AAL1 session; test users removed |
| Frontend | 141 files; 868 passed, 1 skipped; lint/build passed |
| E2E safety guard tests | Passed; authenticated browser E2E not run |
| Dependency locks / migration validators / secret hygiene | Passed |
| pip check / pip-audit 2.10.1 | Passed; 140 installed packages, zero known vulnerabilities, zero skipped |
| npm production dependency audit | Zero vulnerabilities |
| Live and isolated RLS verifier | Passed, including six existing commerce tables |
| Existing Node 1 backup round-trip | PASS; schema 93, 74 public tables, zero invalid indexes, 98 local files and 102 provider objects; temporary customer copies removed |
| Full Supabase platform recovery / physical PITR | Not proven |
| GitHub CI | Record exact PR head checks separately; local results do not attest GitHub |

Evidence: `/home/madar/master-implementation-20260908`. Logs preserve initial
harness errors and the S3 internal-host signature failure alongside successful
corrected runs. No failed gate has been waived. The restored backup was the
existing `madar-20260908T021811Z`; a new post-release backup has not been created
because no production release or schema change occurred.

## Release blockers and required unfinished work

- No e-commerce plan mapping exists in the canonical catalog. Website pricing
  advertises reservations while canonical capabilities reserve them for Business
  Plus. Product decisions are required; the matrix was not invented.
- Live tenant commercial decisions are incomplete: twelve tenants, no approved
  entitlement decisions and no entitlement-bearing subscriptions. Global
  enforcement remains disabled; usage is not evidence of payment or a grant.
- Node 1 `sudo -n true` still requires interactive authentication. Privileged
  SMART and host capacity acceptance remain blocked. Never use /srv/data1 or
  modify Mailcow's /srv/data2/docker.
- The full financial/domain/sync implementation and adversarial tests remain
  required. Existing cash-on-delivery ordering lacks atomic stock reservation
  and durable checkout idempotency; it has not been repaired by this patch.
- Complete migration parity/CDC/sequence tooling, managed Storage/Auth parity,
  physical backup/PITR, true future off-host topology, safe application E2E and
  exact release acceptance are still required.

No live CyberSource processing, real customer DB connection, production database
cutover, production configuration change, manual grant, payment or proxy change
was performed. No complete platform recovery or offline/immutable layer is claimed.

## Documents

- [Architecture/gap matrix](architecture-gap-matrix.md)
- [Canonical machine-readable plan matrix](plan-capability-matrix.json)
- [Threat model and required regression mapping](security-threat-model.md)
- [Official external research](external-research.md)
- [Exact self-host image lock](selfhost-versions.json)
- [Future cutover runbook and remaining gates](october-cutover-runbook.md)
