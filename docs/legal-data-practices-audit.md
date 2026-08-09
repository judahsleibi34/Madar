# Madar Legal and Data-Practices Audit

**Audit date:** 2026-07-25  
**Repository:** `/home/madar/saas/Madar-dev`  
**Branch:** `builder-backend`  
**Commit:** `78bf6f000a7edb2b98a0cd7aaf61a60f74935734`

> This is a technical and factual audit, not a legal opinion and not a draft Privacy Policy or Terms and Conditions. It describes the inspected development checkout. Runtime behavior remains dependent on deployed configuration, applied migrations, Supabase project settings, and operational practices that are not fully observable from this repository.

## 1. Executive summary

Madar is a multi-tenant React/FastAPI service using Supabase Auth, PostgreSQL/PostgREST, and Supabase Storage, plus local mounted storage and Redis. Verified current product areas include platform accounts and tenant workspaces, a website/page builder, published sites, public forms and reservations, public-site visitor accounts, data upload/analysis/export, calendars, optional Google/Microsoft calendar synchronization, notifications, administrative user management and temporary account access, and a manual billing-selection workflow.

The current legal pages are materially incomplete. The Privacy Policy names only a subset of processed data and third parties. Its statement that the application uses “first-party authentication and CSRF cookies” omits four other application cookies, including an administrator account-access cookie, and it omits substantial browser storage. It also omits public-site accounts, reservations, calendar data, web push, notification queues, data-analysis files, optional AI processing, optional calendar providers, Google Fonts, QR generation, WhatsApp sharing, YouTube embeds, Google Sheets retrieval, and customer-configurable external content. The Terms accurately state several broad responsibilities but give insufficient detail on billing, customer visitor data, support access, content licensing, termination/deletion, governing entity and law, refunds, eligibility, privacy obligations, and feature limitations.

The most consequential verified issues are:

- Platform signup requires explicit Terms acceptance and stores a date/version, but public-site visitor registration creates a Supabase identity and local user without Terms acceptance. No Privacy Policy acceptance, policy-version history, or material-change notice mechanism was found (`backend/routes/auth_routes.py:291-399`; `backend/routes/public_site_routes.py:1284-1366`; `supabase/migrations/048_add_terms_acceptance.sql:3-35`).
- There is no self-service account or tenant deletion and no comprehensive account export. A Madar administrator can delete a user; deletion may also delete the tenant when no other staff membership exists, but file deletion and backup erasure are not transactionally guaranteed (`backend/routes/admin_user_routes.py:84-123`; `backend/services/admin_user_service.py:281-375`).
- Form and reservation records have no record-level deletion endpoint or defined retention rule. Reservation “cancellation” changes status rather than deleting data (`backend/routes/builder_routes.py:1296-1385,2016-2167`; `backend/routes/public_site_routes.py:1907-1975`).
- Customer-defined forms accept arbitrary field labels and answers. There is no sensitive-field blocklist, dedicated consent field, or tenant privacy-notice requirement. A “file” form field stores only filename, size, and MIME metadata, not file bytes (`backend/routes/public_site_routes.py:1055-1095`; `frontend/src/components/PageBuilder/core/PageBuilder.constants.js:121-131`; `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:1380-1408`).
- Form submissions and reservations store submitter IP addresses and user-agent strings. Reservation payloads are also duplicated into notification data. Active tenant staff can view tenant submissions and reservations (`supabase/migrations/027_create_builder_form_submissions.sql:13-30`; `supabase/migrations/044_create_builder_reservations.sql:9-39`; `backend/routes/builder_routes.py:1296-1354,2016-2094`; `backend/routes/public_site_routes.py:1847-1881`).
- Billing is not a payment system. Choosing a plan creates a pending manual request; no payment provider, card processing, automatic renewal, cancellation portal, invoice, tax, chargeback, or refund implementation exists. Static monthly dollar amounts are shown, but currency semantics and taxes are unspecified (`backend/routes/billing_routes.py:31-80,126-174`; `frontend/src/content/pages/pricingContent.js:38-149`; `frontend/src/components/DashboardBuilder/MyPlanPage.jsx:67-104`).
- Builder images are intentionally public; avatars are in a public Supabase bucket. Dataset files and generated charts are private local files, but no server-side deletion or retention workflow was found for them. Browser-side dataset storage can contain full data and is unencrypted unless the user supplies a password (`backend/app.py:191-223`; `supabase/migrations/022_create_avatars_storage_bucket.sql:12-37`; `backend/data_analysis/services.py:429-507`; `frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/datasetStorage.js:1-213`).
- Optional Gemini processing sends a user instruction and dataset profiles/sample values to Google when enabled and configured. Google and Microsoft calendar synchronization can transmit calendar content and store encrypted OAuth credentials. Neither appears in the current Privacy Policy (`backend/data_analysis/ai/planner.py:35-146`; `backend/data_analysis/ai/settings.py:73-133`; `backend/services/calendar_sync_service.py:128-256,345-449`).
- Backup scripts and runbooks exist, but the repository explicitly does not prove a production restore, does not choose RPO/RTO, and never prunes backups. No backup retention period or uptime promise is supportable (`docs/backup-restore-runbook.md:3-15`; `scripts/backup_madar.sh`; `scripts/restore_madar.sh`).

From a role-analysis perspective, Madar is likely an independent controller for platform-account, billing-selection, support, security, and product-operation data. For visitor form and reservation data selected and collected by a tenant, the implementation supports a processor-like role for Madar and a controller-like role for the tenant. Public-site account identities, security telemetry, and Madar-generated operational records create mixed or ambiguous roles. These are technical observations only; the legal allocation requires counsel and customer data-processing terms.

## 2. Audit scope and methodology

### Scope

The audit covered the development checkout only. The production checkout `/home/madar/saas/Madar` was not accessed or modified. The inspection included:

- Git state, architecture, entry points, package manifests, Dockerfiles, Compose, Nginx, configuration names, readiness, backup and deployment documentation.
- All backend route registrations, request models, authentication/session code, tenant authorization, public-site routes, storage code, billing, data analysis/AI, calendars, notifications, workers, logs, rate limiting, and administrative access.
- Frontend routes, legal pages, signup, website runtime, form runtime, pricing, storage APIs, service worker, state persistence, external resources, and exports.
- All Supabase migrations through `066`, including tables, relationships, RLS/grants, cleanup metadata, and lifecycle fields.
- Tests and historical audit documents as corroborating or contradictory evidence only. Tests, comments, and documentation were not treated as proof of deployed behavior.

No external service was queried. No database was queried or altered. No service was started, stopped, rebuilt, or restarted. The local `.env` and backup environment file were not reproduced; only variable names were recorded.

### Evidence labels

| Label | Meaning |
|---|---|
| **Verified** | An active route/component/service traces the behavior to persistence, output, or transmission. |
| **Configuration-dependent** | Active code exists, but environment settings, credentials, deployment topology, or provider configuration determine whether it runs. |
| **Partially implemented** | UI/schema or code exists, but an essential operational or product step is absent. |
| **Test-only** | Demonstrated only in tests or fixtures; not treated as live functionality. |
| **Planned or documented only** | Described in documentation/comments/UI copy but not backed by a complete active flow. |
| **Unknown** | The repository cannot establish the fact. |

Line references identify the inspected commit and may move in later revisions. Duplicate migration trees exist under `database/migrations/` and `supabase/migrations/`; the latter is cited as the canonical schema evidence in this report. `docs/applied-migrations/production.md` records some operator-reported migration facts, but this audit did not independently query the live schema. Therefore all database behavior is “verified in repository code,” while the exact deployed schema remains configuration/operations-dependent.

## 3. Repository branch, commit, and architecture

The initial worktree was clean. The inspected branch was `builder-backend` at commit `78bf6f000a7edb2b98a0cd7aaf61a60f74935734`.

| Layer | Finding | Status | Evidence |
|---|---|---|---|
| Backend | FastAPI application; middleware and routers are assembled in `app`. | Verified | `backend/app.py:17-38,65-69,226-249` |
| Frontend | React 19/Vite single-page application; Nginx serves the built output. | Verified | `frontend/package.json`; `frontend/Dockerfile:1-30`; `frontend/nginx.conf.template` |
| Identity/data | Supabase URL plus anon and service clients support Auth, PostgREST, and Storage. | Verified; destination configuration-dependent | `backend/database.py:34-78,92-127` |
| Database | PostgreSQL/Supabase migrations define tenant, builder, submission, security, billing, notification, storage, and calendar tables. | Verified in repository; live application unknown | `supabase/migrations/001_initial_schema.sql` through `066_normalize_sensitive_object_privileges.sql` |
| Rate limiting | Redis is the normal backing store; production defaults fail closed if unavailable. In-memory fallback is allowed only when configured. | Configuration-dependent | `backend/services/rate_limit_service.py:18-98,220-420`; `docker-compose.yml:2-29` |
| Files | Public builder assets, private datasets, private generated charts, and an avatar directory are durable bind mounts in Compose; profile avatars normally go to Supabase Storage. | Configuration-dependent | `docker-compose.yml:78-97`; `backend/services/upload_config.py`; `backend/routes/user_routes.py:20-91` |
| Workers | Notification and calendar-sync workers exist but use optional Compose profiles/settings. | Configuration-dependent | `docker-compose.yml:100-205`; `backend/workers/notification_worker.py`; `backend/workers/calendar_sync_worker.py` |
| Edge security | Nginx provides CSP, HSTS placeholder, no-sniff, referrer and permissions policies; TLS/HSTS and proxy behavior depend on deployment. | Configuration-dependent | `frontend/security_headers.conf.template:1-7`; `docker-compose.yml:210-254` |
| Hosting/provider | No cloud hosting operator or infrastructure location is established. Cloudflare appears only as a recommendation in a historical review. | Unknown | `docs/full-codebase-review-2026-07.md:885`; no Cloudflare service/SDK found |

Development and production Compose behavior differ: `docker-compose.dev.yml` sets development mode, local ports, and enables calendar features by default; the base Compose sets production mode, secure cookies, bounded JSON logs, and calendar/worker flags off unless configured.

## 4. Product and actor overview

### Current, partial, and planned product areas

| Product area | Current finding | Status | Evidence |
|---|---|---|---|
| Platform accounts | Signup, verification, login, refresh, logout, password reset/change, profile and avatar. | Verified | `backend/routes/auth_routes.py`; `backend/routes/password_routes.py`; `backend/routes/user_routes.py` |
| Tenant workspaces | Tenants and owner/admin/member memberships; all active roles can write builder content, owners/admins manage site members/archive. | Verified | `backend/services/tenant_service.py:15-151`; `supabase/migrations/036_restore_original_signup_foundation.sql:65-110` |
| Website builder | Draft/published JSON schemas, revisions, page/site settings, public binding, upload assets, publish/unpublish/archive. | Verified | `backend/routes/builder_routes.py:1482-2317`; `supabase/migrations/024_create_builder_projects.sql`; `051_bind_public_sites_to_projects.sql` |
| Public sites | Path-based `/site/<subdomain>/` runtime backed by a bound published project, including public/protected pages. | Verified | `backend/routes/public_site_routes.py:307-489,1451-1595`; `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx` |
| Forms/reservations | Public capture, tenant review/status update, anti-spam basics, reservation cancellation and optional email. | Verified | `backend/routes/public_site_routes.py:1597-1975`; `backend/routes/builder_routes.py:1296-1385,2016-2167` |
| Public-site accounts | Visitors can register/login and receive project roles. | Verified, with legal-consent gap | `backend/routes/public_site_routes.py:1284-1475`; migrations `042`, `049`, `057-060` |
| Data workspace | CSV/XLS/XLSX upload, read/clean/analyze/visualize and client/server export. Remote URLs optional. | Verified / configuration-dependent | `backend/data_analysis/routes/`; `backend/data_analysis/services.py:429-530` |
| AI analysis assistant | Gemini planner/code generator; OpenAI/DeepSeek branches explicitly not implemented. | Configuration-dependent; other providers incomplete | `backend/data_analysis/ai/planner.py:35-146`; `backend/data_analysis/ai/settings.py:16-133` |
| Calendars | Calendars, members, events, attendees, reminders, tasks, ICS import/export; feature flag. | Configuration-dependent | `backend/routes/calendar_routes.py:696-1337`; migration `061-065` |
| Calendar synchronization | Google and Microsoft OAuth/event sync; CalDAV and ICS are schema provider values, but no CalDAV connector was found. | Google/Microsoft configuration-dependent; CalDAV partial | `backend/services/calendar_sync_service.py:128-449`; `supabase/migrations/061_create_calendar_platform.sql:158-181` |
| Notifications | In-app, SMTP email, and Web Push queue/delivery. Worker optional. | Configuration-dependent | migrations `038`, `047`; `backend/services/notification_delivery_service.py` |
| Billing | Manual plan selection and admin-set feature/payment state. | Partially implemented | `backend/routes/billing_routes.py`; `backend/services/billing_service.py` |

### Actor and permission matrix

