# Database integrity and provider boundaries

## Observed authority

PostgreSQL is authoritative for tenants/users/memberships, forms/submissions,
builder projects/settings, catalog/orders, reservations, commercial ledger,
notifications and audit records. Native Auth owns credential/session/TOTP state;
Storage owns bucket/object metadata and object bytes. Redis contains disposable
rate-limit/MFA-pending/cache state, not the durable notification business queue.
External financial providers and calendars remain independent authorities;
there is no cross-system transaction. No new connector framework or direct SQL
access layer was introduced.

`web/backend/database.py` uses synchronous Supabase-compatible HTTP clients;
`services/tenant_service.py` and resource authorization guard privileged queries.
RPCs provide existing atomic operations. `notification_outbox_service.py` and
`notification_delivery_queue_service.py` use PostgreSQL functions and leases.
No broad ORM/provider replacement or speculative index was justified by these
measurements. No monetary arithmetic or historical financial record was changed.

## Read-only production metadata

PostgreSQL 17.6;144 public tables had RLS enabled when inspected. `service_role`
has BYPASSRLS and is not superuser; it cannot CREATE in public. Inspected anon,
authenticated, authenticator and provider administrator roles were not superuser
or BYPASSRLS. This is not proof that every policy/view/function is correct.
Service-role access still requires application ownership checks. Tenant RLS
runtime-role cutover was not attempted. Background job tenancy was not exhaustively
verified.

## Migration safety

Source has146 mirrored migrations; source descriptor accepts schema144..146,
target146. Production release state independently reports146. No historical SQL,
release descriptor, transition manifest, controller or production migration state
was changed. Existing013/014 duplicate-content debt is preserved and reported.

Three disposable SQL rehearsals validate115,145 and146. They use random owned
containers, loopback-only ephemeral PostgreSQL, CPU/memory/PID bounds and known
synthetic database comments. `tests/disposable_database_support.py` rejects
remote/redirected DSNs, pins loopback hostaddr rather than trusting PGHOSTADDR,
and verifies the comment before writes on every connection. A marker query uses
autocommit before returning the caller's requested transaction mode. Test logs
must be read together with09-TEST-RESULTS.md; no production migration follows
from a rehearsal.

The146 pricebook test now closes only known synthetic `old_`, `current_`,
`second_` random fixture windows inside a rolled-back transaction. Earlier
continuity fixtures otherwise won automatic selection. It still asserts the
prepared pricebook/pricing and restoration of all prior windows after rollback.
No domain price selection rule was changed to satisfy the test.

## Native integration and recovery evidence

Native GoTrue/PostgREST/Storage schema plus immutable application migrations were
rehearsed in an independently marked staging database. Two synthetic tenants
could read their own builder projects; both cross-tenant IDs returned404,
spoofed user paths403, ordinary admin access403, and a foreign tenant query did
not change the server-owned tenant context. Coverage is selected reads, not a
complete write/mutation/worker isolation certification.

Notification fixture replay returned the same intent and a real worker consumed
it. SQL drill proved lease expiration/reclaim, delayed retry, exhaustion/dead
letter and terminal exclusion. **Unresolved:** migration073
`finish_notification_delivery` checks id/status but has no lease owner or claim
version argument. A native adversarial probe confirmed FAIL: attempt1 could mark the row sent after attempt2 reclaimed it.
A safe repair needs a new mirrored forward migration, versioned finish RPC,
worker compatibility handling and adversarial concurrent acceptance; editing073
or granting immediate production migration authority would be incorrect.
At-least-once processing and possible duplicate external effects remain.

Synthetic component recovery compares177 public/Auth/Storage tables,21 sequences,
object byte hashes and MFA factors into a separate database/object volume on the
same VM/cluster. Existing cluster roles are reused. This does not prove roles,
PITR, offsite recovery, full restored application operation, RPO or RTO.

## Remaining integrity work

Reservation capacity, order/inventory atomicity, payment-provider replay,
subscription reconciliation, concurrent builder mutation, deleted-form stale
writes and integration conflict semantics need additional native adversarial
coverage. Existing hermetic tests are useful evidence, not a substitute for
those drills. No new schema/index/currency authority is claimed here.


## Executed stale-owner failure probe

`evidence/notification-stale-ack.json` records schema146, source0c591b8f,
old_attempt1, reclaimed/current_attempt2, stale_finish_accepted:true, status:FAIL.
The marked synthetic database and owned worker were verified, the worker paused,
and all fixture writes rolled back before resuming it. This is a pre-existing
invariant failure, not a newly introduced regression or a passing acceptance.

The executed core sequence was an isolated transaction with synthetic tenant/user
values from the private smoke fixture and a generated deduplication key:

```sql
-- BEGIN; insert a synthetic internal notification with max_attempts=3;
-- old_claim := claim_notification_deliveries(1, clock_timestamp(), 30);
-- new_claim := claim_notification_deliveries(
--   1, old_claim.processing_lease_until + interval '1 second', 30);
-- Assert both claims identify this fixture and new_claim.attempts=2.
-- Then the old worker invokes the existing finish API:
select public.finish_notification_delivery(
  :fixture_id, 'sent', null, null, null,
  'synthetic-old-worker', :old_processing_started_at);
-- Actual result: status sent, attempts2; no claim generation was checked.
-- ROLLBACK; resume only the owned staging notification worker.
```

The pseudovariables above intentionally avoid publishing private fixture values;
the function signature/source and sanitized result make the failure auditable.
Acceptance for repair must reject stale sent/retry/dead completion atomically,
keep the newer claim intact, and preserve current-worker completion/retry and
old/new release compatibility. A separate read-before-finish application check
would still race and is not an adequate repair.
