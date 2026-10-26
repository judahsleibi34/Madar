# Google Sheets connector operator guide

The connector is an unselected schema161 candidate. These instructions prepare a
staging review; they do not authorize production activation.

## Google Cloud preparation

1. Create or select a dedicated Google Cloud project manually.
2. Enable Google Sheets API v4. Google documents API enablement and web OAuth
   client creation at <https://developers.google.com/identity/protocols/oauth2/web-server>.
3. Configure the OAuth consent screen and request only
   `https://www.googleapis.com/auth/spreadsheets.readonly`. The scope can read
   spreadsheets accessible to the authorizing account; Madar narrows use to the
   configured spreadsheet and tab.
4. Create a **Web application** OAuth client. Register the exact HTTPS callback
   URI exposed by Madar: `/data/oauth/google-sheets/callback`. Do not add wildcard
   redirects.
5. Keep the app in testing mode with explicit test users during staging. Review
   Google's publishing and verification requirements before any wider audience.
   Use a staging-only Google Cloud project: Google requires separate projects for
   testing and production. For an External app in Testing, add every staging
   account as a test user and expect non-basic-scope refresh grants to expire
   after seven days.
6. Store the client ID and secret in the approved server secret-delivery system,
   never in Git, frontend variables, Compose source, database rows, logs, support
   tickets, or chat.

## Madar configuration

Configure server-side values only:

- `GOOGLE_SHEETS_PROVIDER_ENABLED=true`
- `GOOGLE_SHEETS_CLIENT_ID`
- `GOOGLE_SHEETS_CLIENT_SECRET`
- `GOOGLE_SHEETS_REDIRECT_URI` (exact registered callback)
- `GOOGLE_SHEETS_STATE_KEY` (at least 32 random bytes, base64url encoded)

The provider remains absent from capabilities if any setting is missing or
invalid. Endpoint overrides are test-only loopback controls and must not appear in
staging or production. Schema157, schema155 Vault Transit, schema156 scheduling,
the private immutable bucket, and the existing worker controls must all pass their
own activation gates first.

## Staging acceptance

- Confirm state replay, altered state, wrong session, wrong tenant/project/source,
  expired state, denial, missing code, insufficient scope, and redirect mismatch
  all fail without exposing secrets.
- Confirm refresh-token ciphertext is bound to the exact source and that access
  tokens, authorization codes, PKCE verifiers, and refresh tokens are absent from
  HTTP responses, logs, audit metadata, ingestion lineage, and storage paths.
- Authorize a staging-only Google account; read a dedicated synthetic workbook;
  select a tab, validate a stable-ID column, ingest, schedule, update, reorder,
  insert, and revoke. Confirm revocation blocks the final commit and places the
  schedule in credential-attention state.
- Confirm no Google Drive browsing, cell writes, arbitrary URLs, custom headers,
  or provider-defined executable templates exist.
- Disconnect locally by revoking the active Madar credential. Revoke the Google
  grant as well when retiring the connection. Dataset history is retained under
  normal Madar retention policy; disconnect does not delete analytical history.

## Quotas and bounds

Google currently documents 300 read requests per minute per Cloud project and 60
per minute per user per project, recommends request payloads no larger than 2 MB,
returns 429 for quota exhaustion, and recommends truncated exponential backoff:
<https://developers.google.com/workspace/sheets/api/limits>.

Madar is more conservative: at most 10,000 rows, 128 selected columns, 1,000 rows
per values request, 10 provider pages, 4 MiB per Sheets response, three bounded
GET attempts, a 15-second ingestion budget, and an in-process Google request
cadence of at most one request per second. The minimum schedule interval is 15
minutes. The process-local limiter is not a distributed quota coordinator, so
multi-worker staging must keep provider concurrency conservative. These are
safety bounds, not a scalability claim. Operators must
monitor request rate, 429s, timeouts, credential-attention status, ingestion
failures, worker lease expiry, checkpoint lag, and Google quota changes.

## Rotation and incident response

Rotate the Google OAuth client secret through the server secret system and restart
the relevant backend/worker processes under the ordinary deployment procedure.
Rotating the HMAC state key invalidates outstanding authorization attempts and
must be coordinated. Reauthorizing a source creates a new Vault credential version
and fences the previous version. Never edit credential ciphertext or source
revisions directly.

On suspected exposure, disable the provider, revoke the OAuth client or affected
Google grants, revoke Madar source credentials, stop due synchronization through
the governed worker controls, retain secret-free audit evidence, rotate affected
keys, and repeat staging acceptance before reactivation.

## Snapshot limitation

Google Sheets does not provide the connector with a transactional multi-range
snapshot or event cursor. Madar fingerprints complete bounded scans and imports
only changed content. It intentionally retains records absent from later scans;
partial reads, authorization errors, header drift, timeouts, and concurrent edits
therefore cannot mass-delete data. Full deletion support needs a separately
reviewed consistency protocol.
