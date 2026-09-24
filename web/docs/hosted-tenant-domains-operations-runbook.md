# Hosted Tenant Domains Operations Runbook

This runbook records the schema-105 production architecture verified on 2026-09-24. At closeout, the serving release was `8c3ae47f848a4b84655d6d6cb42edac3e69be989` in slot `blue`, the 16 website bindings were nonempty and unique, and automatic deployment was disabled. These are historical facts, not values to pin in a monitor or assume during a future incident. Read live version, readiness, release state, and backup evidence each time.

## Request path and source of truth

```text
Browser → Cloudflare DNS/TLS/WAF → Tunnel ingress → release proxy :3000
        → frontend Nginx → tenant SPA route
                         → same-origin /api/** → slot-local backend
                                                → host/tenant validation
                                                → website_settings.subdomain
                                                → tenant + published project
```

`madarportal.com` serves the platform. `https://{tenant}.madarportal.com/` and its `/about`, `/shop/**`, `/forms/{id}`, and published page routes serve the tenant. Wildcard DNS and TLS cover one-label tenant hosts; no per-tenant DNS record is needed. Exact infrastructure hosts retain their own routes. The frontend proxies `/api/**` to its Compose-local backend, so tenant browser calls remain same-origin and the active frontend stays paired with its release slot's backend. The backend validates the public `Host` and trusted proxy forwarding context before using a path tenant identifier.

`website_settings.subdomain` is the canonical binding. Migration 105 normalizes it to a lowercase DNS label, rejects reserved names, requires one binding per hostname, and enforces case-insensitive uniqueness. `standard_path_slug` is legacy-path compatibility data. A tenant hostname is authoritative: a path identifier cannot select a different tenant. Ambiguous, unpublished, inactive, or unknown bindings fail closed. See [canonical hosting architecture](canonical-tenant-hosting-architecture.md) for the full publication contract.

The reserved-label contract includes `admin`, `api`, `app`, `auth`, `billing`, `cdn`, `dashboard`, `forms`, `health`, `login`, `logout`, `mail`, `pricing`, `privacy-policy`, `public`, `signup`, `site`, `static`, `terms-and-conditions`, and `www`. Check the authoritative backend, frontend, and migration contract before adding an infrastructure hostname. Current exact Tunnel routes include apex, `www`, `api`, `mail`, and `sleibi`; other explicit services, including unrelated domains, also exist. Inspect the actual ingress configuration rather than treating this list as exhaustive.

## Edge ordering and tenant operations

Tunnel ingress must match exact hostnames first, `*.madarportal.com` to the frontend origin `:3000` next, and the terminal `http_status:404` last. Keep `api` and `mail` ahead of the wildcard or they may reach the tenant frontend instead of their intended origins. The exact frontend origin should preserve the public host and HTTPS forwarding context. The release proxy routes the active frontend to port `3100` or `3200`; its matching backend is `8101` or `8201`.

To provision a tenant, use the ordinary authorized account/settings and publication workflows. Confirm an active tenant, one valid nonreserved `website_settings.subdomain`, an appropriate hosted-address entitlement, and a bound published project for a website. Public forms require their own publication/capability contract. Wildcard DNS already covers new tenant labels. Confirm the generated canonical URL and perform tenant-host plus wrong-host checks after provisioning.

For a rename, check global case-insensitive availability and reserved names, authorize the settings change, record the audit event, and verify that old and new host caches cannot reuse tenant data. Update customer links, QR/share URLs, and external references. The old hostname does not automatically become an alias or redirect. `standard_path_slug` can retain a legacy `/site/{slug}` mapping but is not a hosted alias. Plan a rollback as another authorized settings change only if the old label remains free; verify publication and caches afterward. Never assign a colliding label silently.

Main-host `/site/{tenant}/...` URLs are compatibility routes. A valid `/site/madar-demo/about?x=1` yields HTTP 308 with `Location: https://madar-demo.madarportal.com/about?x=1`. The server validates the legacy identifier against database state before building the redirect, preserving the query. Fragments are browser-only. `/store/{tenant}/...` and `/forms/{tenant}/{id}` have corresponding compatibility handling. Canonical tenant hosts do not loop back to legacy paths.