| Actor | Submit/create | View | Edit/delete/export | Administrative or cross-person access | Logging |
|---|---|---|---|---|---|
| Unauthenticated Madar visitor | Public contact: name, optional phone, message. Can browse public marketing/legal pages. | Public marketing, privacy, terms. | No contact deletion/export. | None. | Contact result, client IP and metadata are logged; contact row is stored (`backend/routes/public_contact_routes.py:14-88`). |
| Registered platform user | Identity/profile, tenant settings, builder content, uploads, forms, data files, calendar content, plan requests. | Own account and active tenant data. | Profile changes; builder save/publish; dataset/report/calendar exports. A form-response-to-CSV import path exists only for responses already embedded in the project object; active backend wiring was not verified. No self account deletion/full export. | Access depends on tenant role. | Auth/security, builder, billing and calendar events are partly audited. |
| Tenant owner/admin | Same as member; manages site users and project archive. | All tenant submissions/reservations and tenant builder data. | Can update status, site users/roles; archive projects. No submission/reservation hard delete. | Can see visitor names, emails, phones, arbitrary answers, IP and UA in stored records/API. | Role, site-user, publish, upload, record-status actions audited. |
| Tenant member | Can create/edit/publish builder content because `require_builder_write_access` includes `member`. | All tenant form submissions/reservations, not merely own. | Status update and data exports; cannot archive/manage site members. | Can access visitor personal information for tenant. | Some mutations audited; ordinary reads are not individually audited. |
| Madar system administrator | Admin profile; billing/status and user-role actions. | Paginated users: IDs, auth IDs, tenant IDs, names, email, phone, avatar, verification/account/billing state. | Promote/demote users, delete users, set billing features. | AAL2 required for sensitive admin routes. | Admin changes are audited (`backend/routes/admin_user_routes.py:16-123`). |
| Support/account-access administrator | Requests a code emailed to target; after code verification can act as a non-admin target for 30 minutes by default. | Target account/tenant data allowed by routes that permit account access. | Many write routes explicitly reject support access; read availability varies by route. | Separate signed, HttpOnly cookie bound to admin, target, DB session, expiry and user-agent hash. | Request, failures, start/end audited; request/session rows persist without defined retention (`backend/services/admin_account_access_service.py:280-643`). |
| Published-site visitor | Views public pages/resources; can submit public forms/reservations. | Public site and form schema. | Can cancel a reservation with a time-limited token; cannot delete data or export it. | None. | IP/UA stored with submissions/reservations; spam/rate-limit events logged. |
| Registered published-site visitor | Full name, email and password; protected forms/pages/reservations. | Authorized protected resources. | No own-record view after migration `060`; no self-service account deletion. | Project role controls protected resources. | Registration/login/security events are limited compared with platform signup; no Terms acceptance record. |
| Form submitter | Arbitrary tenant-defined answers; file metadata if a file field is used. | Submission confirmation only. | No access, correction, export or delete workflow. | Tenant staff can view. | IP/UA stored; content is not intentionally placed in structured application logs. |
| Reservation submitter | Arbitrary payload, commonly name/email/phone/service/date/time. | Confirmation and cancellation result. | Cancellation changes status; no deletion/export. | Tenant staff can view. | IP/UA stored; payload duplicated to internal notification data. |
| Billing customer | Plan/subscription/builder selection. | Current feature state. | Can request a plan; no payment cancellation/refund portal. | Admin can activate/change state. | Plan choice and admin updates audited. |
| Background process | Notification delivery, calendar reminders/sync, asset reconciliation/cleanup. | Service-role database access within code path. | Mutates queues/provider sync records and can delete expired unreferenced asset files only when cleanup is run with apply. | Privileged service-role access. | Operational events/errors logged; no human actor. |
| External provider | Receives data described in section 9. | Provider-dependent. | Provider retention/control is outside repository. | Supabase/SMTP/push/AI/calendar providers process user data when invoked. | Application logs provider result/error type, not credentials. |

## 5. Complete personal-data inventory

The table below reports active or configuration-dependent processing. “No user notice” means no specific disclosure beyond the current short legal pages was found.

| Category and exact fields | Source and purpose | Storage | Access and recipients | Retention/deletion | Logs, sensitivity, necessity, notice | Status/evidence |
|---|---|---|---|---|---|---|
| Platform identity: `first_name`, `last_name`, `email`, optional `phone`, `avatar`, numeric `id`, Supabase `auth_id`, `tenant_id`, `user_type`, account kind/status, timestamps | Signup/profile; identify, authenticate and authorize | Supabase Auth plus `public.users`; avatar URL; public avatar bucket | User, tenant-context APIs, Madar admins; Supabase | Admin deletion only; auth cascade; no self-service rule | High identity sensitivity; IDs in logs/audit, email generally hashed in audit. Broadly mentioned, not field/lifecycle detail | Verified: `supabase/migrations/001_initial_schema.sql:1-10`; migrations `023`, `040-043`, `048`; `backend/classes.py:10-42` |
| Passwords and auth tokens | Password sent server-side to Supabase Auth for create/login/change/reset; access/refresh tokens in cookies | Password representation is in Supabase Auth, not `public.users`; tokens in HttpOnly cookies; pending MFA cookie temporarily contains encrypted access/refresh tokens | Supabase and authenticated browser; backend | Session inactivity default 1 hour; provider token lifetime/revocation configuration unknown; logout clears cookies | Highest sensitivity; application does not intentionally log values; provider hashing/settings unknown. Password collection is necessary and not explained in policy | Verified/configuration-dependent: `backend/routes/auth_routes.py:342-355,780-1027`; `backend/services/auth_service.py:94-218`; `backend/services/mfa_login_service.py:18-111` |
| Verification/reset: verification flags/timestamps/resend count, pending email, email hash, provider/message status, requester IP hash, reset nonce hash/status/times | Verify accounts, rate-limit/reconcile delivery, reset passwords | `users`, `email_verification_attempts`, `password_reset_requests`; Supabase Auth | Backend/service role; Supabase email service | Expiry/state fields; no general row cleanup found. Pending account default 14 days, cleanup script not scheduled | Security-sensitive; tokens hashed; provider failures logged by type. Not disclosed | Verified: migration `043_create_account_lifecycle.sql:6-167`; `backend/services/email_verification_service.py`; `backend/routes/password_routes.py` |
| Terms acceptance: `terms_accepted_at`, `terms_version` | Establish platform signup acceptance | `users` | Madar backend/admin DB access | Until user deletion; no version history beyond current pair | Necessary contractual evidence; not described in policy. Public-site registration omits it | Verified/partial: `backend/routes/auth_routes.py:316-321,379-399`; migration `048` |
| MFA: factor IDs/types/friendly names and assurance levels at Supabase; `mfa_required`, enrollment/verification timestamps, `last_aal2_at` locally | Account security/AAL2 | Supabase Auth MFA; `user_security_settings`; short-lived MFA cookie | User, backend, admins for requirement setting | Factor removal supported; local security row cascades with user | Very sensitive; factor IDs may be audited, secrets/tokens excluded. Current policy only says security broadly | Verified: migration `033_create_user_security_settings.sql`; `backend/routes/mfa_routes.py`; `backend/services/user_security_settings_service.py` |
| Tenant/business: brand/business/owner name, business type, membership role/status/auth IDs, selected/requested subdomain | Provision workspace, display site, authorization | `tenants`, `tenant_memberships`, pending onboarding, `website_settings` | Active tenant users; Madar admin; public site exposes selected profile fields | Tenant may be deleted only by admin user-deletion cascade; no self-service lifecycle | Business data can identify sole traders. Policy mentions tenant profile and website settings but not roles/onboarding retention | Verified: migrations `036`, `043`; `backend/routes/auth_routes.py:379-520`; `backend/routes/website_routes.py` |
| Website profile: subdomain, brand, footer store name, logo URL, public contact email/phone/description, bound project ID | Configure and serve customer site | `website_settings` | Tenant staff; public visitors receive configured profile | No dedicated delete; tenant cascade/settings relationships; published binding restricts project delete | Public by purpose; customer must understand publication. Mentioned only generally | Verified: `supabase/migrations/003_create_website_settings.sql:1-12`; `051:3-18`; `backend/routes/public_site_routes.py:539-548` |
| Builder content: project owner/name/slug/status, draft/published schemas, pages, text, forms, roles, workflows, external URLs, revisions/timestamps | Author and publish sites/forms | `builder_projects`; full draft also in browser localStorage/recovery; published subset publicly served | Tenant members; public receives authorized published schema; support access may read permitted routes | Project “delete” archives; no physical delete API. Browser copy cleared after confirmed save in some flows, but legacy/recovery may remain | Potentially contains personal/confidential data. Schema excluded from audit metadata. Policy underdescribes browser copies and publication | Verified: migration `024`; `backend/routes/builder_routes.py:1482-2317`; `frontend/.../useDebouncedProjectStorage.js:35-229` |
| Uploaded builder assets: bytes, original filename, randomized filename, MIME, size, SHA-256, uploader ID, reference paths | Site images | Public local mounted storage plus `builder_assets`, `builder_asset_references`, quota tables | Anyone knowing public URL; tenant staff; backend | Referenced indefinitely; unreferenced gets 7-day eligibility, but deletion needs an operational cleanup run | Original filename is DB-only; public filename random. Upload audit has URL/type/size. Policy says assets but not public nature/cleanup qualification | Verified/operationally dependent: `backend/routes/builder_routes.py:1149-1287`; `backend/services/asset_registry_service.py:20-99` |
| Avatars: image bytes, public URL, randomized filename under auth-ID path | Profile display | Public Supabase `avatars` bucket | Public internet; Supabase | Replaced old in-bucket avatar is best-effort removed; account deletion does not explicitly remove avatar storage object | Biometric-like image sensitivity depends on content. Public nature not disclosed | Verified: `backend/routes/user_routes.py:20-110,247+`; migration `022` |
| Madar public contact: name, optional phone, message, created time | Marketing/support contact | `contacts` | Service-role/backend; no customer-facing retrieval route found | No deletion/retention workflow | Message may contain sensitive free text; client IP used/rate-limited and passed to logs but not stored in table. Privacy intro mentions support, not exact flow | Verified: `backend/classes.py:5-8`; `backend/routes/public_contact_routes.py:14-88`; migrations `001`, `010`, `011` |
| Form definitions: arbitrary labels, types, options, help/default/required values, file constraints | Tenant designs collection | Builder schema | Tenant members; published form visitors | Follows builder project retention | Can solicit sensitive data; no blocklist or dedicated consent field. Necessary only as customer chooses. No submitter-facing Madar notice | Verified: `frontend/.../PageBuilder.constants.js:121-131`; `backend/routes/public_site_routes.py:501-555,1055-1095` |
| Form submissions: answers JSON, quiz result, field snapshot, form/project/tenant IDs, status, timestamps, `submitter_ip`, `user_agent`, idempotency/request hashes, optional site user/membership IDs | Receive and manage visitor response, prevent duplicates/security | `builder_form_submissions`; sessionStorage response cache in staff browser | All active tenant members via API; Supabase backend; support access may read depending route | No record deletion; tenant/project physical cascade only; response cache up to 30 entries and 6-hour usability within browser session | High/unknown sensitivity because arbitrary fields. Answers deliberately excluded from audit sanitizer and structured log labels. Current policy mentions submissions but not IP/UA, access, retention, or tenant role | Verified: migrations `027`, `054`, `059`; `backend/routes/public_site_routes.py:1597-1713`; `frontend/.../responsesCache.js:1-117` |
| Form file fields: filename, size, browser MIME type only | Provide visible file selection metadata in a form | Stored as form answer JSON; file bytes are not uploaded | Tenant staff | Same as submission | Filename may identify person/content. UI note explains runtime behavior; policy does not | Verified: `TenantSiteRuntime.jsx:1380-1408` |
| Reservations/events: customer name/email/phone, service/date/time, start/end/timezone, arbitrary payload and field snapshot, status, tenant/project/block/site IDs, IP, UA, idempotency/request/cancellation hashes and expiry, cancellation time, site IDs | Booking request, notification, cancellation, collision prevention | `builder_reservations`; payload copied into notification outbox/event/user notification data | Active tenant members; SMTP provider receives email and minimal status/message; Supabase | Cancellation is status change; no hard delete/retention. Cancellation token default 30-day validity | High sensitivity and duplicates increase retention surface. Current policy does not mention reservations at all | Verified/configuration-dependent delivery: migration `044`, `046`, `059`; `public_site_routes.py:1716-1975` |
| Public-site account: full name split to first/last, email, Supabase password identity, IDs, account kind/status, tenant-site role/status/source | Authenticate protected customer pages/forms/reservations | Supabase Auth, `users`, `tenant_site_memberships`, project role assignments | Visitor; tenant site managers; Madar administrators | Site membership can be removed by owner/admin; user identity remains unless admin-deleted. No self-delete | High identity sensitivity; no Terms acceptance or dedicated notice | Verified with gap: `public_site_routes.py:1284-1475`; migrations `042`, `049`, `057-060` |
| Notifications: event title/body/data, read time, source, user/tenant IDs; outbox template/payload/status/attempts/errors/times; recipient hash/reference | In-app/email/push delivery and retry | `notification_events`, `user_notifications`, `notification_outbox` | Tenant staff recipients; backend worker; external SMTP/push service | `retention_until` defaults 90 days for outbox, but no deletion job found; other notification tables no rule | Can duplicate reservation/calendar details. Not disclosed | Verified/worker configuration-dependent: migrations `038`, `047`; `notification_outbox_service.py:34-97`; `notification_delivery_service.py` |
| Push subscription: endpoint, P-256 key, auth secret, user/tenant, user agent, timestamps/revocation | Browser Web Push | `web_push_subscriptions` | Backend and browser-selected push service | User can delete subscriptions; 404/410 marks revoked; no purge rule | Unique endpoint is an online identifier; user is prompted by browser, not legal notice | Configuration-dependent: `backend/routes/notification_routes.py:88-130`; `frontend/src/services/notificationsApi.js:90-134` |
| Calendar content: calendar names/colors/timezones/visibility; event title/description/location/times/status/recurrence; attendee emails/names/responses; tasks/descriptions/owners/dates; reminders; before/after change history; invitation sender/reasons | Team calendar/task operation, audit/history, reminders | Calendar tables; full workspace cached in sessionStorage for five minutes | Tenant/calendar roles; Google/Microsoft when sync enabled; SMTP/push for reminders | Event delete is soft (`deleted_at`); children can be replaced/deleted; tenant/calendar cascades; no time retention | High personal/work-pattern data. Entirely absent from current policy | Configuration-dependent: migrations `061-065`; `calendar_routes.py`; `calendarWorkspaceCache.js:1-75` |
| Calendar integration data: provider, account label/external account ID, encrypted access/refresh credentials, sync cursors/errors, local/remote conflict JSON, OAuth nonce hash/bindings | Connect/synchronize external calendar | `calendar_sync_connections`, conflicts, OAuth states | Backend and Google/Microsoft | Disconnect tries provider revocation and deletes connection; OAuth state has expiry/consumed time but no cleanup rule | Credentials encrypted with application key; provider data transmission not disclosed | Configuration-dependent: `calendar_sync_service.py`; migrations `061`, `065` |
| Dataset uploads: original filename returned to browser, randomized private path, size/hash/format, column names, preview/sample values, rows/counts, full CSV/XLS/XLSX bytes | Analyze/export user data | Private tenant/user local mounted files; `storage_objects` metadata; browser memory/local metadata/optional IndexedDB full copy | User-scoped authenticated routes; Supabase quota metadata; Gemini may receive profile/sample subset | No server file delete/retention API; browser manual clear/delete only | May contain any sensitive data. Logs size/mode/counts and IDs, not filename/content. Policy does not mention datasets | Verified: `backend/data_analysis/services.py:400-530`; migration `056`; `datasetStorage.js` |
| Generated charts/reports/cleaned exports | User analysis output | Private generated chart directory; browser report state/download | Authenticated scoped user; local browser | No server retention/delete found; exports saved by user locally | Derived data can remain personal. Not disclosed | Verified: data-analysis routes/services; `README.md:165-181` |
| AI inputs/usage: user instruction, allowed column names, compact/full profiles and sampled approved values; user/tenant/date usage counts/reservations | Generate analysis plan/code, enforce quota | Prompt sent to configured Gemini; usage tables store counts/status, not prompt text | Google Gemini and backend | Provider retention unknown; local usage rows no cleanup | Potentially high sensitivity even with heuristic sensitive-column filtering. Not disclosed; AI use should be optional/clearly explained | Configuration-dependent: `planner.py:35-146`; AI prompt/profile services; migration `037` and `039` |
| Billing selection/state: tenant, subscription type, plan, builder type, payment status/state-change times; development event IDs/hash/status | Manual access request and admin activation | `features`, `billing_webhook_events`; some legacy summary fields on `users` | Tenant staff and Madar admin | No cancellation/retention workflow; billing events intentionally survive tenant deletion because no FK | No financial instrument data. Current terms incorrectly sounds like a subscription checkout could be live | Verified/partial: migration `016`, `045`; `billing_routes.py` |
| Security/audit telemetry: action, target, actor/tenant IDs, sanitized metadata, IP, user agent, timestamps; request route/method/status/latency/request ID; rate-limit keys | Fraud/security, accountability, troubleshooting | `audit_logs`; process/Docker logs; Redis or memory counters | Madar operators/admin backend; metrics endpoint protected by token/loopback | Audit: no defined retention. Docker JSON logs rotate by size/file count, not time. Redis keys expire with window | IP/UA personal/technical data. Structured formatter removes arbitrary extra fields, but DB audit intentionally stores raw IP/UA. Current policy only broadly says operational logs | Verified/configuration-dependent: `audit_service.py:9-133`; `observability_service.py:1-219`; `docker-compose.yml` |

