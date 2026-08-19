# Privacy and data-lifecycle audit

This is a technical assessment, not legal advice.

## Data inventory

| Data class | Store/processors | Effective lifecycle | Main gap |
|---|---|---|---|
| Accounts, memberships, MFA/security | Supabase Auth/Postgres; Briefedly Postgres | account lifetime; admin/privacy-job deletion varies | Madar lacks comprehensive self-service closure/export |
| Builder drafts/published sites/settings | Postgres, browser localStorage, backups | indefinite/archive | local browser copies and backup erasure not controlled |
| Assets/datasets/charts/avatars | local bind mounts, Supabase storage, registry, backups | reference retention exists for builder assets | no universal subject/account erasure proof |
| Forms/tests/reservations | Postgres, notifications, exports, backups | mostly indefinite/status-based | tenant/submitter retention, notice, delete/anonymize incomplete |
| Analytics/IP/user agent/audit | Postgres and logs | mixed/undefined | explicit periods and minimization absent |
| Notification/push | Postgres, browser push providers | 90/180-day delivery retention with cleanup | no external proof cleanup/alerts run continuously |
| Calendar/OAuth | Postgres, Google/Microsoft | connection/event lifetime; disconnect | backup token erasure/rotation and provider-state proof |
| Briefedly Gmail tokens | encrypted Postgres, backups, Google | connection lifetime; revoke on disconnect | production worker/schema absent; key rotation unproven |
| Imported email/report evidence | Briefedly Postgres, Ollama | raw content default 720 hours in current source | cleanup inactive in production; derived/backup retention |
| Export artifacts | Briefedly Postgres | 24-hour default in current source | production schema/worker absent |
| Mailboxes | Mailcow volumes/backups | mailbox/server policy | no backup or documented retention/restore |
| Logs | journald/Docker/app tables | size-based/undefined time | no unified retention/access/erasure policy |
| Backups/config/secrets | local host | manual, never pruned by script | no off-host encryption, retention, or deletion propagation |

## Verified controls

Madar records Terms version/time, uses audit events with minimized IDs/hashes, redacts query strings/tokens, supports feature-specific export, and has admin deletion. Builder assets, notification deliveries, OAuth state, account lifecycle, and support access have explicit records/retention mechanics.

Briefedly current source supports recent-password + CSRF-protected workspace/account export/deletion, expiring artifacts, encrypted Gmail tokens, one-time OAuth nonce, raw-body cleanup, and disconnect. These controls are well designed but not active in the stale production deployment.

## Gaps before sensitive customers

1. Establish operator-owned privacy request intake, identity verification, tenant authority, deadlines, audit trail, and completion evidence.
2. Add comprehensive account/tenant/workspace export and deletion manifests across DB, filesystem, queues, browser guidance, provider tokens, logs, and backups.
3. Define category-specific retention; do not claim automatic deletion unless a monitored worker actually performs it.
4. Add tenant-configurable privacy links/notices and consent fields to public forms/reservations; arbitrary custom fields can collect special-category data today.
5. Maintain a subprocessor/data-location register for Supabase, Cloudflare, Google, Microsoft, push, SMTP, Ollama/Tailscale, and AI providers.
6. Define backup retention and how deletion requests age out of backups without making recovery impossible.
7. Verify age/minimum-age, cookie/browser storage disclosures, controller/processor roles, and DPA needs with counsel.

Existing Madar legal-data-practices documentation accurately identifies many gaps but contains stale implementation statements (for example, notification cleanup and form idempotency were subsequently added). Policy text and technical evidence must be re-baselined together.