| Request | Expected result |
| --- | --- |
| Correct host and matching path tenant | Site/bootstrap data for that tenant, subject to publication |
| Correct host and a different valid path tenant | 404; no cross-tenant data |
| Unknown one-label tenant host | 404 for tenant public API |
| Unknown path tenant | 404 |
| Reserved infrastructure host | Exact service route, never a tenant binding |

## Security and cache boundaries

Tenant `/api/**` uses the tenant origin; it does not require wildcard CORS or parent-domain cookies. Auth, refresh, CSRF, MFA, and tenant visitor cookies remain host-only. Do not add `Domain=.madarportal.com`. The trusted edge/release proxy must replace client-supplied forwarding headers; the backend only consults `X-Forwarded-Host` from a trusted immediate peer. CSRF origin checks remain exact-origin and DNS-boundary aware.

HSTS `max-age` is active. **Keep `includeSubDomains` disabled** until a separately reviewed security decision covers every subdomain and service, including non-tenant exact hosts. The synthetic monitor fails if it sees that directive on any observed response. Tenant-specific caches and ETags must retain hostname, tenant/site, project/publication, version, and schema identity. Validate host/tenant agreement before cache lookup or reuse; `/` alone is never a safe shared cache key. CDN rules must include the host and honor application cache directives.

## Synthetic monitor and alerting

`web/scripts/monitor_hosted_domains.py` performs nine public, unauthenticated GETs every five minutes when its timer is separately enabled. It checks the demo homepage, `/about`, `/shop`, tenant `/api/health/version`, tenant bootstrap, wrong-host 404, unknown-tenant 404, exact 308 legacy redirect with query preservation, and explicit API `/health/version`. It compares the two live release SHAs and slots; it never pins a release. It also checks a positive HSTS `max-age` on the tenant homepage and rejects `includeSubDomains` on every observed response. A fresh 128-bit random host makes the isolation checks independent of a fixed unclaimed name. Redirects are never followed. Each request has a four-second timeout and no credentials. The result is one JSON journal line with status, codes, bounded timings, SHA, slot, and per-probe errors; failure exits nonzero and triggers `madar-ops-alert@%n.service`.

The production `/health/version` response reports the release slot as well as the SHA. The monitor requires both fields on both origins and fails if they disagree. It has no local production-state, cloudflared, database, or backup access; inspect those separately below. The control-plane installer preserves, installs, and attests the script and systemd units but does not enable or start the timer. A future authorized control-plane upgrade is required before the installed files can be used. This task does not perform it.

## Safe diagnosis

These commands are read-only. Run them from an approved operator environment; replace placeholders with reviewed values. Do not print protected environment files or credentials.

```bash
curl --max-time 10 -sS -i https://api.madarportal.com/health/version
curl --max-time 10 -sS -i https://api.madarportal.com/health/ready
curl --max-time 10 -sS -D - -o /dev/null https://madar-demo.madarportal.com/
curl --max-time 10 -sS -D - -o /dev/null https://madar-demo.madarportal.com/about
curl --max-time 10 -sS -D - -o /dev/null https://madar-demo.madarportal.com/shop
curl --max-time 10 -sS -i https://madar-demo.madarportal.com/api/health/version
probe_label="monitor-$(openssl rand -hex 16)"
curl --max-time 10 -sS -D - -o /dev/null "https://${probe_label}.madarportal.com/api/public/sites/madar-demo/bootstrap"
curl --max-time 10 -sS -D - -o /dev/null 'https://madarportal.com/site/madar-demo/?probe=manual-check'
cloudflared --config /etc/cloudflared/config.yml tunnel ingress validate
cloudflared --config /etc/cloudflared/config.yml tunnel ingress rule https://api.madarportal.com/health/version
cloudflared --config /etc/cloudflared/config.yml tunnel ingress rule https://madar-demo.madarportal.com/
systemctl is-active cloudflared.service madar-release-proxy.service
systemctl is-enabled madar-auto-deploy.timer madar-backup.timer madar-backup-verify.timer madar-node1-backup.timer
systemctl --failed --no-pager
systemctl list-timers 'madar-*'
systemctl show madar-backup-verify.service madar-node1-backup.service -p Result -p ExecMainStatus -p ActiveEnterTimestamp
stat -c '%y %n' /var/lib/madar/backups/LATEST
journalctl -u madar-node1-backup.service -n 30 --no-pager
journalctl -u madar-hosted-domain-monitor.service -n 30 --no-pager
```