No geolocation, ad identifiers, behavioral analytics, card number, CVV, bank account/IBAN, billing address, tax ID, invoice, refund, or payment-provider customer/subscription/checkout ID processing was found.

## 6. Cookies and browser-storage inventory

### Cookies

All listed cookies are first-party application cookies in the inspected code. `Domain` is not set, so the browser defaults to the setting host. All use path `/` except the MFA-pending cookie. Secure and SameSite values are configuration-dependent: production requires `Secure=true`; base Compose uses `SameSite=None`, while code default is `Lax`. No cookie banner or preference center was found. These cookies are functional/security cookies rather than analytics cookies.

| Cookie | Purpose/content | HttpOnly / JS | Lifetime | Logout/revocation | Status and evidence |
|---|---|---|---|---|---|
| `madar_access_token` | Supabase access token | Yes / no | Session cookie; token expiry provider-defined | Cleared on logout/session failure; server-side provider revocation on logout is not clearly proven | Verified: `auth_service.py:194-239,313-390` |
| `madar_refresh_token` | Supabase refresh token | Yes / no | Session cookie; provider lifetime unknown | Cleared with auth cookies | Verified: same |
| `madar_csrf_token` | Signed, session-bound CSRF token; echoed in `X-CSRF-Token` | No / yes | Cookie session; signed payload defaults to 900 seconds | Cleared on logout; refreshed with auth cookies | Verified: `request_security.py:14-36,166-205`; `frontend/src/utils/apiClient.js:13-25` |
| `madar_session_activity` | Signed last-activity timestamp for app inactivity timeout | Yes / no | Session cookie; validity defaults to 3,600 seconds | Cleared on logout; updated during authenticated activity | Verified: `auth_service.py:94-190` |
| `madar_pending_verification` | Signed pending auth/user identity context | Yes / no | Persistent; default 14 days via `max_age` | Explicit clear route and successful lifecycle clear it | Verified: `pending_verification_context.py:15-18,44-118` |
| `madar_mfa_pending` | Encrypted short-lived pending access/refresh/auth/user/tenant data during login MFA | Yes / no | 300 seconds; path `/auth/mfa/login` | Deleted after verification/failure flow | Verified: `mfa_login_service.py:18-111` |
| `madar_admin_access_session` | Signed admin/target/session IDs and nonce, backed by hashed DB token | Yes / no | Default 30 minutes (`max_age`) | End route and normal logout clear it; DB session can be ended/expire | Verified: `admin_account_access_service.py:24-28,205-245,472-643` |

The current Privacy Policy statement is therefore **inaccurate by omission**. It correctly says the frontend has no analytics/payment SDK cookies, but “authentication and CSRF cookies” does not describe the activity, pending-verification, MFA-pending, or administrator-access cookies. No third-party cookie is directly set by Madar code, but external pages/embeds may set or read cookies in their own contexts.

### Browser and edge storage

| Mechanism/key | Stored information and purpose | Duration/clear behavior | Notice/consent | Evidence |
|---|---|---|---|---|
| localStorage `madar-theme-mode` | Light/dark/system preference | Indefinite until changed/browser-cleared | No notice | `frontend/src/utils/themeMode.js:1-55` |
| localStorage `madar.language` | English/Arabic preference | Indefinite | No notice | `frontend/src/i18n/index.js:110-240` |
| localStorage `madar_app_builder_frontend_v4`, scoped keys and `:backup`/recovery keys | Potentially complete customer builder project/draft schema | Autosave; some values cleared after confirmed cloud save; recovery/legacy copies can remain | No legal notice | `PageBuilder.constants.js:1-5`; `useDebouncedProjectStorage.js:35-229`; `PageBuilder.recovery.js` |
| localStorage starter-modal dismissal | UI choice | Indefinite | No notice | `PageBuilder.jsx:452` |
| localStorage data-workspace cache | Dataset metadata/state; legacy preview data is removed during migration; 24-hour usability | Stale entry removed on read; browser may retain until read/clear | No notice | `dataAnalysis.helpers.js:561-656` |
| sessionStorage `madar.pending-verification-email` | Full pending email address | Browser tab/session or explicit clear | No notice | `AuthPages/emailVerification.js:1-44` |
| sessionStorage `madar-builder-responses-cache-v1` | Form response records and pagination | Up to 30 entries; usable six hours, storage lasts browser session | No notice | `responses/utils/responsesCache.js:1-117` |
| sessionStorage `madar-calendar-workspace-cache-v1` | Calendars and full event workspace for date range | Five-minute usability; max 24 entries; browser session | No notice | `DashboardBuilder/utils/calendarWorkspaceCache.js:1-75` |
| IndexedDB `madar-sensitive-data` (`datasets`, `archive_items`) | Full files/datasets and archived report items | Until manual clear/delete/browser storage removal; no automatic expiry | No notice; optional password is the only trigger for AES-GCM encryption | `datasetStorage.js:1-213` |
| Service worker `/madar-push-sw.js` | Receives notification payload, displays notification, handles click | Browser registration until unregistered; no explicit unregister workflow found | Browser notification permission is requested | `frontend/public/madar-push-sw.js:1-45`; `notificationsApi.js:90-134` |
| BroadcastChannel | Cross-tab builder save/recovery coordination; transient messages | Memory/session only | Not applicable | `useDebouncedProjectStorage.js:61-82`; `PageBuilder.jsx:1109-1120,3390+` |
| Clipboard | User-triggered public/form links or QR image copy | OS/browser clipboard | User action | `PageBuilderPublishTab.jsx:72-118` |
| HTTP cache | Public site response uses ETag with revalidation; protected response `private, no-store` | Browser/proxy dependent | No consent required for functional cache | `public_site_routes.py:462-498` |

No application use of browser Cache Storage, analytics identifier storage, or an authentication SDK’s browser persistence was found. The frontend does not instantiate Supabase directly.

## 7. Database and file-storage inventory

### Database tables

Later migration `066_normalize_sensitive_object_privileges.sql` enables RLS and normalizes grants on sensitive objects. Most application writes use the service role after backend authorization. The exact live policy/grant state was not queried; source-level RLS is not proof of production state.

| Table | Purpose and personal/tenant data | Isolation/access and foreign-key deletion | Retention, soft delete, export |
|---|---|---|---|
| `users` | Identity, contact, auth/tenant IDs, roles, verification/lifecycle, billing summary, Terms acceptance | Own-row/privilege hardening in later migrations; auth deletion cascades to local row; tenant FK set null | Admin delete only; no full export |
| `contacts` | Public name, phone, message, time | Backend/service role after hardening | No defined retention/delete/export |
| `tenants` | Brand and owner name | Tenant membership RLS; tenant deletion cascades broadly | Admin-assisted cascade only |
| `tenant_memberships` | Tenant/user/auth IDs, owner/admin/member, status | Tenant/user/auth cascade; backend checks active membership | Membership deletion through tenant/user lifecycle; no user UI found |
| `website_settings` | Public site profile and bound project | Tenant-scoped; project binding `ON DELETE RESTRICT` | No dedicated delete; public output by purpose |
| `features` | Plan/builder/payment state | Tenant cascade; admin/service mutation | No cancellation retention; tenant cascade |
| `builder_projects` | Owner, name/slug/status, complete draft/published JSON and revisions | Tenant cascade; owner set null; active member access with role checks | Archive soft state; no hard-delete route; data export only indirectly through browser/schema |
| `builder_form_submissions` | Answers, snapshots, IP/UA, site ownership, hashes/status | Tenant/project cascade; site user/membership set null; backend-only after hardening | No record delete. A client-side CSV-to-dataset path exists for project-embedded responses, but current backend response wiring into that path was not verified; no retention |
| `builder_reservations` | Identity/contact, timing, payload, IP/UA, cancellation metadata | Tenant/project cascade; site user/membership set null | Status cancellation; no delete/export/retention |
| `audit_logs` | Actor/tenant/action/target/metadata/IP/UA/time | RLS/service-role; actor and tenant `ON DELETE SET NULL`, preserving record | No defined retention/export |
| `user_security_settings` | MFA requirement/enrollment/AAL2 times | User cascade; service role | Factor actions supported; row user cascade |
| `admin_account_access_requests` | Admin/target/email, code hash, attempts/expiry/use/revocation, UA hash | Both user FKs cascade; service-role only | Expiry/revocation state, no purge |
| `admin_account_access_sessions` | Admin/target/session-token hash, expiry/end, UA hash | User FKs cascade; request set null; service-role only | Default 30-minute active period, no purge |
| `ai_usage_daily` | User/tenant/day and message/code counts | User/tenant cascade; service-role | No retention/export |
| `notification_events` | Tenant event title/body/data/source | Tenant cascade; service-role | No defined retention |
| `user_notifications` | Per-user copy/read status/data | Event/tenant/user cascade | User can mark read, not delete; no retention |
| `web_push_subscriptions` | Endpoint, push keys, UA, user/tenant, revocation | User/tenant cascade; service-role | User delete endpoint/revocation; no purge |
| `notification_outbox` | Delivery payload, recipient hash/reference, status/errors/times | Tenant cascade, user set null; service-role | `retention_until` default 90 days but no deletion implementation |
| `tenant_site_memberships` | Public-site user/auth/role/status/source | Tenant/user/auth cascade | Tenant admin can remove membership; underlying user may remain |
| `tenant_site_project_roles` | Project role names/capabilities and deleted time | Tenant/project cascade | Soft `deleted_at`; no general retention |
| `tenant_site_project_role_assignments` | Site membership/project/role assignment, assigning user | Membership/project cascade; role restrict; assigner set null | Removed with membership/project |
| `email_verification_attempts` | Email/IP hashes, provider/message status/error and times | User/auth set null to preserve attempt | No purge; export absent |
| `pending_account_onboarding` | Business/subdomain/plan and expiry/provision state | Auth/user cascade, tenant set null | Default 14 days while pending; cleanup operational script not scheduled |
| `password_reset_requests` | User/auth, nonce hash, status and lifecycle times | User/auth cascade | Expiry/status, no purge |
| `billing_webhook_events` | Synthetic provider/event IDs, tenant number, hashes/status/times | Deliberately no tenant FK so replay evidence survives tenant removal | No retention/export |
| `builder_assets` | Original/random filename, MIME/size/hash/uploader, state/references/retention | Tenant cascade; project/uploader set null; service role | Unreferenced seven-day eligibility; cleanup job required; soft-deleted registry remains |
| `builder_asset_references` | Asset/project/reference path | Asset/project cascade | Reconciled on save/archive |
| `storage_accounts` | Tenant/user quota/used/reserved bytes | Tenant/user cascade | Accounting record; no export |
| `storage_reservations` | Tenant/user/category/bytes/status/expiry | Tenant/user cascade | Expired reservation reconciliation |
| `storage_objects` | Tenant/user/category/storage key/size/hash/status/retention | Tenant cascade; user/reservation set null | Dataset objects have no retention date; release operation exists but no dataset delete route |
| `calendars` | Name/color/timezone/visibility/owner | Tenant cascade; owner set null | No calendar delete route found; tenant cascade |
| `calendar_memberships` | Calendar/user role | Calendar/tenant/user cascade | Replace/update supported |
| `calendar_events` | Full event content, recurrence, source, project, timestamps | Calendar/tenant cascade; users/projects set null | Soft delete via `deleted_at`; ICS export |
| `calendar_event_attendees` | Email/name/response | Event/tenant cascade | Replaced during event edits; no time retention |
| `calendar_event_reminders` | Channel/timing/delivery state | Event/tenant cascade | Replaced/deleted with event/reminder edit; no retention |
| `calendar_event_changes` | Before/after JSON and actor | Event/tenant cascade; actor set null | History export via event API; no retention |
| `calendar_tasks` | Task text/owner/times/status/priority | Tenant cascade; calendar/project/owner set null | Update but no dedicated hard-delete route found |
| `calendar_task_dependencies` | Task relationships | Task/tenant cascade | Cascade |
| `calendar_task_reminders` | Channel/time/delivery state | Task/tenant cascade | Can be deleted during reminder update; no retention |
| `calendar_sync_connections` | Provider/account IDs, encrypted credentials, cursor/errors | Tenant/user/calendar cascade | Disconnect attempts provider revocation and deletes connection |
| `calendar_sync_conflicts` | Local/remote event JSON and resolution | Tenant/connection/event cascade | Resolve status; no retention |
| `calendar_invitation_reviews` | Sender email, trust reasons/disposition | Tenant cascade; event cascade | Review update; no retention |
| `calendar_oauth_states` | Hashed nonce and tenant/user/calendar/provider bindings | Connection/tenant/user/calendar cascade | Single-use expiry fields; no cleanup job |

