# Madar Backend Architecture Notes

Last updated: 2026-06-08

## Auth Model

Madar uses Supabase Auth for identity and HTTP-only cookies for browser sessions. The local `users` table remains the application profile and authorization source. Login returns the local user payload, including the local `id`, which is then used by frontend calls to user-scoped routes.

Protected browser requests read `madar_access_token` and `madar_refresh_token` cookies server-side. Auth routes are owned by `routes/auth_routes.py`; the deleted duplicate `contact_routes.py` auth router must not be restored.

## Route Boundaries

- `/auth/...`: public authentication/session endpoints.
- `/admin/...`: system-admin-only management APIs.
- `/users/{user_id}/...`: regular user workspace APIs. The `{user_id}` must match the authenticated local user id.
- `/public/...`: public no-auth endpoints such as published site reads, public form submissions, and the contact form.
- `/health/...`: process and readiness checks.

Admins are intentionally blocked from regular user workspace routes unless a future explicit impersonation flow is designed.

## Service-Role Safety Rule

`service_supabase` is server-only. It may be used only after the route has established the appropriate boundary:

- auth provisioning and local profile creation
- session/local user lookup after Supabase Auth
- tenant membership lookup after authentication
- admin-only management
- billing/admin billing management
- public contact insert
- public form submission insert
- avatar storage after user authorization
- website settings after user authorization
- builder queries after tenant authorization
- data-analysis routes after user authorization

Tenant-owned builder data must be queried with `tenant_id` wherever possible. Avoid project-id-only lookups for tenant resources.

## Logging Rules

Use structured event names such as `contact.message_received` and `builder.project_published`. Do not log secrets, cookies, tokens, service keys, or full public message bodies. User-facing errors should be generic; raw Supabase errors should stay out of API responses.

## Pagination

Growing list endpoints support database-level `limit` and `offset` pagination:

- default `limit`: 20
- maximum `limit`: 100
- default `offset`: 0
- invalid values return FastAPI validation errors

List routes fetch `limit + 1` rows where practical, return only `limit` items, and include:

```json
{
  "items": [],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "count": 20,
    "has_more": true
  }
}
```

Legacy response keys such as `projects`, `submissions`, and admin page metadata are preserved for frontend compatibility.

## Compression And Payload Safety

FastAPI `GZipMiddleware` is enabled with `minimum_size=1000` for larger JSON responses. It is registered alongside the existing CORS and CSRF middleware and does not change cookie behavior.

Builder `draft_schema` payloads are limited by `MAX_BUILDER_SCHEMA_BYTES`, defaulting to 2 MiB. The limit is intentionally generous for current builder usage and can be tuned without a code change.

Public data/form surfaces also keep compatibility-safe limits:

- public contact fields have strict length limits
- public form submissions validate answers against the published form schema
- remote data reads use timeouts, redirect limits, max byte limits, and private-network URL blocking
- uploaded and remote datasets have row and column caps

## Public Contact Route

`POST /public/contact` accepts `name`, optional `phone`, and `message`. It trims input, rejects empty names/messages, enforces max lengths, rate limits by client IP, inserts into the existing `contacts` table through `service_supabase`, and returns a generic success response. The route does not require authentication.

## Data Analysis State

Data-analysis routes are protected user APIs. Route modules delegate shared behavior into `backend/data_analysis/services.py`, and compatibility shims preserve older imports while the package is being organized.

## Deferred Phase 2 Items

- `analysis_jobs` table
- Redis/RQ or another worker queue
- `worker.py`
- staged analysis APIs
- frontend polling for async jobs
- deeper payload governance if future builder schemas grow beyond the current limit

## Deferred Database Redesign Items

- indexes, constraints, and foreign keys
- `audit_logs` table
- final builder schema and ownership model
- website settings ownership cleanup
- possible contacts table improvements
- UUID conversion, if ever needed