Cloudflared ingress commands may require an operator with read access to the root-protected configuration; they must not display credentials. On Node 1, inspect the latest verified replica under `/srv/data2/madar-backups` and compare its backup ID and `SHA256SUMS` digest to the governed source receipt. At closeout, backup `madar-20260924T121538Z` and SHA256SUMS digest `1fe74342d6e06a92ac310f0067390eb504cfcdc7a73d2bf24ddf06b07c60ab55` were verified on Node 1; these are historical evidence, not a substitute for a fresh receipt. Website settings hostname bindings and `application_schema_state` are part of the database backup. Offline/offhost backups have a separate policy.

## Failure triage and rollback

| Symptom | Check first |
| --- | --- |
| Wildcard hostname does not resolve | Wildcard proxied DNS record and Tunnel health |
| TLS fails on tenant host | Wildcard certificate coverage and edge TLS mode |
| `api`/`mail` reaches the site frontend | Exact ingress rule position ahead of wildcard |
| Tenant host reaches wrong origin or 404 at edge | Wildcard rule position ahead of final 404; inspect `ingress rule` output |
| Tunnel down | `cloudflared` state, journal, and exact-host health |
| Frontend responds but tenant fails | Same-origin `/api`, backend readiness/version, binding, publication, trusted host headers |
| Tenant resolves but site missing | `website_settings.subdomain`, active tenant, published project/binding |
| Wrong host retrieves valid tenant | Treat as a tenant-isolation incident; preserve request/cache evidence and contain exposure |
| Duplicate/reserved binding attempt | Reject and explicitly remediate the requested identity; do not auto-rename |
| Unexpected cross-tenant cache result | Contain cache serving, inspect host-aware key/Vary/ETag behavior, preserve evidence |

Edge rollback means restoring the last reviewed exact/wildcard/catch-all routing order through the Cloudflare operator process; it does not change application or data. Application rollback requires the release controller's retained-target and schema compatibility attestations. **Never manually run a schema-104 application against schema 105.** After schema 105, use a schema-105-compatible release or reviewed forward repair. Database recovery is a separate incident decision: verify a fresh backup and isolated restore, assess RPO, and use governed recovery procedures. Never run reverse SQL just to clear an alert.

## Future change checklist

Before a hosted-domain change: record serving SHA/slot/schema, current exact and wildcard ingress order, tested tenant bindings, synthetic monitor baseline, verified backup and Node 1 receipt, rollback owner, and HSTS policy. During the change: validate edge rule selection and host forwarding; confirm same-origin API identity, 308 Location, correct-host 200, wrong-host and unknown-host 404; inspect HSTS. After the change: observe several monitor cycles, release/readiness and systemd failures, tenant cache separation, backup timers, and Node 1 replication. Preserve logs and change record.

## Gate for automatic deployment

`madar-auto-deploy.timer` stays disabled and inactive. Re-enable it only after the monitor implementation is merged, the reviewed monitor files are installed through the governed control-plane process, its own timer is separately activated, multiple real production runs are healthy, normal backup timers are active, Node 1 replication is current and verified, no relevant units have failed, the deployment guard accepts the exact main candidate, exact-main CI is green, and rollback/recovery documentation is current. Record the operator's approval and current release/schema identity before enabling. A failed synthetic check blocks re-enablement and requires investigation. If automation has later been enabled and monitoring detects a regression, the immediate containment command is `sudo systemctl disable --now madar-auto-deploy.timer`; then preserve the monitor JSON, alert, release state, and logs for diagnosis. The monitor never changes the timer itself.