### Storage behavior

1. **Builder assets — Verified public local storage.** Authenticated tenant members upload PNG/JPEG/WebP up to `BUILDER_ASSET_MAX_BYTES` (base Compose 5 MiB). Magic bytes and declared MIME must agree. Files are randomized with 32 hex characters, tenant-scoped, registered with a SHA-256 hash, and served without authentication. References are reconciled from the builder schema. Unreferenced assets become eligible after seven days; the cleanup service defaults to dry-run and no recurring cleanup schedule is in Compose (`backend/routes/builder_routes.py:1149-1287`; `backend/app.py:191-223`; `asset_registry_service.py:20-99`).

2. **Avatars — Verified public Supabase Storage.** The `avatars` bucket is public and limited to PNG/JPEG/WebP and 5 MiB. The backend uses a random filename under `users/<auth_id>/`. Replacing an avatar best-effort removes the prior object if it belongs to the same auth path. User deletion does not explicitly remove the bucket object (`supabase/migrations/022_create_avatars_storage_bucket.sql:12-37`; `backend/routes/user_routes.py:20-110,247+`).

3. **Datasets — Verified private local storage.** CSV/XLS/XLSX files are streamed to tenant/user directories with random filenames. Base defaults allow dataset files up to 200 MiB and Excel up to 50 MiB. Storage quota metadata is written, but no `retention_until` is supplied and no user deletion endpoint for the file exists. Routes authorize the user and path. Remote URL reading is disabled by default (`ALLOW_REMOTE_DATASET_URLS`) and guarded against private-network targets/unsafe schemes when enabled (`backend/data_analysis/services.py:429-530`; `backend/data_analysis/io/data_reading.py`; `README.md:165-181`).

4. **Generated charts — Verified private local storage.** These are served only through authenticated user-scoped routes and must not be mounted under the public directory. No expiration/deletion workflow was found (`backend/app.py:71-83`; `backend/services/upload_config.py`; data-analysis visualization routes).

5. **Browser datasets — Verified.** IndexedDB can store complete files/data. Encryption is optional and only used when the caller supplies a password; otherwise the value is stored in plaintext in browser storage (`datasetStorage.js:64-175`).

6. **Backups — Tooling verified, execution unknown.** The backup script includes database dump, builder assets, private uploads, private generated artifacts and local avatars. It generates a checksum manifest and never prunes older backups. The runbook directs operators to encrypted off-site storage but expressly says this is not proof of production restore and leaves retention/RPO/RTO undecided (`docs/backup-restore-runbook.md:3-15`).

## 8. Public-site, form, and reservation data flows

### Published-site lifecycle

```text
tenant member creates/edits JSON draft
→ backend tenant/session/CSRF authorization and schema/URL validation
→ builder_projects.draft_schema + local browser recovery copies
→ publish checks revision and optional entitlement
→ published_schema/version/status
→ website_settings.published_project_id binding
→ public /sites/{subdomain} route resolves only the bound published project
→ backend removes private top-level keys and unauthorized pages/forms
→ React tenant runtime renders content and external resources
→ unpublish changes status only; archive changes status and releases asset references
```

Evidence: `backend/routes/builder_routes.py:1482-2317`; `backend/routes/public_site_routes.py:307-555,1451-1595`; migrations `024`, `045`, `051-052`.

Published content can contain external HTTPS image/media/link URLs and a YouTube embed. Starter schemas hotlink Unsplash. The server validates supported URL fields and production HTTPS requirements, while visitors’ browsers contact those hosts directly (`backend/services/url_validation.py`; `frontend/src/components/PageBuilder/core/PageBuilder.starters.js:209-899`; `frontend/src/styles/core/base.css:1`).

Customer sites do not automatically link to Madar’s Privacy Policy or Terms. Footer links resolve customer-created page names/internal paths, and a fixed “Powered by Madar” link is rendered. Customers can create ordinary pages named Privacy/Terms, but no dedicated legal-page field, notice template, mandatory link, policy acceptance, or versioning feature was found (`TenantSiteRuntime.jsx:2134-2177`).

### Public form flow

```text
tenant defines fields in project schema
→ project publish makes referenced form definition public
→ visitor browser renders fields
→ POST answers + honeypot + elapsed time + optional idempotency key
→ rate limit and simple honeypot/minimum-time check
→ server checks published bound form, resource permission, size/count, known field IDs and required presence
→ answers, field snapshot, IP, user agent, project/tenant/form/site-user metadata stored in Supabase
→ tenant staff list/read/update status
→ browser may session-cache responses
→ no record-level delete, submitter access, or retention expiry
```

The backend limits forms to 100 answer fields, individual strings to 5,000 characters, and answer JSON to 64 KiB. Validation does not enforce semantic field types or block health, financial, identity-document, child, biometric, or other sensitive questions. A checkbox group can be labeled as consent, but there is no dedicated consent record/version/time/notice field. File inputs transmit metadata only. No CAPTCHA or external spam service is used; protection is rate limiting, honeypot, elapsed time, known-field validation and idempotency (`public_site_routes.py:45-68,143-180,1055-1095,1597-1713`).

No notification email or external CRM forwarding is implemented for forms. An internal tenant notification is queued. No form answer encryption at the application layer is implemented; transport/database encryption depends on Supabase/deployment.

### Reservation flow

```text
tenant publishes reservation block and arbitrary configured fields
→ visitor submits payload
→ rate limit, honeypot/time, size and published-block/role checks
→ server extracts common identity/timing fields but preserves arbitrary payload
→ atomic reservation insert with IP/UA, idempotency and optional slot exclusivity
→ cancellation token returned once; only HMAC hash stored, default validity 30 days
→ payload duplicated into tenant internal notification
→ optional SMTP confirmation and later status email through durable outbox
→ tenant staff view/update status
→ token cancellation sets status/cancelled_at; no deletion
```

Evidence: `public_site_routes.py:1716-1975`; `builder_routes.py:1296-1385`; migrations `044`, `046`, `059`.

### Technical role observations

| Flow | Likely technical role facts for legal analysis |
|---|---|
| Madar marketing contact | Madar determines fields/purpose: independent-controller characteristics. |
| Platform account, security, billing selection, audit | Madar determines core purpose/means: independent-controller characteristics. |
| Tenant website content | Tenant determines content/publishing; Madar hosts and operates it: processor/service-provider characteristics plus Madar’s own security/operations data. |
| Visitor form/reservation answers | Tenant defines fields and business purpose; Madar stores and exposes them to tenant: strong processor characteristics. Tenant likely needs its own notice and legal basis. |
| Submitter IP/UA, anti-abuse and platform logs | Madar independently chooses some collection/security uses: separate or mixed controller characteristics. |
| Public-site accounts | Tenant needs account-gated site access while Madar supplies shared global identity/security: role is joint/ambiguous and requires legal allocation. |
| AI/calendar/push integrations | Tenant/user initiates optional provider transfer; contractual controller/processor allocation and subprocessor terms remain unknown. |

No final controller/processor determination should be published without counsel and provider/customer contract review.

## 9. Third-party service and subprocessor inventory

| Service | Purpose, data and trigger | Direction / configuration | Status | Current notice and policy implication |
|---|---|---|---|---|
| Supabase | Auth receives emails, names metadata, passwords, sessions, MFA and verification/reset actions. Postgres/PostgREST stores all relational content. Storage hosts public avatars. | Server-side; `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` | Verified core provider; region/location unknown | Named only generally. Must disclose categories, Auth/DB/Storage roles, international location based on actual project, and retention/contract facts |
| SMTP provider (identity unknown) | Target email and one-time admin permission code; reservation recipient/status; calendar reminder title/body | Server-side; `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS` | Configuration-dependent | Not named. Provider/legal entity/location must be supplied; likely subprocessor |
| Browser Web Push service | Push endpoint and encrypted payload containing title/body/data; browser vendor routes delivery | Server-side to subscription endpoint; `WEB_PUSH_VAPID_PUBLIC_KEY`, `WEB_PUSH_VAPID_PRIVATE_KEY`, `WEB_PUSH_VAPID_SUBJECT` | Configuration-dependent | Not disclosed; endpoint operator varies by browser and may receive IP/UA |
| Google Gemini | User instruction, dataset profile/allowed column names and sample values used for AI plan/code generation | Server-side; `AI_ENABLED`, `AI_PROVIDER`, plan provider/model variables, `GEMINI_API_KEY`/provider key | Configuration-dependent; default provider name is Gemini when AI enabled/key present | Not disclosed. Must describe optional AI transfer, categories, provider terms/location and sensitive-data restrictions |
| Google Calendar/OAuth | OAuth account/credentials, calendar event read/write, sync cursor, revocation | Browser redirect + server-side APIs; Google client ID/secret and calendar flags | Configuration-dependent | Not disclosed; likely subprocessor/integration recipient |
| Microsoft identity/Graph Calendar | Same calendar OAuth/event sync | Browser redirect + server-side APIs; Microsoft client ID/secret | Configuration-dependent | Not disclosed |
| Google Sheets | Public/published sheet ID/content retrieved as CSV from `docs.google.com` when user supplies URL and remote ingestion enabled | Server-side; `ALLOW_REMOTE_DATASET_URLS` and related guards | Configuration-dependent; default disabled | Not disclosed; Google receives server IP and requested sheet identifier |
| Google Fonts | Inter and IBM Plex Sans Arabic stylesheet/font requests | Browser-side on every page where CSS loads | Verified code, but CSP/deployment/browser may affect actual load | Not disclosed; Google receives normal request metadata/IP/UA. Self-hosting would reduce this transfer |
| Unsplash | Starter-template image URLs are hotlinked, not copied/proxied | Browser-side when starter/live content retains URL | Verified in starter content; actual visitor load content-dependent | Named in current policy; should clarify hotlink and visitor metadata |
| YouTube | Starter embed URL and permitted CSP frames | Browser iframe when customer publishes embed | Content-dependent | Not disclosed; can place/read third-party storage in embed context and receive IP/UA |
| goQR / `api.qrserver.com` | Public site or public form URL is placed in QR-generation query; browser fetches image | Browser-side when publish tab renders/copies QR | Verified for tenant staff | Not disclosed; transfers the public URL and request metadata |
| WhatsApp (`wa.me`) | Public/form URL inserted into share link | User-triggered browser navigation | Verified | Not disclosed; recipient/provider receives link and request metadata |
| Instagram | Madar marketing footer link | User-triggered browser navigation | Verified | Named in current policy |
| LinkedIn and GitHub | Team-member external links | User-triggered browser navigation | Verified | Not disclosed; ordinary external-link disclosure may suffice |
| Customer-configured external hosts | Images, video/media, links, custom HTTPS URLs and supported embeds in published schemas | Browser-side when published content renders or visitor clicks | Verified capability; recipient arbitrary | Material. Terms should allocate responsibility; Privacy Policy should warn customers/visitors and require tenant notice |
| Madar attribution URL (`madar.app`) | Fixed customer-site footer link | User-triggered browser navigation | Verified | First-party/related-domain ownership unknown; operator must confirm |
| Redis | Rate-limit counters within Compose | Internal server network; `REDIS_URL` | Verified infrastructure component, external hosting unknown | Not a third party in local Compose; managed Redis provider would require disclosure |
| Nginx/Docker/host | Frontend serving, API containers, local volumes and logs | Deployment infrastructure | Verified software; host/provider/location unknown | Founder/operations must identify hosting, database region, backups and subprocessors |

