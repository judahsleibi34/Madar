# Madar canonical tenant hosting architecture

For current operator procedures and monitoring, see [Hosted Tenant Domains Operations Runbook](hosted-tenant-domains-operations-runbook.md).

## Status and scope

Schema 105 makes `website_settings.subdomain` the canonical Madar-hosted tenant identity. The public URL is `https://{tenant}.madarportal.com`; `standard_path_slug` remains only a legacy path alias. Customer-owned domains are not implemented.

## Resolution and isolation contract

The frontend classifies the browser hostname before platform routing. A valid tenant host has exactly one DNS label before the configured `VITE_PUBLIC_SITE_DOMAIN`, is lowercased, is at most 63 characters, matches the DNS-label grammar, and is not reserved. Tenant hosts render `/`, page routes, `/shop/**`, and `/forms/{formId}` without changing browser history. The reserved-label contract is necessarily duplicated at the JavaScript, Python, and SQL language boundaries: frontend hostname tests enumerate the client behavior, while backend tests verify every authoritative Python label is present in migration 105.

Same-origin `/api/**` requests are proxied by the frontend Nginx service to the backend. Nginx removes the `/api` prefix, derives `Host`/`X-Forwarded-Host` from the verified public request host, preserves an exact `http`/`https` forwarded scheme and request ID from the release proxy, and maintains the forwarding chain plus real peer IP. It is not an arbitrary upstream proxy.

The backend validates `PUBLIC_SITE_DOMAIN`, parses `Host`, consults `X-Forwarded-Host` only from a trusted immediate proxy, and rejects malformed or ambiguous public-domain hosts. On a tenant host, every `/public/sites/{identifier}` route requires the path identifier to equal the host tenant. Resolution selects at most two settings rows by canonical `subdomain` and fails closed unless exactly one active tenant/site is found. A tenant host never falls back to `standard_path_slug`. Cache and ETag boundaries retain hostname, tenant/site, project, publication version, and schema identity.

Reserved labels are the synchronized application/database contract: `admin`, `api`, `app`, `auth`, `billing`, `cdn`, `dashboard`, `forms`, `health`, `login`, `logout`, `mail`, `pricing`, `privacy-policy`, `public`, `signup`, `site`, `static`, `terms-and-conditions`, and `www`.

## Database identity and migration 105

Migration 105 locks `website_settings` against concurrent identity writes and validates before mutation. Existing valid nonreserved subdomains are preserved apart from lowercase/outer-whitespace canonicalization, even when the legacy path slug differs. Missing/blank subdomains are backfilled from a valid, nonreserved `standard_path_slug`.

The migration aborts with row/tenant evidence for invalid or reserved identities, duplicate normalized subdomains, or backfill collisions. It never generates a replacement. It enforces non-null normalized DNS labels, a validated check constraint, a case-insensitive unique index, and a normalizing trigger. It does not drop legacy or commercial-history columns.

## Legacy compatibility

Main-host `/site/{legacy}/**`, `/forms/{legacy}/{formId}`, and `/store/{legacy}/**` are compatibility entry points. The browser first calls the authoritative public bootstrap resolver to validate the legacy identifier and obtain the row's canonical `subdomain`; only then does it replace location with the configured canonical tenant origin. Query strings and browser-visible fragments are retained. Invalid or ambiguous identifiers never become hostnames. Canonical tenant hosts do not run this redirect flow.

The compatibility path remains during rollout. Historical hostname aliases are not created when a tenant renames its subdomain.

## Entitlements, cookies, origins, PWA, and SEO

A Madar tenant subdomain is the normal hosted address. Configuring it requires the standard hosted-website or public-form-link capability. Website publication separately requires `website_publish`, so forms-only plans do not gain website publishing. The historical `branded_madar_subdomain` entry is deprecated and is not consulted by routing or settings updates.

Authentication, refresh, CSRF, session-activity, MFA, and account-access cookies remain host-only; no cookie sets `Domain=.madarportal.com`. Existing `HttpOnly`, `Secure`, `SameSite`, CSRF, and AAL2 behavior remains. Platform authentication bootstrap is skipped on tenant runtime hosts.

Same-origin tenant API calls need no wildcard CORS permission. Do not add suffix-wildcard platform origins. The platform PWA remains limited to non-tenant hosts; tenant origins do not register its service worker. Storefront canonical and sitemap URLs use the tenant origin.

## Rollout and rollback

1. Rehearse migration 105 against a disposable restore and remediate every reported identity explicitly.
2. Confirm wildcard DNS, TLS, and Tunnel readiness.
3. Set `PUBLIC_SITE_DOMAIN=madarportal.com` and production `VITE_API_URL=/api`, then promote the application bridge compatible with schemas 104 and 105.
4. Take and attest the governed schema-104 backup.
5. Apply forward migration 105 through the migration controller.
6. Validate backend host enforcement, frontend host routing, and same-origin proxy behavior.
7. Enable wildcard traffic and smoke-test at least two isolated tenants.
8. Verify legacy redirects, query preservation, mismatch rejection, cookies, forms, reservations, and checkout.
9. Observe invalid-host/mismatch logs, 5xx, cache behavior, and publication polling.

Migration 105 is forward-only. After commit, repair forward; do not automatically run downgrade SQL. Retain `/site/{tenant}` compatibility during the rollback window.

## Cloudflare/operator checklist

No repository change performs these actions.

- Add/proxy `*.madarportal.com` to the existing Madar Tunnel/edge target. Keep explicit records for infrastructure hosts.
- Confirm TLS covers `*.madarportal.com` and `madarportal.com`; a wildcard does not cover deeper labels.
- Order Tunnel ingress: exact infrastructure hosts first, `*.madarportal.com` to the existing frontend origin/port 3000 next, catch-all last.
- Let repository Nginx handle tenant `/api/**`; do not create an arbitrary upstream proxy.
- Preserve the public host and HTTPS scheme, overwriting client forwarding headers at the trusted edge.
- Ensure CDN cache keys include hostname and honor application cache headers.
- Apply existing WAF/rate limits to wildcard hosts; do not use unsafe string-suffix origin matching.
- Smoke test with a real test tenant:
  ```bash
  curl -I https://demo.madarportal.com/
  curl -I https://demo.madarportal.com/about
  curl -I https://demo.madarportal.com/shop
  curl -I 'https://madarportal.com/site/demo?x=1'
  curl -sS https://demo.madarportal.com/api/public/sites/demo
  curl -i https://demo.madarportal.com/api/public/sites/another-tenant
  ```
  The mismatch must fail and the legacy URL must end at `https://demo.madarportal.com/?x=1`.
