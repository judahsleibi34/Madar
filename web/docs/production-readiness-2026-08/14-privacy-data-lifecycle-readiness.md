# Privacy and data-lifecycle readiness

Status: **READY** for product/counsel decisions and development verification; production proof remains blocked by P0. This is a technical assessment, not legal advice.

## Lifecycle matrix

Every row must acquire an approved purpose, owner/controller determination, retention duration and legal basis from counsel/product. “Until account deletion” is not a complete retention rule. Deletion verification covers primary DB, files, caches, queues, generated exports, browser copies, provider copies, logs and backup expiry; immutable backups use documented suppression-on-restore and age-out rather than ad hoc mutation.

| Product/data class | Primary and derivative locations | Binding | Deletion/export and remaining proof |
|---|---|---|---|
| Madar account, tenant, membership | Supabase auth/DB, audit/log/cache, backups | user/tenant | self/admin closure policy, tenant export, last-owner rules, restored-backup suppression |
| forms/tests/submissions | DB, notification/export, logs/backups | tenant/project/publication/form | user-visible retention/delete/export, recipient copies, CSV safety, backup age-out |
| reservations/availability | DB, calendars, notifications, backups | tenant/project/block/customer | cancellation vs erasure, provider deletion, timezone/audit retention |
| analytics/IP/user agent | DB/cache/logs/backups and possible Cloudflare copy | site/tenant/pseudonymous visitor | minimization, aggregation, consent/cookie treatment, IP truncation and expiry |
| security/audit logs | DB/journal/container/off-host logs/backups | actor/tenant/security event | restricted access, justified tamper-resistant retention, deletion exceptions approved by counsel |
| browser builder recovery | IndexedDB/local/session/browser caches | browser profile/user/project | explicit disclosure, expiry, clear-on-sign-out/account deletion, shared-device test |
| assets/documents/media | registry DB, host files/object store, publications/CDN/cache/backups | tenant/project/visibility | primary/orphan cleanup, cache purge/expiry, quarantine copies, backup age-out |
| notifications/push | DB/queue/provider/browser/service worker/logs | tenant/user/device | unsubscribe, stale endpoint purge, payload minimization, browser cache clearance |
| calendars/OAuth | encrypted token, provider, events/jobs/logs/backups | user/tenant/connection | disconnect/revoke/retry, provider deletion limits, token and state expiry |
| Briefedly Gmail token | encrypted DB, process memory, backups, Google | user/workspace/connection | revoke, disconnect retry, key rotation, backup handling and old-token death |
| raw/parsed email and metadata | DB, import/job intermediates, backups | workspace/connection/thread/message | retention expiry, selective/workspace deletion, export, provider remains authoritative |
| report evidence/generated reports | DB, exports, browser/cache/backups, Ollama request memory | workspace/report/message | evidence cascade, artifact expiry, no model training, restore suppression |
| exports | controlled filesystem/object store/browser | requesting user/workspace | short TTL, one-time/authorized access, cleanup and access log |
| deletion/retention jobs | DB queue/audit/logs/backups | subject/workspace/job | idempotent completion, retry/dead letter, measurable overdue state |
| OAuth nonce/state/session/rate state | DB/Redis/cookies/logs/backups where applicable | user/workspace/browser | one-time use, short expiry, revocation/versioning and cache failure behavior |

## Operator privacy procedures

1. Authenticate requester and authority; require recent authentication for destructive/export action.
2. Freeze only the subject data needed to avoid races, inventory all scoped objects by aggregate/identifier metadata, and record request ID without content.
3. Generate encrypted authenticated export with bounded expiry and auditable delivery.
4. Revoke provider tokens and retry until provider outcome is known; then delete/cascade primary and derived data through a durable job.
5. Verify scoped counts, filesystem/object registry, cache/queue/export state and third-party action; never log private content.
6. Record backup generations containing the data and suppression-on-restore marker until retention expires.
7. Notify the requester of completion, exclusions or provider limitations using counsel-approved language.

Separate runbooks are required for account, tenant/workspace, connection/imported mail, form/submission, reservation, asset, and provider deletion. Test partial failures and restore interactions.

## Public-product prerequisites

Before payment/onboarding: accessible terms/privacy/support/incident contact; contextual notice for public forms/reservations and Gmail import; documented retention/export/delete/account closure; subprocessor and cross-border/data-location inventory; consent/policy version records where required; cookie/browser-storage disclosure; and internally approved controller/processor roles. Counsel must decide jurisdiction, age/children, retention/legal-hold exceptions, contractual commitments and notification language.