The installed OpenAI Python package and provider settings are not evidence of active OpenAI transmission: the provider branch raises “not implemented.” DeepSeek is likewise unimplemented. CalDAV appears as a database provider value but no active connector was found. No payment provider, analytics platform, ad network, Sentry-like error tracker, map, or Cloudflare runtime integration was found.

## 10. Logging, monitoring, analytics, and audit-data findings

### Verified logging

- Production/default structured logging converts arbitrary messages to a fixed safe event name and includes only correlation/security/error/status/duration/method/route allowlisted extras. HTTPX/HTTPCore are limited to warning or above. This reduces accidental body/token logging (`backend/services/observability_service.py:139-219`).
- Request metrics use route templates, methods, status class and latency, not query strings or user identifiers. The metrics endpoint also exposes bounded queue/storage/backup operational numbers and requires a bearer token or loopback access (`observability_service.py:20-137`; `backend/routes/health_routes.py`).
- Uvicorn access logging strips query strings but can still log client address, method, path template/request path, status and UA depending Uvicorn format. Exact deployed collector configuration is unknown (`observability_service.py:172-191`).
- Docker uses `json-file` rotation: backend/workers 20 MiB × 5; frontend/Redis 10 MiB × 3. This is size-based, not a legal time retention period (`docker-compose.yml`).
- Database audits intentionally store raw IP address and user-agent plus actor/tenant/target/action/metadata. Sensitive metadata keys including password, token, cookie, authorization, session, schema, answers and raw body are removed, but other free-form metadata values could still identify a user (`audit_service.py:9-133`; migration `030`).
- Authentication success/failure, verification, password, MFA, admin role/delete/profile/billing, support account access, builder uploads/publish/archive/site-members, website settings, submission status and calendar actions have audit calls. Ordinary reads, public contact creation and every builder edit are not uniformly written to `audit_logs`.
- Rate limiting stores keys derived from scope, identifier and often client IP in Redis/in-memory with the configured window TTL. Some identifiers use IDs or hashed email; it is operational security data (`rate_limit_service.py`).

### Personal data exposure assessment

| Item | Finding |
|---|---|
| Email/name/phone | Structured production log formatter drops arbitrary extra keys, but development/nonstructured logger configuration could expose extras if a formatter includes them. Admin dev email flow deliberately provides recipient/code as extra fields when SMTP is absent. Database records and admin APIs contain full values. |
| Form/reservation content | Not intentionally included in structured logs. Reservation payload is stored in notification data, which is persistence rather than logging. |
| IP/user agent | Raw in `audit_logs`, submission/reservation rows, push subscription; client IP appears in some logging `extra` but is omitted by the structured allowlist. Uvicorn access log may include client IP. |
| Authorization/cookies/tokens | No intentional logging found; audit sanitizer blocks common keys; HTTP client logging is reduced. Error strings are converted to `error_type` in most code. |
| Uploaded filename | Builder original filename is in registry, not audit log; dataset original filename is returned to browser, while accepted-upload log records only size/mode/counts. |
| Provider/payment references | OAuth access tokens are encrypted in DB and not logged; provider/event IDs may be stored in billing/sync tables. No live payment references exist. |
| Frontend console | Development warnings/errors exist. They generally log Error objects/messages, creating some risk if future errors contain payloads; no analytics/error reporter forwards console data. |

No application-log retention duration, audit-log retention, access-log retention at a reverse proxy, or external monitoring vendor was defined. Size rotation in Compose must not be described as a guaranteed retention period.

## 11. Security-control findings

| Control | Actual implementation | Classification / qualification |
|---|---|---|
| Password handling | Backend enforces 8–1,024 characters and passes password to Supabase Auth; no password column in public schema. | Enforced by app; hashing/breach checks/provider policy unknown (`password_policy.py`) |
| Email verification/reset | Supabase is canonical verification authority; local lifecycle records/cooldowns and reset nonces exist. | Enforced/configuration-dependent provider delivery |
| Session cookies | Access/refresh are HttpOnly; production requires Secure; SameSite configurable; signed activity cookie defaults to one-hour inactivity. | Enforced with environment-dependent attributes |
| Logout/revocation | Application clears auth, CSRF, activity and admin-access cookies. | Cookie clearing verified; provider-wide refresh-token revocation not clearly established |
| CSRF | Signed token bound to session plus cookie/header comparison and origin checking; public/auth/webhook routes exempt and rely on other controls. | Enforced; allowed origins configuration-dependent (`request_security.py`) |
| CORS | Credentials allowed only for configured frontend origins; methods/headers broad within allowed origins. | Configuration-dependent (`backend/app.py:92-117`) |
| MFA/AAL2 | Supabase TOTP enroll/challenge/remove; sensitive admin list/mutation/support-access routes require AAL2. Admin login enforcement has a deployment flag. | Partly enforced; global admin-login requirement configuration-dependent |
| Rate limiting | Redis normal, fail-closed production default; auth/password/contact/forms/uploads/data/admin-access scopes. | Enforced if configured; trusted-proxy correctness deployment-dependent |
| Tenant authorization | Backend resolves authenticated local user and active membership, scopes queries by tenant/project and checks roles. | Enforced in normal routes. Service-role makes backend checks critical |
| RLS/grants | Later migrations enable RLS and revoke broad direct privileges on sensitive objects. | Verified in source, live state unknown; requires live catalog test (`050`, `053`, `066`) |
| Public resource authorization | Public schema filters private keys and unauthorized pages; protected resource capability checks use project role assignments. | Enforced in current backend code; requires full-stack validation |
| Request limits | Global/body-type limits, public payload field/string/JSON caps, builder schema cap. | Enforced/configurable (`request_body_limits.py`; `public_site_routes.py:45-59`) |
| Upload validation | Builder/avatars check magic bytes/MIME/size and randomize names; dataset checks extension/content/zip/spreadsheet limits and path scope. | Enforced; malware scanning absent |
| File isolation | Public assets separated from private uploads/charts; startup rejects private paths nested in public root. | Enforced in app; mounted-volume/host permissions configuration-dependent |
| Admin support access | AAL2, emailed one-time code, hashed code/session token, five attempts, short expiry, UA binding, audit, separate cookie. | Enforced; data-retention and user visibility/withdrawal controls incomplete |
| Audit security | Sensitive metadata key filter, IP/UA security events, fixed structured logs. | Enforced for callers using service; not every action/read logged |
| URL/SSRF controls | HTTPS validation, managed upload path checks and remote ingestion network guards. | Enforced; customer browser can still contact allowed arbitrary external HTTPS hosts |
| AI execution | Sensitive-column heuristics, resource-bounded code/sandbox settings; production local execution off by default. | Configuration-dependent; semantic sensitive-data detection is not a guarantee |
| Calendar credentials | Fernet-style application encryption using `CALENDAR_CREDENTIALS_SECRET`; OAuth state hashed/single-use/bound. | Enforced when configured; key storage/rotation operational |
| Encryption in transit | Production URL validation and HSTS placeholder/CSP exist; Supabase/Google/Microsoft endpoints are HTTPS. | Infrastructure-dependent; no global TLS proof |
| Encryption at rest | Calendar credentials and optionally browser IndexedDB datasets are application-encrypted. General DB/files/backups at-rest encryption is not proven. | Unknown/configuration-dependent; must not claim generally |
| Backups/DR | Backup, verification and restore scripts/runbooks exist, freshness check optional. | Operational capability; schedule, retention, off-site encryption and tested recovery unknown |
| Secrets management | Secrets read from environment; docs direct use of deployment secret manager; Compose references `.env`. | Operational/configuration-dependent; no secret manager implementation in repo |
| Account lockout | Rate limiting, MFA attempt controls and admin access code attempts exist. | No durable general login lockout found |
| Vulnerability reporting | `/.well-known/security.txt` provides `info@madar.com`, English/Arabic and expiry. | Verified page; email ownership/process unknown |
| Incident notification | Runbook identifies incident roles/evidence/containment. | Documented only; no customer notification timetable/contact workflow |
| Compliance/certification | None evidenced. | Not found; no compliance claims should be made |

No malware scanning, DLP, formal sensitive-form-field prevention, device inventory, session management UI, user-visible login history, or automatic account-lockout table was found.

## 12. Retention, deletion, and export matrix

| Data category | Current retention rule | Deletion mechanism / trigger | Backup implications | Legal/business reason in code | Confidence / missing requirement |
|---|---|---|---|---|---|
| Platform account/Auth | No defined retention policy found | Madar admin can delete; no self-service. Supabase auth deletion cascades local user | Backup erasure timing unknown | Account operation/security | High; define closure, verification and backup expiry |
| Pending unverified account | 14-day expiry state | Dry-run cleanup service/script can delete eligible resource-free accounts; schedule not found | Unknown | Prevent orphan pending accounts | High implementation, low operational execution |
| Terms acceptance | Until user deletion | User/admin deletion cascade | Unknown | Contract evidence | High; retain version history and define post-closure retention |
| Verification/reset attempts | Expiry/status fields only; no purge | User cascade for reset; verification attempts may preserve null user/auth | Unknown | Security/audit | High; set purge periods |
| Tenant/workspace | No defined retention policy found | Possible tenant delete during admin user deletion when no other staff membership | Files/external objects may survive; backups unknown | Workspace operation | High; add owner closure and safe transfer/export |
| Builder project | Indefinite; archived state | Archive only; physical project delete route absent | Included in DB backup | Content/recovery | High; define archive purge and cancellation behavior |
| Published site | Until project status/binding changes | Unpublish status; bound project restrictions; no domain-level termination workflow | Prior schema in backups | Hosting | High; define takedown timing and notice |
| Builder asset | Referenced: no expiry. Unreferenced: eligible after 7 days | Apply-mode cleanup deletes file and soft-deletes registry; not scheduled | Backups may retain | Orphan cleanup/storage | High in code; operations/backup policy missing |
| Avatar | No defined retention policy found | Replacement best-effort removes old; account delete does not explicitly remove | Supabase Storage backup/provider retention unknown | Profile display | High gap |
| Public contact | No defined retention policy found | No route/tool found | DB backups unknown | Support/lead response | High gap |
| Form submission | No defined retention policy found | No row delete; tenant/project physical cascade | DB backups unknown; staff session cache may persist during session | Tenant workflow | High gap; tenant-configurable retention/delete required |
| Reservation | No defined retention policy found | Cancellation only changes status; tenant/project cascade | Payload duplicated in notification tables/backups | Booking/history | High gap |
| Public-site user | No defined retention policy found | Tenant admin removes membership; admin deletes global user | Auth/provider/backups unknown | Protected site access | High gap; membership removal does not equal identity deletion |
| Notification/event | No defined retention policy found | Read status only; cascades | Backups unknown | User notification | High gap |
| Notification outbox | `retention_until` defaults 90 days | No deletion worker/script found | Backups unknown | Retry/delivery audit | High: date is metadata, not enforced deletion |
| Web-push subscription | Until delete/revocation | User delete endpoint; invalid endpoint marks revoked | Backups unknown | Push delivery | High; purge revoked records |
| Audit logs | No defined retention policy found | No deletion path; actor/tenant set null on deletion | Runbook encourages preserving incident evidence | Security/accountability | High; balance evidence and privacy |
| Admin access records | Active code/session expiry 10/30 minutes default, rows indefinite | End/revoke state, user cascade; no purge | Backups unknown | Support consent/security | High; define access-record retention and user visibility |
| Rate-limit records | Configured window (typically 60–300 seconds) | Redis TTL/in-memory expiry on access | Redis tmpfs in Compose, not backed up | Abuse prevention | High |
| Dataset server file | No defined retention policy found | No delete API found; tenant/user deletion does not explicitly unlink local files | Included in backup script | Analysis workspace | High-severity gap |
| Dataset browser IndexedDB | Indefinite | Manual `clearDataset`/archive delete/browser clear | Local device backup/sync outside Madar control | Local resume/archive | High; UI disclosure and clear-all/account logout behavior needed |
| Generated charts | No defined retention policy found | No delete API found | Included in backup script | Visualization | High gap |
| Data/report export | User-controlled local file | User deletes local download | Outside Madar | Portability/analysis | High; not comprehensive account export |
| AI usage | No defined retention policy found | User/tenant cascade | DB backups; Gemini provider retention unknown | Quota/fraud | High; provider retention decision required |
| Calendar/event | No defined retention policy found; event soft delete indefinite | Event soft delete; connection delete; children cascades | DB backups and provider copies | Calendar/history/sync | High gap; define deleted-event/history retention |
| OAuth credentials | Connection lifetime | Disconnect attempts Google revocation, deletes connection; Microsoft revocation confirmation behavior differs | DB backups may contain encrypted credentials | Sync | Medium/high; key and backup erasure policy needed |
| Billing feature state | No defined retention policy found | No customer cancellation/delete; tenant cascade for features | DB backups | Manual access state | High |
| Billing event evidence | Indefinite and deliberately survives tenant deletion | No deletion path | DB backups | Replay/idempotency evidence | High; define if real billing launches |
| Docker/app logs | Size rotation only: 10/20 MiB × 3/5 files | Docker rotation | External collector unknown | Operations/security | High code confidence; time retention unknown |
| Backups | Script never prunes | Operator action only | This is the backup itself; off-host copies unknown | Recovery | Critical missing policy |

