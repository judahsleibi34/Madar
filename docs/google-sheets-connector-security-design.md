# Google Sheets connector security design

Status: unselected C3 Step 5 source candidate. This design does not enable the
provider, select migration 161, contact Google, or authorize a deployment.

## Boundary and scope

The connector is read-only and requests only
`https://www.googleapis.com/auth/spreadsheets.readonly`. That Google scope can
read every spreadsheet accessible to the authorizing Google account. Madar
therefore applies a narrower, durable source configuration containing exactly
one spreadsheet ID and one numeric sheet ID. Browser-supplied URLs are parsed
only to extract those identifiers and are never fetched.

Google Sheets is available only when an operator explicitly enables it and all
server-side configuration is valid. Its approved network destinations are the
Google authorization endpoint, the Google token endpoint, and the Sheets API
host. The browser cannot choose an endpoint, method, header, or scope.

## Authorization callback, state, and PKCE

The server creates a 256-bit random state nonce and PKCE verifier for each
authorization attempt. It stores only the SHA-256 digest of the complete signed state in the
database with the authenticated tenant, project, source, user, provider, exact
redirect URI, expiry, and an unused marker. The signed state value returned to
the browser contains only the random nonce and a version. It contains no token,
client secret, PKCE verifier, spreadsheet metadata, or customer data.

The PKCE verifier is encrypted with the same Vault-backed source credential
boundary used by other Data Sources. A callback must:

1. use the exact configured HTTPS redirect URI;
2. authenticate the current Madar session;
3. hash the returned state and atomically consume one unexpired transaction;
4. recheck the session user, active tenant membership, project, source, provider,
   source creator, and redirect URI against the consumed transaction;
5. exchange the code using the stored PKCE verifier and server-side client
   secret at Google's fixed token endpoint; and
6. validate the returned scope before activating the source credential.

Consumption is one-time and precedes exchange, so replay and concurrent callback
attempts fail closed. Denials also consume state. State and authorization codes
are never logged or reflected in redirect query strings.

## Credential lifecycle

The OAuth client ID and client secret come only from server configuration. The
client secret is never stored in source rows or returned to the browser. Madar
stores the Google refresh token as a compact JSON credential with credential
type `oauth_refresh` through the existing schema-155 Vault Transit envelope.
The associated-data binding includes environment, tenant, project, source,
provider, credential ID, and version. The short-lived access token is obtained
when needed and held only in process memory.

Background refresh calls use only Google's fixed token endpoint. A rotated or
revoked source credential is detected by the existing credential revision
revalidator, and the final incremental commit remains fenced by the exact
credential revision. Invalid-grant and insufficient-scope failures place the
schedule into credential-attention state without advancing a snapshot or Madar
revision. Disconnect uses the existing source credential revocation lifecycle;
remote Google revocation is best effort and does not weaken local revocation.

Calendar credentials are not read, copied, or silently reused.

## Sheets reads and snapshot safety

Metadata and values are read only from `sheets.googleapis.com` through fixed
Google Sheets API v4 paths. The adapter enforces configured row, column, byte,
page, and elapsed-time bounds. It identifies a resource by spreadsheet ID plus
numeric sheet ID and identifies business records only through the configured
unique, nonblank record-ID column.

Google Sheets does not expose an event cursor or an atomic multi-range snapshot
for this workflow. A successful bounded scan therefore produces a Madar snapshot
fingerprint, not a provider cursor. New and changed records are upserted by
content hash. Missing records are retained in this milestone: the connector does
not infer deletion from a scan that could have raced with edits or been partial.
This conservative behavior prevents mass deletion after truncation, permission
failure, header drift, timeout, or concurrent edits. Full deletion reconciliation
requires a separately reviewed consistency design.

## Schema and release boundary

The existing credential tables can safely hold the source-scoped refresh token;
no new secret store is required. Additive migration 161 is required only for:

- one-time OAuth transaction metadata and encrypted PKCE credential reference;
- the selected spreadsheet/tab/header/column/record-ID mapping; and
- the last validated snapshot fingerprint used for diagnostics and no-op checks.

Both tables are service-role-only with tenant/project/source foreign keys. The
migration requires and locks exact schema 156 before DDL. It remains absent from
the active schema-146 release and cannot be applied or selected by this change.

## Operator configuration

Required settings are `GOOGLE_SHEETS_PROVIDER_ENABLED`,
`GOOGLE_SHEETS_CLIENT_ID`, `GOOGLE_SHEETS_CLIENT_SECRET`, and
`GOOGLE_SHEETS_REDIRECT_URI`. The redirect must be an exact HTTPS URL except for
an explicitly test-only loopback fixture. Provider availability fails closed if
any setting is absent or invalid. Real activation additionally requires Google
Cloud consent-screen configuration, exact redirect registration, staging OAuth
authorization, quota monitoring, egress controls, and a release review.

## Stop-gate conclusion

The reviewed C2 Vault, credential revision, C3 scheduler, ingestion, immutable
history, and checkpoint contracts can support this connector without a major
authentication redesign. The implementation may proceed within the bounded
schema-161 and provider-specific adapter described above.
