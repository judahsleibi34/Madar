# Network, firewall, DNS, TLS, and SSH audit

## Authoritative listening-port inventory

| Bind | Ports | Owner/purpose | Assessment |
|---|---|---|---|
| loopback | 3000/8001 | Madar production | correct origin isolation |
| loopback | 3001/8002 | Madar development | not directly public |
| loopback | 3010/8010 | Briefedly production | correct origin isolation |
| loopback | 3011/8011 | Briefedly development | not directly public |
| loopback | 3020 | Sleibi | correct |
| loopback | 6379 | Madar Redis | local-only but unauthenticated |
| loopback | 13306/7654 | Mailcow DB/Redis | correct |
| all IPv4 and IPv6 | 22 | SSH | public management surface |
| all IPv4 and IPv6 | 25, 465, 587 | SMTP/submission | intentional mail surface |
| all IPv4 and IPv6 | 110, 143, 993, 995, 4190 | POP/IMAP/Sieve | legacy plaintext-capable ports increase surface |
| all IPv4 and IPv6 | 8080, 8443 | Mailcow web/admin origin | directly reachable, not Cloudflare-only |
| Tailscale | overlay sockets | host/tailnet | trust depends on tailnet ACLs |

No PostgreSQL, Docker API, Uvicorn, frontend development server, Redis, or Ollama listener was found globally bound. Docker runtime publishing confirms the SaaS origins are loopback-only.

## Firewall

`/etc/default/ufw` specifies IPv6 enabled and default input/forward DROP, but `/etc/ufw/ufw.conf` says `ENABLED=no`. Root-only `ufw status`, nftables, iptables, and ip6tables inspection was denied. Therefore effective host filtering is **not verified**. Public probes demonstrate HTTPS/mail reachability; listening sockets show IPv6 exposure is real, not theoretical.

Required root verification: capture `ufw status verbose`, `nft list ruleset`, `iptables-save`, `ip6tables-save`, Docker `DOCKER-USER` policy, forwarding/sysctl state, and an external IPv4/IPv6 scan from outside the LAN. Explicitly decide whether 110/143, 8080, and 8443 should be Internet-reachable.

## SSH

Readable base config disables keyboard-interactive authentication but otherwise keeps many defaults: root key login is likely permitted (`prohibit-password` default), password authentication may remain enabled, X11 forwarding is explicitly enabled, TCP/agent forwarding default to enabled, `MaxAuthTries` defaults to 6, and no idle timeout or allowlist is visible. The decisive cloud-init drop-in is mode 600 and could not be read; `sshd -T` also failed on that file. Effective state therefore needs root verification.

Recommended baseline: keys only; `PermitRootLogin no`; password and KbdInteractive off; X11/agent forwarding off; restrict TCP forwarding unless required; explicit `AllowUsers`/`AllowGroups`; lower auth attempts; sensible idle timeout; retain modern OpenSSH crypto defaults; test a second session before rollout.

## Public DNS and Cloudflare

Madar, `www`, API, and Sleibi resolve to Cloudflare anycast A/AAAA records. Briefedly, `www`, and API also resolve to Cloudflare. `mail.madarportal.com` resolves directly to the mail origin, as expected for SMTP. Application origins are not directly exposed by host ports.

Madar mail DNS has MX to `mail.madarportal.com`, strict SPF (`mx -all`), and a DKIM public key. DMARC is only `p=none`, so spoofed aligned-domain policy is monitoring-only. Briefedly currently has no observed MX/SPF/DMARC records; acceptable only if it never sends/receives mail as that domain.

## Public HTTP/TLS

- Madar and Sleibi return Cloudflare HSTS (`max-age=15552000`) and strong origin CSP/anti-frame/nosniff/referrer policies.
- Briefedly returns 200 through Cloudflare but lacks HSTS, CSP, frame restriction, permissions policy, and explicit no-store at the public edge.
- Mailcow HTTPS, SMTP STARTTLS, SMTPS, and IMAPS present a valid Let's Encrypt certificate for `mail.madarportal.com`, valid 2026-07-10 through 2026-10-08. No certificate-expiry alert was found.
- Mailcow outbound connection-only TCP/25 to Gmail MX timed out. This supports the historic ISP/router egress restriction; it is not an application defect.