### Current rights support

| Desired right | Technical support today |
|---|---|
| Access | Users can view profile/current workspace; tenant staff can view tenant records. No consolidated subject-access export. Public submitters cannot retrieve their record. |
| Correction | Profile names/phone/avatar can be changed. Email change is deliberately rejected pending a verified email-change flow. Form/reservation submitters have no correction workflow. |
| Deletion/account closure | Only Madar admin user deletion; no self-service account/tenant closure. No form/reservation/dataset/chart/audit deletion workflow. |
| Restriction | Account/site membership can be disabled; reservation/form status can change, but no privacy restriction state. |
| Objection | No workflow. |
| Consent withdrawal | Push subscription can be deleted; no general consent register/withdrawal workflow. |
| Portability | Dataset CSV/XLSX, report and ICS exports exist. A form-response-to-CSV dataset import exists only when responses are already embedded in a project object; current backend wiring was not verified. No comprehensive account/workspace export and no submitter export. |
| Account closure | Not self-service; requires operational/admin action not documented to user. |

## 13. Billing and subscription findings

**Verified current behavior:** authenticated tenant members can choose a plan. The backend validates plan names, upserts a `features` row with `payment_status=pending`, audits the choice, and returns `checkout_available=false`, `requires_payment=false`, and `pending_manual_activation`. The UI says no payment was taken (`billing_routes.py:31-123`; `MyPlanPage.jsx:67-104`).

Static public pricing displays monthly dollar symbols:

- CMS Builder: `$15`
- Forms + DA: `$10`
- CMS Plus: `$20`
- Complete: `$25`

Evidence: `frontend/src/content/pages/pricingContent.js:38-149`. The code does not specify whether `$` is USD, tax-inclusive, tax-exclusive, promotional, or merely indicative. Arabic content repeats the same symbols.

| Topic | Finding |
|---|---|
| Paid subscriptions live | No. Manual/beta access state only. |
| Payment provider | Not found. |
| Card/bank processing | Not found. |
| Checkout session/customer/subscription IDs | Not found. |
| Automatic renewal | Not found. |
| Cancellation/customer portal | Not found. |
| Refund/chargeback | Not found. |
| Trial/promotion | AI normalizes trial aliases to free internally, but no commercial trial workflow was found. |
| Taxes/billing address | Not found. |
| Invoices/receipts | Not found. |
| Failed payment behavior | Status values include `past_due`, `canceled`, `expired`, but no real provider transitions. Optional publish entitlement can deny access based on state. |
| Webhook | A non-production shared-secret development adapter exists; production always returns 503. It is not a provider webhook. |
| Feature limits | Static UI describes bundles. Publishing entitlement is off by default and supports beta allowlisting. Broad module limits are not comprehensively enforced. |
| Billing-term acceptance | No billing-specific checkbox/version acceptance before plan request. |
| Plan consistency | Backend accepts historical full-platform and individual-builder plan sets beyond the four current public cards. This is an internal compatibility surface, not proof those plans are offered. |
| Custom plan | Current content has no modules; `CustomPlanPage` only opens a success modal and does not call the backend. Partially/dead implementation. |

Terms must not promise automated subscription creation, renewal, cancellation, refunds, invoices, taxes, payment security, or gateway behavior. Before paid launch, founders must decide currency, tax display, billing cycle, renewal, cancellation effective date, proration, refunds, failed-payment grace, invoices, provider, checkout acceptance, and retention of financial records.

## 14. Intellectual-property and acceptable-use findings

### Intellectual property

- No repository-level license file was found. Package manifests identify open-source dependencies, but dependency inclusion does not establish Madar’s own source license.
- The current Terms say customers remain “responsible” for content but do not expressly say who owns customer content or grant Madar a hosting/publishing/backup/moderation license (`frontend/src/i18n/locales/en/public.json:100-103`).
- Technical operation necessarily copies, transforms, caches, backs up, serves and publishes customer schemas and assets. Final Terms need a limited technical license while preserving the ownership allocation chosen by founders/counsel.
- Starter templates hotlink Unsplash images. They are not proxied or copied by upload code. The repository does not contain image attribution/license tracking or proof that every starter use satisfies current Unsplash terms.
- Google Fonts are remotely loaded. Dependency/template/open-source license notices are not surfaced to customers in the inspected UI.
- Published customer sites include a fixed “Powered by Madar” link to `https://madar.app/`; no setting to remove attribution was found (`PageBuilder.siteChrome.jsx:1-20`; `TenantSiteRuntime.jsx:2169-2177`).
- Customers can set branding, content, external images and links. No automated copyright/license verification exists.
- No feedback/suggestion assignment or license clause was found.

### Technical misuse risks and Terms recommendations

| Capability/risk | Technical finding | Required Terms direction |
|---|---|---|
| Phishing/impersonation/fraud | Users can publish arbitrary pages, forms, login-looking blocks and external links | Prohibit deception, credential harvesting, impersonation and unlawful/fraudulent business |
| Excessive/sensitive collection | Arbitrary form/reservation labels and free text; no sensitive-data blocklist | Require lawful basis, minimization, notice and consent where needed; prohibit high-risk/sensitive data unless Madar expressly supports it |
| Malware/dangerous files | Builder/avatars limited to validated raster images; datasets accept spreadsheets; form “file” does not upload bytes | Prohibit malware and weaponized documents; reserve scanning/removal rights; clarify file limitations |
| Copyright/trademark/privacy | Customer uploads/publishes content and hotlinks external URLs | Require rights/permissions and takedown cooperation; prohibit doxxing/privacy violations |
| Spam | Public forms, notifications and public sites can be abused; rate limits/honeypot exist | Prohibit unsolicited bulk messaging and abusive automation |
| Unlawful products/services | Generic website publishing capability | Prohibit illegal/restricted sales and activity |
| Scraping/DoS/security testing | Public APIs and upload/analysis resources are rate-limited but accessible | Prohibit disruption, bypass, scraping beyond permission and unauthorized testing; provide authorized disclosure channel |
| Cross-tenant/credential abuse | Multi-tenant service and roles | Prohibit access outside authorization, credential sharing and privilege abuse |
| AI/data abuse | Datasets can contain third-party data and optional AI transfer | Require upload authority and prohibit secrets/sensitive data unless approved; explain provider use |
| Admin misuse | System admins can see identity/billing and use consent-code access | Internal access policy, least privilege, training, access review and sanctions are operationally required |

The existing one-paragraph acceptable-use clause covers broad categories but should be made specific to hosting, forms, visitor data, uploads, automation, intellectual property, phishing, malware, regulated/sensitive data and enforcement/takedown.

## 15. Existing-policy claim verification table

The wording below is the English source. Arabic contains equivalent sections and should be revised consistently.

| Existing claim | Classification | Evidence and analysis |
|---|---|---|
| Privacy: “collects information needed to provide accounts, tenant workspaces, website builder features, contact forms, and support workflows” | Partially supported; missing qualification | These exist, but reservations, public-site accounts, data analysis, calendars, notifications, AI and admin/security flows are omitted (`public.json:86`) |
| “Account details may include name, email, phone…” | Supported | `users` and request models store these |
| “…tenant profile data, website settings, uploaded assets, form submissions, billing selections…” | Supported but incomplete | All exist; does not explain public/private assets, dataset uploads, reservation/calendar/push data |
| “…operational logs such as IP address and user agent” | Supported | Audit/submission/reservation/push records and access logs |
| “authenticate users, operate tenant workspaces, publish customer sites, process contact and form submissions, secure, troubleshoot, support” | Supported but incomplete | Accurate purposes, omits reservations, analytics workspace, AI, calendar sync, billing requests, notification delivery |
| “uses first-party authentication and CSRF cookies” | Inaccurate by omission | Seven application cookies found, not only auth/CSRF |
| “Analytics and payment SDK cookies are not currently integrated in frontend” | Supported, narrowly | No analytics/payment SDK found. Does not mean no external/browser tracking or storage |
| “uses Supabase-backed authentication and data services” | Supported | Core backend dependency |
| “Public links may open Instagram” | Supported | Marketing footer link |
| “starter content may reference external Unsplash image URLs until replaced” | Supported | Hotlinked starter assets |
| Privacy contact `info@madar.com` | Repository-supported, operationally unknown | Displayed in contact/footer/security.txt; ownership and legal privacy process unverified |
| Terms acceptance by creating an account/access/use | Partially supported/inaccurate qualification | Platform creation has explicit checkbox and record. Public-site registration lacks acceptance. Access/use as acceptance is legal wording, not technical record |
| Organization user confirms authority | Unsupported technically; requires legal/business rule | No authority attestation or organization field enforcement |
| Accurate information/confidential credentials; responsibility for account activity | Policy rule, not technically verifiable | Password/session controls exist, but no business verification |
| Customer responsible for text/files/images/forms/submissions and rights/permissions | Broadly appropriate; missing qualification | Capabilities exist. Does not address Madar license, ownership, tenant visitor notices or sensitive data |
| Prohibits unlawful/fraudulent/abusive/deceptive/harmful use, interference, unauthorized access, malware, privacy/IP violations | Supported as necessary rule; enforcement only partial | Rate limits/admin suspension states exist, but no content moderation/takedown workflow |
| “Paid features are governed by plan and price shown when you subscribe” | Inaccurate/misleading for current product | No subscription/payment; only pending manual request. `$` currency/tax undefined |
| Third-party availability/separate terms may affect features | Supported but too vague | Many specific providers and user-triggered integrations should be named/described |
| May maintain/improve/replace/discontinue and temporarily limit | Business/legal statement; technical support exists for disabling/suspending | No notice process or feature-deprecation procedure found |
| “reasonable efforts to protect service continuity and stored workspace data” | Too vague to verify / risky | Hardening and backup tooling exist; no SLA, proven restore, RPO/RTO or backup schedule |
| May restrict/end for violation/risk/law | Partially supported | Account status/admin delete and role disable exist; no documented enforcement/appeal process |
| User may stop using at any time subject to obligations | Missing important qualification | No self-service cancellation/account closure/export; paid obligations do not yet exist |
| “as-available,” no uninterrupted/error-free guarantee, indirect/consequential loss exclusion | Requires legal review | No uptime promise in code; limitation enforceability and liability cap/operator law unknown |
| Terms updates; latest version/date remains available | Partially supported | Static date/version shown; no policy history or notification/reacceptance process |

### Policy surfaces and acceptance

- Privacy and Terms pages are public routes and can be accessed before signup (`frontend/src/config/routes.js:1-15`; page components).
- The marketing footer links Privacy but not Terms (`Footer.jsx:11-14`). Signup links Terms but not Privacy (`SignUpPage.jsx:595-614`). The Terms page links Privacy.
- Platform signup requires a checkbox; frontend and backend tests cover it (`SignUpPage.test.jsx:58-93`; `backend/tests/test_onboarding_routes.py:201-315`).
- Backend stores the current Terms version `2026-07-13` and server time. It does not store the rendered language/content hash, Privacy acceptance, or an acceptance event history.
- No cookie notice, form privacy notice, refund text, policy change notification, reacceptance, or customer-site auto-legal links were found.
- No policy-specific tests beyond signup Terms acceptance were found.

## 16. Privacy Policy requirements matrix

| Topic | Verified current behavior/evidence | Required disclosure and wording direction | Gap/decision | Confidence |
|---|---|---|---|---|
| Operator identity | Only “Madar,” emails/phone and domains in UI | State full legal operator, address, registration/contact | Founder decision; critical | High absence |
| Scope/roles | Platform plus tenant visitor processing | Explain Madar controller uses and tenant-directed processing; tenant is responsible for its own notice | Legal role/DPA decision | High technical facts |
| Account information | Identity/auth/profile/roles/verification | List fields, purposes, Supabase, security records, acceptance record | Retention/rights workflow | High |
| Public-site accounts | Separate visitor account kind and membership | Explain global identity, tenant affiliation and protected-site access | No Terms/Privacy acceptance/self-delete | High |
| Tenant/business | Tenant, memberships, site settings, business/subdomain | Explain workspace administration and public publication | Ownership/administrator responsibilities | High |
| Customer content | Draft/published schema, uploads, local browser copies | Explain storage, public publication, browser recovery and tenant control | Content retention/export/ownership | High |
| Forms/reservations | Arbitrary answers/payload, IP/UA, tenant access, email | Explicitly describe tenant-directed collection and submitter rights/contact path | Sensitive fields, consent, delete/retention | High |
| Contacts/support | Name/phone/message and admin access | Explain support records and time-limited consent-code account access | Support retention/access policy | High |
| Data analysis/AI | Private files, previews, exports; optional Gemini profiles/samples | Explain categories, local/browser/server storage, AI transfer and user control | Provider terms, sensitive-data policy, retention | High |
| Calendars | Events/attendees/tasks/history; optional provider sync | Explain collaboration visibility, reminders and Google/Microsoft transfers | Feature launch scope and retention | High |
| Notifications/push | In-app/email/web push and endpoint/keys | Explain opt-in browser permission, providers, revocation and queue copies | Provider identity/retention | High |
| Cookies | Seven functional/security cookies | Provide exact categories, purposes, attributes/lifetimes and no analytics/payment cookies currently | Banner necessity legal review; text inaccurate | High |
| Browser storage | local/session/IndexedDB/service worker | Disclose full project/response/calendar/dataset local storage and manual clearing | Clear-on-logout/device guidance | High |
| Technical/security data | IP, UA, routes, timestamps, audit, rate limits | Explain fraud/security/troubleshooting purposes and access | Retention periods | High |
| Third parties | Section 9 inventory | Name active/configurable provider categories; distinguish embeds/user links | Legal names, locations, contracts | High |
| International processing | Supabase/provider locations absent | State actual regions/transfers and safeguards only after verified | Critical founder/operations/legal input | Unknown |
| Security | Controls in section 11 | Use qualified wording: reasonable technical/organizational measures; do not promise general at-rest encryption/compliance | Incident/contact and live RLS validation | High |
| Retention | Mostly undefined | Use category-specific periods or criteria; do not claim automatic deletion not implemented | Critical operational decision/build | High |
| Deletion/closure | Admin-only account delete, many orphan risks | Explain current request process honestly; preferably build self-service/operational workflow first | Critical gap | High |
| Exports/portability | Feature-specific exports only | Explain available exports and privacy-request process | Comprehensive export missing | High |
| Rights | Desired broad rights not fully supported | Offer access/correction/deletion/restriction/objection/withdrawal/portability with a verified handling process and exceptions | Build/request SLA, identity verification | High |
| Children/age | No age gate or minimum age | State chosen age and handling of child data; restrict tenant collection as needed | Critical founder/legal decision | High absence |
| Legal bases | No business/legal facts in repository | Counsel must map contract, consent, legitimate/security, legal obligations | Legal review | Not code-verifiable |
| Automated decisions | No consequential automated decision found; AI assists analysis | Say AI outputs assist users and do not establish a rights-significant decision unless product changes | Confirm business practice | Medium |
| Policy updates | Static page/date/version | Explain notice/reacceptance method and effective date | No notification/version history | High |
| Contact/complaints | `info@madar.com`, phone shown | Verify privacy email, mailing address, escalation/authority contact | Founder/legal input | High absence |

