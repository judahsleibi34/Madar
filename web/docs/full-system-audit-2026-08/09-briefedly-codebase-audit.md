# Briefedly codebase and architecture audit

## Architecture

React/Vite frontend → Cloudflare → FastAPI backend → local PostgreSQL → durable job worker → Google OAuth/Gmail → encrypted token storage → message/thread/report tables → Ollama over Tailscale → evidence-backed reports.

Current source is organized into auth, workspaces, communications/Gmail, reports, privacy, jobs, rate limits, middleware, and ORM/migrations. It is substantially cleaner and smaller than Madar. Tenant ownership constraints were added at the database layer and the Alembic graph has 15 revisions, one root, and one head (`c8e5f1a3b647`).

## Authorization and isolation

Every reviewed workspace resource route depends on a membership resolved by both current user and path workspace ID. Email connections, import jobs, threads/messages, reports, sources, background jobs, and export artifacts are then filtered by that workspace. Migration `a6c3d9e1f425` adds composite unique/FK relationships so a child cannot reference an object from another workspace even if application code errs.

Gmail connect/search/import/disconnect/provider operations require owner/admin authority. Ordinary members can read already imported workspace email and generate workspace reports; this is an explicit collaborative-workspace power and must be documented because it is broader than "only the Gmail owner." No confirmed cross-workspace IDOR was found.

## Auth/session controls

Passwords use a modern password-hash library, access tokens are short-lived signed JWTs, sessions are durable DB records, token versions allow global revocation, cookies are Secure/HttpOnly/SameSite in production, and state-changing routes require CSRF. Login/signup use both IP and account scopes. The current code validates production origins, cookie settings, Gmail credentials, DB credentials, and Ollama transport at startup.

## Code quality

Static scan found no dynamic execution, pickle, shell execution, or dangerous frontend HTML rendering. Broad exception handlers are relatively few and usually convert provider failure to controlled codes. Dependencies are exact-pinned through runtime inputs plus constraints. Production npm audit returned zero known production advisories at audit time.

The major issue is not source quality but source/runtime divergence. The public production backend identifies itself with the stale service name `priorify-backend`; current middleware/security headers and durable job tables are not active there.

## Performance

Gmail import and report generation are durable jobs in current source, with bounded thread/message/date/character counts, leases, heartbeats, retries, and idempotency. The absent production worker means these safeguards provide no production service. First scaling limits will be Gmail API quota, serial/provider fetch latency, database text size/indexing, Ollama throughput, and one worker's lease capacity. Per-workspace/user/global expensive-operation limits are present in current code.
