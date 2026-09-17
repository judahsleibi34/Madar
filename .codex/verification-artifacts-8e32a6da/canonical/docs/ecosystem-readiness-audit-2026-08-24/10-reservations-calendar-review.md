# Reservations and calendar review

## Public reservations

Reservation validation derives tenant/project/block from the bound published snapshot, validates field/timezone payloads, rate limits, hashes cancellation/idempotency tokens and calls a service-role-only database RPC. Migration 046 provides:

- unique `(tenant, project, block, idempotency_key_hash)` where present;
- cancellation token uniqueness;
- start/end ordering check;
- project/tenant/published verification;
- `pg_advisory_xact_lock` per tenant/project/block;
- overlap check and insert inside the same transaction for exclusive slots.

This closes the common double-booking TOCTOU race. A corrected live aggregate found zero overlapping active (`new`/`confirmed`) exclusive reservations. Time values use timezone-aware timestamps and an explicit named timezone field. Cancellation expiry and status transition RPCs are present. No live booking/cancellation was executed.

The lock uses `hashtext`, which has a theoretical collision that causes unnecessary serialization, not unsafe parallelism. A native exclusion constraint would provide stronger independent defense, but historical-data compatibility is documented.

## Internal calendar

Calendar records, attendees, reminders, tasks, connections and sync queues carry tenant IDs. Authorization resolves calendar membership and capability server-side. Events use optimistic `version` checks on updates/deletes. Recurrence expansion is bounded by requested time range. Exports require both calendar access and import/export capability.

Application-level conflict checks for ordinary internal calendar events are not database exclusion constraints; this may be intentional because calendars often permit overlaps. Public exclusive reservations use the stronger RPC path.

## External sync

Google and Microsoft OAuth code uses an expiring database state record consumed atomically by migration 065, exact provider callback handling, bounded scopes and encrypted credentials. Refresh tokens are stored only in encrypted credential payloads and are not returned to the frontend. Google and Microsoft inbound synchronization are implemented; two-way task sync is Google-only in the UI. ICS import/export exists.

Production readiness reports calendar configuration/worker/queue healthy. A transient Supabase connectivity window on August 23 produced 49 calendar task poll errors, then recovered. Worker health itself is process-level; backend deep readiness provides the stronger queue/config check.

G10 is **PASS WITH CONDITIONS**: add concurrent database integration tests, DST/timezone matrices and provider outage/token-revocation E2E before scale launch.
