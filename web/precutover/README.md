# Local Supabase pre-cutover candidate

These overlays are opt-in preparation. They do not deploy, promote, execute SQL
migrations, or change the active release. Keep core schema 115. Do not invoke the
current release controller's automatic migration policy: its manifest includes
116. Candidate source remains a forward descendant of the serving release.

## Internal client bridge

Create `madar-supabase-client` with `docker network create --internal`.
Supabase's gateway joins this network with alias `madar-supabase`; the backend
and three queue workers join alongside their existing networks. Parser and
remote-ingestion isolation is preserved. Only the gateway joins the client
bridge; database, Auth, REST and Storage remain on the Supabase service bridge.
The client URL is `http://madar-supabase:8000`. Configure keys through protected
server environments. There are no additional published ports; retain all local
Supabase host bindings on 127.0.0.1. Compose `external` cannot attest network
isolation: an operator must verify `docker network inspect` reports Internal=true
before using these overlays. Never attach live applications during rehearsal.

The application overlay combines with `web/docker-compose.yml` and release
network settings. The gateway overlay combines with the two local Supabase
Compose files. Persistence requires including overlays in future authorized
startup commands; the current controller does not automatically load these.
Any controller integration is separately reviewed under production release policy.

## Browser delivery

`GET/HEAD /assets/avatars/{path}` serves only the public avatars bucket and only
raster image MIME types. Avatar writes generate URLs under PUBLIC_API_URL,
otherwise `/api` for same-origin development. Existing source URLs require a
guarded target-only data rewrite, not a schema migration. Ownership and object
paths are unchanged. Cleanup accepts both legacy and mediated avatar paths and
still requires the authenticated owner's UUID prefix.

Builder assets keep the existing visibility RPC, publication filters, and
same-tenant private preview checks. Storage fallback streams bytes instead of
redirecting. Range, If-Range, If-None-Match, If-Modified-Since and storage response
MIME/length/range/ETag/Last-Modified are retained. Provider errors and redirects
are never relayed; private previews use no-store. Local files and responsive
image behavior retain their existing paths. Service keys remain server-side.

## Auth and mail

The prepared Auth overlay pins canonical HTTPS SITE_URL and exactly two
ADDITIONAL_REDIRECT_URLS: `/verify-email` and `/reset-password` on
`https://madarportal.com`. All mail action paths use `/auth/v1/verify` on
`https://api.madarportal.com`. API_EXTERNAL_URL is already the complete Auth
base; do not append `/auth/v1` twice. The API exposes only the verification
callback, never a general Supabase proxy. It permits expected action types and
exact canonical frontend destinations, including the existing recovery request
nonce, rejects duplicate parameters and open redirects, suppresses upstream
error bodies and caches, and does not log credentials. Native Auth permits the
SITE_URL host (including the recovery query); the API independently constrains
callback paths. See https://github.com/supabase/auth/blob/master/README.md.

SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_ADMIN_EMAIL and SMTP_SENDER_NAME
must be supplied by the operator through protected configuration. No SMTP values
are supplied or invented. This overlay was not activated. Deliverability,
existing-user password login/logout, verification/recovery emails, and real MFA
remain interactive approval gates. Existing AAL2 policy is unchanged.

## Local rollback

Use a verified full local database checkpoint and complete native Storage copy,
including version suffixes, together with pinned Supabase component images and
the compatible candidate application image. A rollback runtime must keep this
same mediated asset interface and local Supabase credentials. The old hosted
runtime is not a valid rollback after local writes. Once cutover accepts writes,
prefer runtime-only rollback against the current local database/storage. Restoring
the pre-cutover checkpoint would discard later writes and requires a separate
reviewed recovery decision. Take a new verified checkpoint at the approved write
freeze. Never execute backup restoration against the live target in rehearsal.
