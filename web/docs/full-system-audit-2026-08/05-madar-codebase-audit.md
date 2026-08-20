# Madar codebase and architecture audit

## Architecture map

React/Vite frontend → Cloudflare Tunnel → loopback Nginx frontend and FastAPI backend → Supabase Auth/PostgREST/PostgreSQL/Storage, local filesystem storage, Redis, SMTP/Web Push, calendar providers, notification/calendar workers, parser worker, and a deliberately egress-capable remote-ingestion worker.

Backend entry is `backend/app.py`. Principal routers cover auth/password/MFA, profile/admin, builder, public sites, notifications, calendar, billing/entitlements, data analysis, storage, and health. Principal service boundaries include authentication/tenant context, audit/security logging, entitlement/usage reservation, storage accounting/asset registry, notification outbox/delivery, calendar queues, public-site address resolution, readiness, parsing/remote ingestion, and admin account access.

## Code quality and maintainability

The application has good service extraction around sensitive concerns, but its largest routers remain operational risk: builder (~112 KiB), calendar (~105 KiB), and public-site (~95 KiB) modules mix validation, authorization, persistence, workflow, and response shaping. This makes route-by-route authorization regressions harder to review and increases merge-conflict/testing cost.

Static scan found no `shell=True`, `os.system`, direct `eval`, bare `except`, or TODO/FIXME debt in the backend. It found many broad `except Exception` handlers; reviewed security-sensitive handlers generally roll back and log only error types. Outbound HTTP is centralized enough to identify provider and ingestion boundaries. SQL functions and dynamic queries require continued review, but the high-risk production grants were independently verified.

The frontend has no production `dangerouslySetInnerHTML` or `eval`; the sole `innerHTML` hit is a test assertion. It does use local/session storage extensively for builder recovery and job state. This is a privacy/XSS impact amplifier even when it is not an authorization mechanism.

## Authentication and admin

Verified controls include Secure/HttpOnly production auth cookies, signed CSRF cookie/token binding, Origin/Referer validation, exact credentialed CORS, login/signup/reset/MFA rate limits, Supabase AAL2 verification for sensitive admin routes, last-admin safety, audited support access, and rejection of support/impersonation context by sensitive builder paths.

The historical migrations `023` and `026` embed an operator email and then force numeric user ID 1 to global admin while demoting all other users. Production currently has exactly one admin and ID 1 is that admin. Current admin APIs protect the last admin, but a fresh or partially restored database can assign global power based on insertion order. Bootstrap must be explicit and one-time, not historical data mutation.

## Input and output safety

Request-body middleware enforces streaming ceilings before routes: approximately 256 KiB small requests, 3 MiB JSON, 12 MiB general, and 252 MiB builder upload request ceiling. Upload routes then enforce 25 MiB image, 250 MiB video, and 50 MiB document limits. CSV/spreadsheet exports neutralize formula injection. Errors generally return controlled codes and request IDs rather than raw exception text.

## Performance and scaling

The backend uses synchronous Supabase/HTTP clients in a primarily synchronous route model, so worker concurrency rather than async event-loop concurrency is the effective scaling mechanism. First bottlenecks are expected to be Supabase round trips, large builder JSON normalization/publication, data-analysis memory, upload I/O, notification/calendar fan-out, and external provider latency. The readiness schema check itself demonstrates the cost of many sequential/parallel remote schema probes under a two-second budget.

Pagination exists on major admin/collection routes, but large router/service operations and whole-schema builder payloads will need query/bundle profiling before scale. No destructive load test was performed.
