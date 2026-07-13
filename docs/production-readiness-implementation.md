# Production-readiness implementation notes

This document describes the operational contract for migrations 043 through
046. It is not an applied-migration ledger and does not mean these migrations
have been run in production.

## Application order and verification

Apply both migration trees manually according to the existing deployment
process. The files in `database/migrations` and `supabase/migrations` are kept
byte-for-byte identical and must be applied in this order:

1. `043_create_account_lifecycle.sql`
2. `044_add_platform_safety.sql`
3. `045_harden_public_reservations.sql`
4. `046_create_notification_outbox.sql`

Do not rename the historical duplicate `040` migrations. Do not adopt
Supabase CLI migration automation without the baseline/import plan described
in `docs/migration-history.md`.

Read-only verification SQL after a non-production or production deployment:

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'users'
  and column_name in ('account_kind', 'account_status', 'pending_email',
                      'verification_required_at');

select to_regclass('public.email_verification_attempts'),
       to_regclass('public.pending_account_onboarding'),
       to_regclass('public.password_reset_requests'),
       to_regclass('public.billing_webhook_events'),
       to_regclass('public.notification_outbox');

select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'builder_projects'
  and column_name in ('draft_revision', 'published_revision', 'schema_version');

select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'builder_reservations'
  and column_name in ('idempotency_key_hash', 'request_hash', 'exclusive_slot',
                      'cancellation_token_hash');

select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in ('provision_verified_account',
                       'claim_password_reset_request',
                       'finish_password_reset_request',
                       'publish_builder_project_atomic',
                       'apply_billing_webhook_event',
                       'admin_update_user_type_safely',
                       'create_builder_reservation_safe',
                       'cancel_builder_reservation_safe',
                       'claim_notification_outbox',
                       'finish_notification_outbox')
order by routine_name;

select relname, relrowsecurity
from pg_class
where oid in ('public.email_verification_attempts'::regclass,
              'public.pending_account_onboarding'::regclass,
              'public.password_reset_requests'::regclass,
              'public.billing_webhook_events'::regclass,
              'public.notification_outbox'::regclass);
