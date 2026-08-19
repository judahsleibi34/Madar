# Sleibi, Mailcow, and other hosted services audit

## Sleibi

Sleibi is confirmed independent and static. It contains HTML/CSS/JS/images only, no server application, API call, fetch/XHR/WebSocket, form action, analytics/payment SDK, shared writable volume, or Madar tenant/cart runtime. Contact links use `tel:`, `mailto:`, and optionally WhatsApp; dynamic content is assigned through `textContent`, not HTML.

The container binds loopback 3020, is read-only, capability-reduced, no-new-privileges, PID-limited, and health-checked. Public CSP has `connect-src 'none'`, `form-action 'none'`, `object-src 'none'`, and no frames/workers. Source validation passed. Sleibi cannot inherit host-only Madar cookies because its hostname differs, assuming Madar never sets cookies for the parent `.madarportal.com` domain; current app cookie config does not.

One low reliability issue: `config/shop.js` and other unversioned assets are cached `immutable` for seven days. Deploying a changed merchant address/contact/product at the same URL can remain stale for returning browsers. Use content hashes or remove immutable caching for mutable config.

## Mailcow

Mail services expose SMTP 25/465/587, POP 110/995, IMAP 143/993, Sieve 4190, and direct web 8080/8443 on IPv4 and IPv6. Postfix relay restrictions are `permit_mynetworks, permit_sasl_authenticated, defer_unauth_destination`, which is not an open relay configuration. Server-to-server outbound TLS is DANE; inbound SMTP TLS is opportunistic (`may`); Dovecot minimum is TLS 1.2.

Public HTTPS/SMTP/SMTPS/IMAPS use a valid Let's Encrypt certificate. Actual private key is mode 600; the tracked `ssl-example/key.pem` is mode 664 and should remain example-only. Mailcow has custom dirty tracked configuration and untracked backups, making vendor upgrades/rebuilds non-reproducible until differences are documented.

SPF and DKIM are present for Madar. DMARC `p=none` does not enforce quarantine/reject. Outbound TCP/25 to Gmail MX timed out without sending data, consistent with the historical ISP/router restriction; inbound/service configuration is distinct from egress reachability.

No Mailcow-consistent backup was found. Port 110/143 and direct admin web access should be explicitly justified or disabled/restricted after client compatibility review. Mailcow's Docker API proxy/scheduler and privileged containers expand host compromise impact.

## Other services

Portainer and Nginx Proxy Manager are present with Docker-socket/legacy configuration; shared PostgreSQL 17 exists with a hardcoded Compose password and unclear active consumer. Checked-in NPM/shared-DB port declarations do not match the running containers. Treat these as unknown assets: assign owner/purpose, verify authentication/update path/backups, then formally retain or decommission in a separate approved change.
