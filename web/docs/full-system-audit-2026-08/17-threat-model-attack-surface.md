# Threat model, attack surface, and trust boundaries

## Trust-boundary diagram

```text
Anonymous/authenticated browser
          |
          | HTTPS, Cloudflare controls
          v
Cloudflare DNS/proxy/tunnel ---- public Internet mail clients/servers
          |                                   |
          | tunnel HTTP to loopback           | SMTP/IMAP TLS
          v                                   v
Linux host (madar=root-equivalent)        Mailcow containers/volumes
          |
          +--> Docker networks --> frontend --> backend --> workers
                                  |             |  |  |
                                  |             |  |  +--> filesystem uploads
                                  |             |  +----> Redis
                                  |             +-------> Postgres/Supabase
                                  |
                                  +--> Briefedly worker --> Google Gmail/OAuth
                                                       --> Tailscale --> Ollama
```

Internet→Cloudflare is TLS and unauthenticated for public pages; dashboard/API authorization occurs in the app. Tunnel→origin is local plaintext HTTP for SaaS origins; host compromise can observe it. Backend→Supabase is TLS but currently uses superuser/service credentials. Docker network isolation is meaningful only until a credential-bearing container or Docker socket is compromised. Briefedly→Ollama is Tailscale-encrypted but HTTP/unauthenticated at the application layer.

## Actor attack-surface map

| Actor | Reach/power | Principal risk |
|---|---|---|
| Anonymous Internet user | public sites/forms/reservations/auth, Cloudflare, mail protocols | abuse/DoS, upload/parser, form spam, auth attacks |
| Authenticated normal user | own tenant/workspace resources; imported workspace email by membership | IDOR, quota abuse, stored content, report prompt injection |
| Tenant/workspace owner | members, integrations, sites, exports/deletion/settings | insider data exfiltration/destructive change |
| Global administrator | all Madar users/billing/support access at AAL2 | total SaaS-plane compromise |
| Compromised app container | its env, mounted writes, Docker networks, external services | currently DB superuser/service role; cross-tenant breach |
| Compromised `madar` user | source, env, backups, logs, Docker, sudo | host root and all local systems |
| Compromised DB credential | full corresponding DB; currently superuser | all tenant/email data, persistence, role creation |
| Compromised tunnel credential | route/tunnel availability and origin reach depending Cloudflare account scope | phishing/routing/outage; not DB access by itself |
| Stolen Gmail refresh token | connected mailbox data within granted read-only scope | private email exfiltration until revocation |
| Malicious uploaded document | validators, storage, parser, visitor download/browser | parser escape, resource exhaustion, active PDF content |
| Malicious imported email | Gmail parser, DB, prompt, Ollama, report/browser | prompt injection/hallucination, resource exhaustion; no command sink found |

## STRIDE summary

- **Spoofing:** credential theft, OAuth state/session theft, Ollama endpoint impersonation, hardcoded admin bootstrap. Strong state/session/MFA controls mitigate user spoofing.
- **Tampering:** app superuser credentials, Docker/root-equivalent host user, deployment from mutable repos, stale runtime. Atomic tenant RPCs and composite FKs mitigate ordinary-user tampering.
- **Repudiation:** Madar audit events and Briefedly audit logs are good, but no immutable/off-host security log, clock/collector assurance, or operator alert workflow exists.
- **Information disclosure:** database superusers, over-injected container secrets, localStorage drafts, inline hostile documents, backups/transcript/history credentials, Gmail/Ollama transport scope.
- **Denial of service:** shared disk, build cache, mail/WAL/log growth, expensive uploads/AI, external provider outage, flaky readiness. Limits exist, but host-wide quotas/alerts do not.
- **Elevation of privilege:** Docker group/socket, DB superusers, historical ID-1 admin bootstrap, privileged Mailcow/Portainer. Current tenant routes/RLS significantly reduce normal-user elevation.

## End-to-end flows

### Madar public form

Visitor → Cloudflare → body/rate/honeypot controls → unambiguous hostname/site/project/publication/form lookup → typed validation/idempotent RPC → submission DB → outbox/delivery → worker → tenant dashboard. Failure after DB commit becomes retry/dead-letter, not lost submission.

### Madar asset

Authenticated tenant user → CSRF/auth/capability → request/MIME/size checks → storage quota reservation → atomic file/object registry → reference reconciliation → immutable publication reference → visitor. Orphan cleanup is retention-based; reconciliation/AV remain gaps.

### Madar publication

Editor → tenant/project role → expected revision/schema validation → immutable snapshot/atomic activation → site binding → publication-specific ETag/no-store CDN → visitor. Ambiguity fails closed.

### Briefedly Gmail

Owner/admin → hashed one-time OAuth state → Google code/token → encrypted connection → durable import job → Gmail pagination/MIME bounds → workspace-scoped DB → hostile-evidence prompt → Tailscale Ollama → schema/evidence validation → workspace report/browser. In current production the durable worker portion is absent.