```

## Migration safety

- Migration 043 adds nullable lifecycle columns, synchronizes verification
  from `auth.users`, then backfills `account_status`. Existing
  provider-confirmed users remain active even if an older local flag was
  stale; existing tenants are not deleted. Rows used exclusively for public
  website membership are classified as `site_visitor` rather than `platform`
  so verification can never provision a SaaS tenant for a website customer.
- Pending signup rows expire after 14 days by default. Cleanup is never
  scheduled automatically. Run `python scripts/cleanup_pending_accounts.py`
  inside the backend image for a dry run. Deletion requires the explicit
  `--apply` flag and skips provider-verified users and users linked to a tenant.
- Verification provisioning locks the local user and uses uniqueness
  constraints/upserts. A requested subdomain that was claimed during the
  verification delay does not block account activation; it is cleared and the
  pending record receives `subdomain_unavailable`.
- Migration 044 backfills `features.billing_state_changed_at`. This is an
  update of the existing features table and should be measured on a
  production-like copy before deployment. Project revision columns use
  metadata/default additions. The last-active-admin trigger serializes role or
  account-status transitions with a transaction-scoped advisory lock.
- Migration 045 adds indexes and check constraints without deleting
  reservations. Historical rows with a missing start or end remain valid.
  New exclusive reservations are serialized per tenant/project/block.
- New feature-payment and reservation checks are added `NOT VALID` so they
  protect new writes without forcing an unbounded historical-table scan during
  deployment. Validate them later, after read-only queries confirm legacy rows
  comply, using a separately scheduled `VALIDATE CONSTRAINT` operation.
- Migration 046 only creates an outbox and worker-claim function. It does not
  send messages, start a worker, or delete notification data.

Rollback is application-specific. Dropping new columns or tables would destroy
lifecycle and idempotency records and is not an acceptable first response.
Prefer rolling the application back while retaining additive schema, then
prepare a separately reviewed cleanup migration if required.

## Canonical identity and email verification

Supabase Auth is the canonical email identity and confirmation-token authority.
`public.users.email` is synchronized only from a provider-confirmed identity.
Normal profile updates reject a different email atomically with
`email_change_requires_verification_flow`; the frontend displays the canonical
email as read-only.

A full provider-backed change-email flow is intentionally deferred. The
current SDK/provider redirect behavior has not been proven end-to-end with
recent-authentication/AAL2 and dual-address confirmation in this repository.
Until that work is completed, direct email editing must remain disabled.

Signup creates an unconfirmed Auth user, a minimal pending local user, and
pending onboarding data. It does not create an active tenant, membership,
project, feature, or website setting. Provider-confirmed status checks and
verified login reconcile the email and call the transactional provisioning RPC
for platform accounts only. Provider-confirmed website-customer accounts are
activated for their existing site membership without receiving a platform
tenant or owner membership.

Verification resend uses a signed HttpOnly pending context when available,
returns enumeration-resistant responses, records only email/IP hashes, and
enforces a 60-second cooldown plus five-per-hour and ten-per-day account
windows. Relevant environment overrides are:

- `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS`
- `EMAIL_VERIFICATION_RESEND_HOURLY_LIMIT`
- `EMAIL_VERIFICATION_RESEND_DAILY_LIMIT`
- `PENDING_VERIFICATION_TTL_SECONDS`
- `PENDING_VERIFICATION_SECRET` (a server secret is mandatory in production)

## Password recovery

Recovery resolves the submitted address in Supabase Auth first, then resolves
the local user by provider auth id. Local mutable email is not the authority.
Only provider-confirmed identities receive recovery email. One-time request
nonces are stored as hashes, older pending or in-progress records are revoked,
and claims are transactional. Once a claim starts processing it cannot be
replayed; a partial provider failure requires a new recovery request. Legacy
timestamp-only links are disabled by default. A finite
`PASSWORD_RESET_LEGACY_LINKS_ALLOWED_UNTIL` cutoff may be configured only for a
deliberate migration window, after which those links are rejected.

All signup, change-password, and recovery paths share an eight-character
minimum policy. Raising the policy later should be done in the shared backend
and frontend helpers together.

## Billing and publishing rollout

Online checkout is not implemented. The UI and API identify plan selection as
a manual access request and explicitly state that no payment is taken.

`ENFORCE_PUBLISH_ENTITLEMENT` defaults to false so current beta tenants are not
locked out on deployment. To stage enforcement:

1. Audit current feature rows and explicitly list temporary beta tenants in
   `PUBLISH_BETA_TENANT_IDS`.
2. Set `ENFORCE_PUBLISH_ENTITLEMENT=true` in a non-production environment.
3. Verify active, pending, past-due, expired, canceled, and absent feature
   behavior.
4. Enable in production only after existing tenants have an intentional state.

When enforcement is active for a feature-backed tenant, the publish RPC checks
the active feature again inside the same transaction as the revision check and
publish update.

The current shared-secret webhook is development/manual-only and is rejected
in production. A real payment provider remains blocked on provider selection,
signature format, event schema, and secret-rotation policy. The ledger and RPC
already provide event-id idempotency, payload conflict detection, and ordering
by provider occurrence time; senders that omit occurrence time use receipt
time and cannot receive strong out-of-order guarantees. Receipt-assigned time
is excluded from the stable replay hash so retries without a provider timestamp
remain idempotent. Ledger tenant identifiers intentionally do not cascade from
`public.tenants`, preserving replay protection after tenant deletion.

## Readiness policy

`/health/live` never depends on external services. `/health/ready` checks, with
short timeouts and a short cache, database REST access, required columns,
Supabase Auth health, Redis according to fail-open/fail-closed configuration,
and writable upload/chart directories. Responses contain component states only
and no URLs, credentials, or raw errors.

Production readiness is unhealthy when
`ADMIN_MFA_LOGIN_ENFORCEMENT` is not enabled, rate limiting is disabled, or
rate limiting is configured fail-open. Redis failure is required when rate
limiting is enabled and fail-closed; `RATE_LIMIT_FAIL_OPEN` defaults to false.
A non-production deployment may explicitly opt into fail-open behavior.

## Reservations, spam controls, and retention

Public reservations accept the same bounded idempotency key in the request
body and `Idempotency-Key` header. Only a server-side hash is stored. Same-key,
same-payload retries return the existing reservation; a different payload is a
409 conflict. Restricted/fixed-slot blocks are exclusive. Writers are
serialized per published block, and both interval overlap and legacy point
slots are checked.

Forms and reservations include an inaccessible hidden honeypot. Optional
submission elapsed time below the configured threshold returns the same generic
`submission_rejected` response. Existing Redis/IP rate limits remain in force.
External CAPTCHA is not configured; introducing one requires an accessible
fallback and a provider-specific adapter.

Cancellation tokens are opaque, stored only as hashes, expire, and are consumed
through a locking RPC. Automated delivery of cancellation links is deferred to
the notification worker/provider integration; the API returns the token only
when a reservation is first created (or deterministically replayed).

No production data retention deletion is scheduled by this change. Before a
retention worker is enabled, approve separate periods for form submissions,
reservations, verification attempts, billing webhook events, audit logs, and
notification outbox work. Every cleanup must support dry run, tenant scoping,
auditing, and legal hold exceptions.

## Notification outbox boundary

The outbox table, enqueue/claim/finish service interface, abandoned-claim
recovery, retry state, bounded attempt count, sanitized failure codes,
tenant-scoped deduplication key, and tenant scoping are implemented. Existing
in-app notification delivery is attempted synchronously and its durable outbox
work is marked sent or failed. Reservation email work is enqueued by recipient
hash/reference.

No background worker or email provider template implementation is scheduled in
this change. Pending email rows therefore represent durable work, not guaranteed
delivery. A worker must resolve recipient references server-side, use approved
templates, claim with `claim_notification_outbox`, apply bounded retries, and
never persist provider secrets or raw provider errors.

## Admin recovery

There is no MFA bypass endpoint. If the last active system administrator loses
all factors, recovery requires a controlled operator procedure:

1. Verify the operator through the infrastructure/provider access process.
2. Record an incident/change ticket and identify the affected auth/user ids;
   do not copy passwords, factors, or recovery tokens into the ticket.
3. Use the Supabase administrative factor-removal process or a separately
   reviewed, time-limited database operation from an approved console.
4. Require new MFA enrollment before sensitive admin actions.
5. Record the recovery action in `audit_logs` and remove temporary access.

The database prevents deleting, disabling, or demoting the last active system
administrator. Promotion requires provider-confirmed email, active account
state, acting-admin AAL2 at the route, and immediately marks MFA required for
the promoted account.
