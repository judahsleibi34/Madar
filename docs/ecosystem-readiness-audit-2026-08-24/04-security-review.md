# Security review

## Result

No Critical cross-tenant, authentication bypass, remote-code execution, SQL injection, or tracked-secret exposure was demonstrated. Six High findings still block launch, three of them security/commercial-integrity related: public quiz answers, admin MFA login fail-open, and permissive entitlement fallback.

## Effective controls

- Auth tokens are HttpOnly cookies; production cookies are Secure and SameSite-configured (`services/auth_service.py:240-264`).
- Signed CSRF tokens are tied to session material; unsafe API requests receive CSRF and exact-origin checks.
- CORS is added as the outermost effective middleware (`app.py:274-286`). Safe external 404 probes showed CORS for `https://madarportal.com` and no `Access-Control-Allow-Origin` for an untrusted origin.
- Frontend CSP excludes unsafe-eval, objects and framing; HSTS, `nosniff`, COOP, referrer and permissions policies are present. The repository edge audit passed against loopback production.
- Rate limiting uses Redis, defaults fail-closed in production, trusts only loopback proxy addresses, and uses user/tenant/IP dimensions.
- Builder rejects raw HTML/script/iframe blocks. React rendering did not reveal a general unsafe HTML sink in the public runtime.
- Remote ingestion resolves and revalidates destinations, constrains protocols/size/time and isolates parsing from network and secrets.
- Containers run non-root with all capabilities dropped, no-new-privileges, read-only roots, PID/memory/CPU limits, bounded tmpfs and rotated JSON logs.

## Secret and supply-chain checks

Tracked source and practical 399-commit history searches for private-key headers, common cloud/API key formats and credential-bearing PostgreSQL URLs returned no matches. Raw secret values were never printed. Production/dev `.env` files are ignored and mode `0600`. Runtime services explicitly clear the direct PostgreSQL URL.

Frontend `npm audit --omit=dev` found zero vulnerabilities. Backend `pip check` found no broken requirements; the repository enforces exact Python constraints. An ephemeral `pip-audit` run emitted no advisory finding, but scanner/tool output was not retained as an artifact, so treat that as limited evidence. The prototype mobile dependency tree reports 16 advisories (5 High, 11 Moderate), mainly Metro `image-size` DoS and an old `uuid` build path; practical exposure is currently build-time because the mobile app is unreleased.

## OWASP-oriented assessment

- SQL injection: queries use Supabase builders or static PL/pgSQL; no user-string SQL execution found.
- IDOR/BOLA: significant routes reassert tenant ID on reads and writes. Live integrity checks found no mismatched binding. Authenticated adversarial E2E was not executed.
- SSRF: remote datasets and push endpoints validate scheme, DNS/IP and redirects; separate workers reduce blast radius.
- Uploads/path traversal: random server names, confined paths, MIME/extension/signature checks and archive limits are present. No SVG is accepted.
- XSS: builder unsafe block types are rejected and React escapes text. Tenant-provided external image/media URLs remain intentionally permitted under CSP `https:`.
- Host-header attacks: public resolution uses Host/X-Forwarded-Host/Origin as routing evidence. Exact database resolution and ambiguity rejection limit content confusion, but trusted-proxy enforcement at the edge could not be independently verified from root-only Cloudflare config.
- Availability: Redis has no maxmemory policy, workers can be false-green, public analytics/form endpoints remain spam targets within fixed rate windows, and repeated deploy builds materially consumed cache.

## Required fixes

Close `MADAR-FORM-001`, `MADAR-AUTH-001`, `MADAR-AUTH-002`, `MADAR-BILL-001`, and infrastructure findings in the master register. Add authenticated two-tenant security E2E to a disposable database before reassessing G4/G5.
