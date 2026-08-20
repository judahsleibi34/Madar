# Madar calendar platform

Migrations `061`–`064` add provider-neutral calendars,
versioned events, attendees, reminders, recurrence exceptions, event history,
tasks, dependencies, workload data, encrypted sync connections, explicit sync
conflicts, and invitation review records.

Migration `065_secure_calendar_oauth_state.sql` adds hashed, single-use OAuth
state records and an atomic service-role-only consume function. None of
migrations 058–065 should be described as production-applied without separate
operator verification.

Migration `067_add_calendar_task_provider_sync.sql` adds protected task-to-event
linkage and bounded sync status. Tasks remain Madar planning records by default.
A scheduled task is sent to Google only after the user explicitly selects a
connected read/write account. The linked provider event uses the task title,
notes, schedule, timezone, and supported recurrence rule. Retrying updates the
same provider event instead of creating another one.

## Authorization model

- Tenant owner/admin: explicit override for all calendars in the tenant.
- Calendar owner: details, events, tasks, reminders, membership, OAuth, sync,
  conflicts, invitations, history, import, and export.
- Editor: details and content operations, sync state/trigger, conflicts, invitations,
  history, import, and export; no membership or OAuth account management.
- Viewer: details and export, but no mutation. Events explicitly marked private
  are reduced to busy/free intervals.
- Availability: bounded busy/free intervals only.
- Unrelated active members cannot discover private calendars. Disabled,
  deleted, unauthenticated, and cross-tenant users fail closed.

The backend uses the service role, so route authorization is mandatory and is
never delegated to a browser-supplied tenant identifier.

## Provider setup

Register these exact backend redirects with each provider:

- `${PUBLIC_API_URL}/calendar/oauth/google/callback`
- `${PUBLIC_API_URL}/calendar/oauth/microsoft/callback`

Google read connections request `calendar.readonly`; two-way connections request
`calendar.events`. Microsoft read connections request `Calendars.Read`; two-way
connections request `Calendars.ReadWrite`. Both request offline access so the
polling worker can reconcile changes when the user is away.

A connected read-only Google account is never silently upgraded. The user must
choose **Enable write access**, review the consent explanation, and complete a
new OAuth grant. Until the callback succeeds, the existing read-only credential
and import behavior remain intact. Interactive task synchronization runs
immediately through the existing sync service; the background worker is an
optional retry/reconciliation path and must be enabled separately.

Provider credentials and refresh tokens are encrypted before storage using
`CALENDAR_CREDENTIALS_SECRET`. Rotating this secret requires reconnecting
existing provider accounts.

Set `APP_ENV=production`, `CALENDAR_FEATURE_ENABLED=true`, exact HTTPS
`PUBLIC_API_URL` and `FRONTEND_PRIMARY_URL` origins, and provider credentials.
Production rejects localhost, paths, queries, fragments, and non-HTTPS OAuth
origins. State binds the connection, calendar, tenant, user, provider, issue
time, expiry, destination, and a random nonce. Only a nonce hash is stored, and
the callback consumes it atomically before token exchange. Codes and tokens are
never returned to frontend JavaScript. Google and Microsoft are the supported
OAuth providers; ICS remains an import/export path rather than OAuth.

Run workers with `docker compose --profile workers up`. The notification worker
queues due reminders and records delivery outcomes. The calendar sync worker
uses Google incremental sync tokens and Microsoft calendar-view delta links.
Provider failures appear as `degraded` connections and do not silently discard
local edits. Concurrent local/remote changes create explicit conflict records.
Disconnect removes stored credentials; Google revocation is attempted where
supported, while local credential removal remains fail-closed if provider
revocation cannot be confirmed.

Deleting a Madar-only task removes only that task (task reminders and
dependencies cascade through existing foreign keys). A synchronized task
requires an explicit choice: delete locally while preserving the Google event,
or delete both. Remote deletion requires an authorized read/write connection;
provider failure leaves the local task intact so the outcome is never
ambiguous. Completing or cancelling a task does not silently delete its Google
event.

## Recurring-event safety

The API accepts `occurrence`, `future`, and `series` edit scopes. Occurrence
edits create an exception and exclude the original instance. Future edits split
the recurrence at the selected occurrence. Every mutation increments an event
version and writes an immutable change record.

## Operational checks

- Alert when `calendar_sync_connections.status = 'degraded'` grows.
- Alert on old `last_success_at`, unresolved sync conflicts, failed reminders,
  and notification dead-letter growth.
- Never log OAuth codes, access tokens, refresh tokens, or encrypted credentials.
- Calendar readiness requires tables 061–065 and the single-use state RPC when
  the feature is enabled. Required provider sync additionally validates worker,
  secret, provider, and exact-origin configuration.
