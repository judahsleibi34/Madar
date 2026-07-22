# Madar calendar platform

Migration `061_create_calendar_platform.sql` adds provider-neutral calendars,
versioned events, attendees, reminders, recurrence exceptions, event history,
tasks, dependencies, workload data, encrypted sync connections, explicit sync
conflicts, and invitation review records.

## Provider setup

Register these exact backend redirects with each provider:

- `${PUBLIC_API_URL}/calendar/oauth/google/callback`
- `${PUBLIC_API_URL}/calendar/oauth/microsoft/callback`

Google read connections request `calendar.readonly`; two-way connections request
`calendar.events`. Microsoft read connections request `Calendars.Read`; two-way
connections request `Calendars.ReadWrite`. Both request offline access so the
polling worker can reconcile changes when the user is away.

Provider credentials and refresh tokens are encrypted before storage using
`CALENDAR_CREDENTIALS_SECRET`. Rotating this secret requires reconnecting
existing provider accounts.

Run workers with `docker compose --profile workers up`. The notification worker
queues due reminders and records delivery outcomes. The calendar sync worker
uses Google incremental sync tokens and Microsoft calendar-view delta links.
Provider failures appear as `degraded` connections and do not silently discard
local edits. Concurrent local/remote changes create explicit conflict records.

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
