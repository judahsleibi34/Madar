# Data preservation and provider compatibility

No historical migration changed.147 and148 are exactly the PR210 SQL/mirrors,
ordered by the new combined manifest.147 SHA256
bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3;
148 a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096.
Existing release.json and old bridge/manifest files remain unchanged.

The new FENCED coordinator snapshot includes every public, auth and storage table,
including sessions, refresh/MFA-related state and extra storage metadata. It
compares original-column roots so the new claim_generation column is not mistaken
for lost historical data. Only application_schema_state may change. Historical
profiles retain their exact earlier five-table identity/storage contract. Native
root snapshot tests verify this distinction and detect unexpected auth changes.
No rows or password hashes are emitted in public reports.

The independent restore verifies177 table roots,21 sequences,8 stored object bytes,
all role attributes/passwords/memberships plus object owners/grants/RLS/definer
settings in a genuinely fresh PG cluster. Original password/AuthID/TOTP/private
object works after restore; anonymous object access is denied. A fresh account
also completes login/MFA/CSRF/refresh/storage/native worker acceptance.22 native
business tests execute in the restored database namespace.

These are synthetic data preservation proofs. Supabase-compatible Auth, SDK,
PostgREST and Storage remain required and present; this is not a provider cutover.
Production customer-data rehearsal/privacy approval/current-data roots and
current backup/replica evidence remain BLOCKED. Never copy live customer secrets
into this ordinary staging stack to satisfy that gate.

The new all-Auth/Storage comparison is deliberately strict. Legitimate provider
session/audit/metadata activity during the maintenance interval can fail it even
when SQL did not corrupt data. Production preparation must prove an approved
Auth/Storage writer/ingress quiescence scope or independently review an explicit
volatility-aware preservation contract before execution. Notification-worker
quiescence alone does not prove provider quiescence. No provider was stopped and
no mismatch allowance was added here; unexpected root changes keep the release
blocked/READ_ONLY. This is an additional current-data admission/rehearsal limit.