## 17. Terms and Conditions requirements matrix

| Topic | Verified current behavior/evidence | Required Terms direction | Gap/decision | Confidence |
|---|---|---|---|---|
| Contracting party | Not identified | Full operator legal name, form, address and effective date | Critical | High absence |
| Eligibility/minimum age | No age gate | Choose minimum age/capacity and organization authority rule | Critical | High absence |
| Account/credentials | Supabase auth, verification, MFA optional/required for admins | Accurate info, credential security, authorized users, recovery and notification | Define shared-account policy | High |
| Tenant roles | Owner/admin/member; member has broad builder/data read | Explain owner responsibility, administrator authority, member actions and tenant control | Role naming/permission expectations | High |
| Public-site users | Separate accounts, tenant roles, no acceptance | Define whether they contract with Madar or tenant and applicable notices | Critical feature-specific decision | High |
| Customer content/ownership | User uploads/publishes; no ownership mechanism | Preserve chosen ownership; grant limited host/process/publish/backup license; warranties | Founder/legal decision | High capability |
| Visitor data | Tenant defines forms/reservations and staff access | Tenant must provide notice/legal basis, minimize, respond to rights and avoid prohibited sensitive fields | DPA/processor terms | High |
| Uploads/external content | Public assets, public avatars, private datasets, hotlinks/embeds | Clarify public/private designations, rights, limits, external terms and removal | Malware/moderation process | High |
| Acceptable use | Broad misuse possible | Detailed prohibitions from section 14, enforcement/takedown and cooperation | Appeals/reporting process | High |
| Platform license | Users access SaaS, no clause | Limited, revocable, nontransferable use right; restrictions on reverse engineering/abuse as legally appropriate | Legal review | N/A |
| Madar IP/branding | Fixed attribution, templates/UI | Reserve platform/template/brand rights; say whether attribution removable | Founder decision | High |
| Feedback | No handling | Optional feedback license only if desired | Business decision | High absence |
| Billing | Manual requests, static `$` monthly display, no charge | State beta/manual access accurately now; do not call it paid subscription | Critical before paid launch | High |
| Paid launch | No provider/renewal/refund/tax/invoice | Add provider, currency, tax, renewal, cancellation, refunds, failed payment, invoices, promotions only when implemented/decided | Critical before paid launch | High |
| Feature limits/beta | Entitlement off by default; optional calendars/workers/AI | Identify beta/configurable features and no promise of listed-but-unavailable modules | Launch scope decision | High |
| Suspension | Account/site status/admin tools exist | Grounds, proportionality, notice where feasible, urgent security exception, appeal/export | Operational process | Medium/high |
| Termination/account closure | Admin delete only; archive/retention gaps | Explain user termination request, tenant authority, export window, content removal and retained records | Critical product/ops gap | High |
| Service changes | No notice system | Reserve reasonable changes; define material-change/feature-removal notice if promised | Founder decision | High absence |
| Availability | No SLA/proven restore | “As available”; avoid uptime, advance downtime or guaranteed restoration promises | Support/maintenance expectations | High |
| Backups | Tooling, no schedule/retention/RPO/RTO proof | Avoid “regular backups” or guaranteed restoration until operations verify | Critical ops decision | High |
| Security | Strong controls but configuration-dependent | Reasonable measures, shared responsibility, no absolute security guarantee | Incident report process | High |
| Third parties | Supabase and optional integrations | Dependency/third-party terms; customer authorization for integrations | Provider contract review | High |
| Privacy/DPA | Mixed controller/processor facts | Incorporate Privacy Policy and offer business DPA if decided | Legal decision | High |
| IP complaints | No workflow | Notice/takedown/counter-notice process appropriate to target law/markets | Legal/ops | High absence |
| Disclaimers | Current as-available sentence | Tailor to Palestine/consumer law and product; preserve non-excludable rights | Legal review | Not code-verifiable |
| Liability cap | None | Choose cap/basis/exclusions and consumer carve-outs | Critical legal/business | High absence |
| Indemnity | None | Decide tenant indemnity scope for content/visitor collection/misuse | Legal/business | High absence |
| Governing law/courts | None | Palestine basis plus exact law/court/arbitration choice | Critical legal | High absence |
| Consumer rights | Intended for businesses and individuals; no differentiation | Preserve mandatory consumer rights; identify consumer cancellation/refund requirements | Legal review | High |
| Policy/Terms updates | Static date; platform acceptance version only | Effective date, material notice, reacceptance and archived versions | Technical gap | High |
| Notices/contact | `info@madar.com` displayed | Verified legal notices email/address and electronic notice rules | Founder decision | High |

## 18. Technical and operational gap analysis

| Priority / gap | Current state and risk | Affected users / evidence | Recommended change | Must precede policy publication? Can disclose temporarily? |
|---|---|---|---|---|
| P0: Legal identity absent | No contracting/controller entity, address, registration or courts | Everyone; repository-wide absence | Founders/counsel supply and verify entity/contact/jurisdiction | Yes; cannot publish complete policies without it |
| P0: Undefined retention/backups | Most data indefinite; backup script never prunes | All subjects; section 12 | Approve schedule by category, implement deletion jobs, backup retention and restore deletion rules | Yes for credible disclosure; temporary “criteria/no fixed period” is too weak for high-risk records |
| P0: No rights/request workflow | No SAR, restriction, objection, portability or submitter workflow | Accounts, visitors, submitters | Create verified intake, identity/tenant routing, deadlines, audit and response/export/deletion tooling | Yes if broad rights are promised; limitations can be disclosed only briefly while operational process exists |
| P0: No self-service closure/comprehensive delete | Admin-only user deletion; files/avatars/submitter records may survive | Platform/site users and tenants | Add closure request/self-service, ownership transfer, cascade manifest, external file cleanup and confirmation | Strongly recommended before policy; temporary support-assisted disclosure possible only with a real staffed process |
| P0: Public-site signup lacks Terms acceptance | Shared Madar identity created without acceptance/version | Site visitors; `public_site_routes.py:1284-1366` | Decide contract model; add notice/checkbox/version or make tenant solely responsible with appropriate flow | Before feature launch/public policies |
| P0: Sensitive custom fields unrestricted | Tenants can collect arbitrary sensitive data without dedicated consent | Form/reservation submitters | Block/highlight prohibited field categories, add consent/privacy-link component, tenant notice configuration and DPA controls | Before broad public form launch; policy warning alone is insufficient for highest-risk data |
| P0: Visitor legal notices absent | Customer sites do not auto-link tenant/Madar notices | Public visitors | Add customer legal-page settings/links and form-level privacy notice | Before public collection at scale; temporary tenant contract requirement possible |
| P1: Cookie/browser storage policy inaccurate | Seven cookies and extensive local/session/IndexedDB storage | All users | Rewrite inventory; add clear-storage controls and evaluate consent banner by law/markets | Yes, text must be accurate; implementation can remain if disclosed |
| P1: Submission/reservation delete absent | Tenant staff can only change status | Submitters/tenants | Add tenant-authorized delete/anonymize with audit and retention settings | Prefer before policy; temporary limitation can be disclosed with support deletion |
| P1: Dataset/chart retention absent | Large private files persist, user delete does not unlink | Data-workspace users/data subjects | Add object-level delete, account cleanup, retention expiry and quota UI | Before promising deletion; limitation can be disclosed temporarily |
| P1: Notification `retention_until` unenforced | 90-day date exists without deletion job; payload duplicates personal data | Submitters/calendar users | Bounded purge job and separate dead-letter/audit retention | Before claiming 90-day deletion; otherwise say no enforced period |
| P1: Third-party list incomplete | AI/calendar/push/fonts/QR/embeds omitted | All affected users | Dynamic feature inventory, provider contracts/DPA/locations; self-host fonts/QR if desired | Yes for enabled services |
| P1: Admin access transparency/retention | Strong code controls but no user access history/withdrawal and rows persist | Platform users | User-visible access log, revoke button, support policy, retention and access reviews | Disclose now; improve before mature launch |
| P1: Terms acceptance/versioning incomplete | Only current Terms pair; no Privacy/version history/change notice | Platform users | Immutable acceptance event table, content hash/language, policy type/version, change notifications/reacceptance | Before material update; current initial Terms evidence is usable |
| P1: Billing wording exceeds implementation | “Paid features/subscription” language despite manual request | Prospective customers | Label beta/manual access everywhere; remove subscription claims until provider live | Yes, correct Terms before publication |
| P1: Pricing currency/tax unclear | Dollar symbol only | Prospective customers | State currency and tax treatment; align backend product catalog/UI | Before paid subscriptions |
| P1: Backup/restoration promises unsupported | Tooling but no proof/schedule/RPO/RTO | Tenants | Approve and execute scheduled encrypted off-host backups and restore drills | Do not promise until verified |
| P1: External resources expose visitor metadata | Google Fonts, Unsplash, YouTube, custom embeds | Site/marketing visitors | Self-host fonts/default assets; add embed controls/notices and referrer policy review | Can disclose temporarily; tenant responsibility clause needed |
| P2: Email change incomplete | Profile email change rejected; no verified change workflow | Account users | Implement verified dual-notification email change | Disclose support correction route temporarily |
| P2: Revoked/expired security records lack purge | Verification, OAuth states, access sessions, push rows persist | Account users | Category retention and cleanup jobs | Can disclose criteria temporarily |
| P2: No malware scanning | Image magic checks and spreadsheet limits, but no scanner | Users/operators | Risk-based AV/sandbox scanning and quarantine for uploaded documents | Terms can disclose limitations; prioritize before broader file hosting |
| P2: No formal incident-user notification process | Operations runbook only | Everyone | Incident response plan, decision log, notification templates/contact/SLAs | Needed before making notification promises |
| P2: No production location/host inventory | Supabase/host/SMTP/push locations unknown | Everyone | Maintain subprocessor/data-location register and configuration evidence | Required for final Privacy Policy |
| P2: Public form export absent/incompletely wired | A client-side CSV import path expects form responses embedded in the project, while the active response page fetches them separately; no subject-centric export was verified | Tenants/submitters; `DataAnalysisWorkspace.jsx:115-127,1468-1505` | Add a supported tenant export plus subject lookup, redaction and identity verification | Needed for portability promise |
| P3: Footer discoverability | Marketing footer lacks Terms; signup lacks Privacy | Prospective users | Add both links at footer/signup and customer-site legal link support | Easy fix before publication |
| P3: Fixed attribution/domain ambiguity | `madar.app` fixed while marketing uses `madarportal.com` | Tenant site visitors | Confirm domain ownership/redirect and branding-removal rule | Terms/business decision |

## 19. Prioritized ambiguity and decision register

