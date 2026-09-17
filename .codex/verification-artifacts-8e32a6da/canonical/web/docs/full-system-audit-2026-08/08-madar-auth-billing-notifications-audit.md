# Madar auth, billing, notifications, admin, and integration audit

## Auth/session lifecycle

Signup/onboarding is multi-step and handles duplicate/recovered identities, but complex compensation logic makes it a concurrency-sensitive path. Database uniqueness is the ultimate guard. Cookies are Secure/HttpOnly in production, CSRF is signed and session-bound, and logout clears browser state. Password reset records a bounded request window and avoids returning provider exception detail.

Supabase remains the authentication authority; token rotation/revocation behavior therefore depends on provider configuration not fully visible locally. Before scale, validate refresh replay across multiple backend replicas and record exact Supabase session/access/refresh lifetimes. Self-service full account/tenant deletion and comprehensive export are still incomplete compared with admin deletion and feature-specific exports.

## Admin

Global admin is `users.user_type=admin`; tenant roles are separate. Sensitive global routes call `require_system_admin(..., require_aal2=True)`. Promotion requires a verified account, demotion protects the last active admin, and changes are audited. Support account access is consent-code/session based and cannot be used as a shortcut into builder admin-write helpers.

The bootstrap migration that assigns admin by numeric ID remains unacceptable for reproducible recovery. Production has one admin, so loss/lockout of that identity is an availability risk even though last-admin deletion is blocked.

## Billing and entitlements

The canonical chain is tenant → one subscription state → plan snapshot/add-ons → capabilities/quotas → atomic usage reservations. Backend checks, not frontend hiding, enforce builder/storage/AI paths reviewed. Reservation/commit/release RPCs handle concurrent storage and AI usage. Missing/invalid commercial state does not silently grant paid capability.

Payment gateway, renewal, cancellation, invoice, refund, proration, and failed-payment workflows are not production-complete. Existing plan selection must be described as administrative/product configuration, not verified payment status.

## Notifications

Event → outbox → claim/resolve → delivery rows → channel worker → retry/backoff → sent/dead → cleanup RPC. Production runs a notification worker and readiness checks its health/queue. Delivery/outbox functions use skip-locked/atomic claims and deduplication keys for at-least-once semantics. Preference is checked at delivery resolution, which correctly respects late opt-out.

Production metadata shows 27 sent outbox items, 12 sent deliveries, and three dead deliveries. Readiness tolerates this count, but no external dead-letter alert exists. Retention cleanup now exists in migration 073 and the worker service; old legal audit text that said it was unenforced is stale.

Push endpoint ownership is user/tenant scoped, VAPID private material is server-only, and action URLs are constrained. Channel payload/template content remains an injection surface and should continue to be rendered as text or fixed templates.

## External integrations and failure behavior

| Dependency | Behavior |
|---|---|
| PostgreSQL/Supabase | hard outage; no authorization fail-open found |
| Redis | rate limiting fails closed in production; readiness degrades |
| SMTP/Web Push | queued/retried, then dead-letter; user action remains committed |
| Google/Microsoft calendar | queued eventual consistency; conflicts/failures recorded |
| Remote ingestion | dedicated egress worker; backend refuses missing/wrong worker identity |
| Parser | dedicated isolated worker required in production |
| AI generated code | disabled in current production; enabling it uses a subprocess in the backend container and is not sufficient isolation for hostile code |

Future chatbot/OCR/Drive/WhatsApp work must reuse tenant-scoped connection ownership, encrypted rotating tokens, atomic quotas, explicit retention, and isolated workers. OCR/document parsing should use a disposable no-network sandbox with no application secrets or shared writable mounts.