| Rank | Concrete unresolved question | Why/code suggestion | Decision and dependent clauses | Blocking |
|---|---|---|---|---|
| Critical before launch | What is the full legal operator name, legal form, registration number and official address? | Only “Madar,” domains, email and phone appear | Identify contracting party/controller, notices, governing law | Blocks publication |
| Critical before launch | Is `info@madar.com` the controlled, monitored legal/privacy/security address, and what mailing address/phone should be official? | Used in Privacy, Terms, contact and security.txt | Privacy requests, legal notices, vulnerability reports | Blocks publication |
| Critical before launch | What minimum age applies to platform and public-site accounts, and can tenants collect child data? | No age field/gate | Eligibility, children’s privacy, tenant restrictions | Blocks publication |
| Critical before launch | Which countries/markets are actually targeted beyond Palestine, and are consumers served? | English/Arabic, dollar prices, “Middle East” demo text; no restrictions | Consumer rights, transfer rules, governing language | Blocks reliable drafting |
| Critical before launch | What are exact retention periods for accounts, contacts, submissions, reservations, audits, support-access records, datasets, charts, calendars, notifications and security records? | Almost all are indefinite | Privacy retention and termination clauses | Blocks accurate retention section |
| Critical before launch | What is backup frequency, location, encryption, access, retention, deletion lag, RPO/RTO and restore-test status? | Scripts exist; runbook expressly leaves these open | Security, retention, availability, deletion | Blocks backup/restoration promises |
| Critical before launch | Will Madar prohibit special-category/high-risk/sensitive form fields, or support them under enhanced controls? | Arbitrary fields allowed | Acceptable use, tenant DPA, Privacy categories/security | Blocks unrestricted public forms |
| Critical before launch | Must every customer site publish its own privacy notice and identify Madar/providers, and will Madar provide/link a template? | No legal settings/auto links | Controller/processor allocation and visitor transparency | Blocks public collection governance |
| Critical before launch | Who is controller for public-site accounts and which Terms/Privacy notice governs registration? | Shared global Supabase/local identity with no acceptance | Site-user contract, Privacy roles, rights handling | Blocks feature legal launch |
| Critical before launch | What operational workflow will honor access, correction, deletion, restriction, objection, withdrawal, portability and closure? | Product only supports fragments | Rights section and support commitments | Blocks promise of broad rights |
| Critical before launch | Will business customers receive a DPA/subprocessor schedule, and what controller/processor allocation is intended? | Tenant defines visitor fields; Madar hosts/processes | Privacy roles, Terms, DPA | Blocks B2B data collection maturity |
| Critical before launch | What governing Palestinian law and exact courts/dispute process apply? | No clause | Governing law, jurisdiction, dispute resolution | Blocks final Terms |
| Critical before launch | What liability cap, excluded losses, non-excludable consumer carve-outs and indemnity are acceptable? | Only broad indirect-loss sentence | Liability, disclaimer, indemnity | Blocks final Terms |
| Required before paid subscriptions | What currency does `$` mean and are prices tax-inclusive? | Static `$10–$25` only | Price, tax, invoicing | Blocks paid launch |
| Required before paid subscriptions | Which payment provider, merchant entity and checkout flow will be used? | No provider/checkout | Privacy recipients, payment Terms, PCI allocation | Blocks paid launch |
| Required before paid subscriptions | What billing cycle, automatic-renewal notice, cancellation timing, proration, failed-payment grace, refunds, chargebacks, invoices and trials apply? | None implemented | All billing/refund/suspension clauses | Blocks paid launch |
| Required before paid subscriptions | Which plan limits are contractually promised and technically enforced? | UI packages; publishing entitlement off by default | Plan description, downgrade/suspension | Blocks paid launch |
| Required before a specific feature launches | Will Gemini AI be enabled, for which plans, with what data restrictions/provider retention/region and opt-out? | Default provider Gemini; configuration/key required | AI disclosure, subprocessor list, acceptable use | Blocks AI launch |
| Required before a specific feature launches | Will Google/Microsoft calendar sync and Web Push be enabled in production, and in which regions? | Optional flags/credentials/workers | Integration privacy/subprocessor/terms | Blocks those features |
| Required before a specific feature launches | Is remote dataset ingestion enabled, and are public Google Sheets permitted? | Backend defaults off while UI offers URL input | Third-party/SSRF/data-source terms | Blocks remote ingestion launch |
| Required before a specific feature launches | Will form file fields remain metadata-only or become true uploads? | Current runtime stores metadata only | Feature promise, upload privacy/security | Before marketing file-upload forms |
| Recommended | Will users see and revoke support account-access sessions/history? | Current code emails a code and logs access but has no user dashboard | Support/privacy/security transparency | Can follow with honest disclosure |
| Recommended | What notice/reacceptance threshold and channels apply to policy changes? | Static pages/date; one acceptance pair | Updates/notices/acceptance | Before first material revision |
| Recommended | What support hours/response expectations and security-incident communications exist? | No SLA; runbook only | Support/availability/incident clauses | Can state no SLA initially |
| Recommended | What dormant-account and post-cancellation export window applies? | No dormant/cancellation lifecycle | Retention/termination/export | Before scaled use |
| Recommended | Can customers remove “Powered by Madar”? | Fixed footer link | Branding/IP/plan promises | Business decision |
| Optional | Will feedback/suggestions be licensed to Madar? | No feedback workflow/clause | Feedback IP | Does not block launch |

## 20. Recommended next steps

1. **Freeze the factual launch scope.** Decide whether public-site accounts, calendars, AI, remote datasets, Web Push and SMTP reservation emails are launch features or disabled beta features. Policies should cover enabled and imminently enabled flows without describing dormant dependencies as active.
2. **Supply the critical legal identity decisions.** Operator/entity, address, privacy/legal/security contacts, age, markets, consumer status, governing law/courts, liability/indemnity and DPA position require founders and Palestinian counsel.
3. **Create a data-retention schedule and implement it.** Prioritize submissions, reservations, contacts, datasets/charts, notification payloads, audit/security records, admin-access records, expired OAuth/verification rows and backups. A timestamp column is not deletion.
4. **Implement a privacy-request/account-closure runbook before promising broad rights.** Include identity verification, tenant-vs-Madar routing, subject lookup, export, correction, restriction, deletion/anonymization, exceptions, backup lag, audit and response deadlines.
5. **Add customer-site privacy controls.** Dedicated Privacy/Terms links/pages, form-level notice URL/text, consent field/version/time, sensitive-field warnings/blocking, tenant accountability and a DPA are the minimum coherent package for tenant-directed visitor collection.
6. **Repair acceptance coverage.** Record immutable policy type/version/content hash/language/time/source for platform and, if legally appropriate, public-site users. Link both Terms and Privacy at signup and in the marketing footer. Define notice and reacceptance for material changes.
7. **Close deletion/orphan paths.** Self-service/support closure should delete or transfer tenant records, unpublish sites, remove local files, avatars, push/OAuth credentials and queued payloads, then document backup expiry. Add tenant submission/reservation deletion/anonymization.
8. **Correct public claims immediately.** Update cookie/browser-storage and third-party disclosures; label billing as manual beta; remove unsupported backup/continuity implications. Do not claim general encryption at rest, regular backups, restoration, compliance certification or an uptime percentage.
9. **Complete the provider register.** Record legal service name, purpose, data, contractual role, region, transfer mechanism, retention and contact for Supabase, deployment hosting, SMTP, push, Gemini, Google/Microsoft calendar and any managed Redis/monitoring service. Consider self-hosting fonts and QR generation.
10. **Prepare paid-launch controls separately.** Do not extend current placeholder Terms. Integrate a provider-hosted checkout/webhook/customer portal, define price/currency/tax/renewal/cancellation/refunds/invoices and record billing-term acceptance before accepting money.
11. **Validate deployed security facts.** Run the repository’s read-only live RLS/grant verification against the intended environment, confirm TLS/HSTS/CORS/proxy settings, prove notification worker configuration, execute an isolated restore drill and document the results without putting secrets in policy evidence.
12. **Then draft policies with counsel.** Use sections 15–19 as the source-of-truth checklist and keep configuration-dependent services explicitly conditional.

## 21. Appendix: important files and symbols inspected

### Application and configuration

- `backend/app.py` — `app`, middleware, public asset route, router registration.
- `backend/database.py` — environment loading, `supabase`, `service_supabase`.
- `backend/classes.py` — account, profile, billing, admin and MFA request models.
- `docker-compose.yml`, `docker-compose.dev.yml` — services, flags, mounts, log rotation.
- `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf.template`, `frontend/security_headers.conf.template`.
- `README.md`, `docs/production-operations-runbook.md`, `docs/backup-restore-runbook.md`, `docs/observability.md`, `docs/migration-history.md`, `docs/applied-migrations/production.md`.

### Legal/UI surfaces

- `frontend/src/i18n/locales/en/public.json:83-111` and Arabic equivalent — policy text.
- `frontend/src/components/MainPages/PrivacyPolicyPage.jsx`.
- `frontend/src/components/MainPages/TermsAndConditionsPage.jsx`.
- `frontend/src/components/MainPages/Footer.jsx`.
- `frontend/src/components/AuthPages/SignUpPage.jsx` — `getValidationErrors`, `getRequestPayload`, acceptance checkbox.
- `frontend/src/components/AuthPages/SignUpPage.test.jsx` and `backend/tests/test_onboarding_routes.py`.
- `frontend/public/.well-known/security.txt`.

### Identity, authorization and security

- `backend/routes/auth_routes.py` — `signup`, `login`, `CURRENT_TERMS_VERSION`, verification and session flows.
- `backend/routes/password_routes.py`; `backend/services/password_policy.py`.
- `backend/services/auth_service.py` — cookie attributes, refresh, inactivity, administrator account access resolution, AAL2.
- `backend/services/request_security.py` — CSRF token/cookie and origin validation.
- `backend/services/pending_verification_context.py`; `backend/services/mfa_login_service.py`.
- `backend/routes/mfa_routes.py`; `backend/services/user_security_settings_service.py`.
- `backend/services/tenant_service.py` — `TenantContext`, membership/role guards.
- `backend/services/admin_account_access_service.py` — code/session/cookie/audit.
- `backend/routes/admin_user_routes.py`; `backend/services/admin_user_service.py`.
- `backend/services/rate_limit_service.py`; `backend/services/request_body_limits.py`.
- `backend/services/audit_service.py`; `backend/services/observability_service.py`.

### Builder, public sites and files

- `backend/routes/builder_routes.py` — asset upload, projects, site members, responses, publish/unpublish/archive.
- `backend/routes/public_site_routes.py` — public schema, visitor accounts, forms, reservations and cancellation.
- `backend/services/site_permission_service.py`; `backend/services/url_validation.py`.
- `backend/services/asset_registry_service.py`; `backend/services/storage_quota_service.py`; `backend/services/upload_config.py`.
- `backend/routes/user_routes.py`; `supabase/migrations/022_create_avatars_storage_bucket.sql`.
- `frontend/src/components/PageBuilder/core/PageBuilder.constants.js`, `PageBuilder.starters.js`, `PageBuilder.siteChrome.jsx`.
- `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx`.
- `frontend/src/components/PageBuilder/tabs/PageBuilderPublishTab.jsx`.
- `frontend/src/components/PageBuilder/workspace/hooks/useDebouncedProjectStorage.js`; builder persistence/recovery modules.
- `frontend/src/components/PageBuilder/responses/utils/responsesCache.js`.

### Data analysis, AI, calendars and notifications

- `backend/data_analysis/routes/`; `backend/data_analysis/services.py`; `backend/data_analysis/io/data_reading.py`.
- `backend/data_analysis/ai/settings.py`, `planner.py`, prompt/profile/execution modules.
- `frontend/src/components/PageBuilder/DataAnalysisWorkspace/dataAnalysis.helpers.js`.
- `frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/datasetStorage.js`, `dataframeExport.js`.
- `backend/routes/calendar_routes.py`; `backend/services/calendar_sync_service.py`; calendar reminder/worker services.
- `frontend/src/components/DashboardBuilder/utils/calendarWorkspaceCache.js`.
- `backend/routes/notification_routes.py`; `backend/services/notification_outbox_service.py`; `notification_delivery_service.py`.
- `backend/workers/notification_worker.py`; `backend/workers/calendar_sync_worker.py`.
- `frontend/src/services/notificationsApi.js`; `frontend/public/madar-push-sw.js`.

### Billing

- `backend/routes/billing_routes.py`; `backend/routes/admin_billing_routes.py`.
- `backend/services/billing_service.py`.
- `frontend/src/content/pages/pricingContent.js`.
- `frontend/src/components/DashboardBuilder/MyPlanPage.jsx`.
- `frontend/src/components/MainPages/CustomPlanPage.jsx`.

### Database migrations

All files in `supabase/migrations/001_initial_schema.sql` through `066_normalize_sensitive_object_privileges.sql` were searched or inspected. The most material are:

- `024_create_builder_projects.sql`
- `027_create_builder_form_submissions.sql`
- `030_create_audit_logs.sql`
- `033_create_user_security_settings.sql`
- `035_create_admin_account_access.sql`
- `036_restore_original_signup_foundation.sql`
- `037_create_ai_usage_daily.sql`
- `038_create_notifications.sql`
- `042_create_tenant_site_memberships.sql`
- `043_create_account_lifecycle.sql`
- `044_create_builder_reservations.sql`
- `045_add_platform_safety.sql`
- `046_harden_public_reservations.sql`
- `047_create_notification_outbox.sql`
- `048_add_terms_acceptance.sql`
- `049_expand_tenant_site_member_roles.sql`
- `050_restrict_authenticated_privileged_writes.sql`
- `051_bind_public_sites_to_projects.sql`
- `052_publish_validated_builder_schema.sql`
- `053_remove_residual_authenticated_privileges.sql`
- `054_add_form_submission_idempotency.sql`
- `055_create_builder_asset_registry.sql`
- `056_add_storage_quota_accounting.sql`
- `057_add_project_site_permissions.sql`
- `059_add_site_member_record_ownership.sql`
- `060_remove_member_record_access.sql`
- `061_create_calendar_platform.sql`
- `062_add_calendar_task_reminders.sql`
- `064_add_calendar_task_recurrence.sql`
- `065_secure_calendar_oauth_state.sql`
- `066_normalize_sensitive_object_privileges.sql`

### Explicit unknowns

The repository does not establish: legal entity/operator details; incorporation/registration/tax status; official address; minimum age; actual target countries; actual production hosting or data regions; Supabase project region; SMTP/push provider identity; provider contracts/DPAs; production flags; live schema equality; TLS certificate/edge provider; at-rest encryption for general DB/files/backups; backup schedule/retention/restore success; log collector/retention; operational support/privacy staffing; insurance/certifications; refund/renewal/tax rules; or Palestinian legal conclusions. These must remain unknown until supplied and verified.
