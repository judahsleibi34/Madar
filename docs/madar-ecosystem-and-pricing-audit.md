# Madar ecosystem and pricing audit

**Audit date:** 2026-07-30 (UTC)

**Repository audited:** `/home/madar/saas/Madar`

**Production branch and commit:** `main` at `92b90bcceda9405441f50f68ae69bbab8331373a`

**Development reference:** `/home/madar/saas/Madar-dev`, `builder-backend` at `3a84a286be8de435095c125fc7963a2f12a69e49`
**Nature of report:** technical and product audit, not legal, accounting, or financial advice

## 1. Executive summary

Madar is already a substantial multi-tenant SaaS application. Its strongest chargeable capabilities are account security, tenant isolation, a persistent website/page builder, Madar subdomain publishing, public forms with durable submission management, public reservation requests with durable management and cancellation, and an internal calendar/task system. It also contains capable data import, cleaning, analysis, visualization, and report-building tools, although the live production readiness check currently reports storage as unavailable, which materially affects uploads, builder assets, and data workflows.

The proposed `$15 / $20 / $25 / $30` price range is reasonable for an early Palestinian-market SaaS, but the proposed feature promises are not. “Business email,” a general “basic chatbot,” randomized quiz questions, public tab-leave test protection, customer-owned Google Drive, OCR, WhatsApp integration, custom domains, online payment, and unlimited team users are not saleable implementations today. External calendar sync, web push, AI analytics, quizzes, photo proofing, and e-commerce exist to varying degrees but should remain beta, internal, or unadvertised until the gaps in this report are closed.

The repository contains three incompatible commercial descriptions:

- The requested proposal uses Forms `$15`, Builder `$20`, Business `$25`, and Business Plus `$30`.
- The public pricing content uses Forms + Data Analysis `$10`, CMS `$15`, CMS Plus `$20`, and Complete `$25` (`frontend/src/content/pages/pricingContent.js:38-149`).
- The authenticated “My Plan” screen displays static sample data such as an “Operations” plan at `$29`, three sites, three users, and unrelated module prices (`frontend/src/components/DashboardBuilder/MyPlanPage.jsx:1-159`).

The backend has a fourth vocabulary: full-platform plans and individual builder types, persisted as feature/payment-state records. Checkout deliberately produces a pending manual request and says online checkout is unavailable; there is no payment provider, invoicing, tax, renewal, refund, card, or self-service cancellation implementation (`backend/routes/billing_routes.py:29-83`; `backend/services/billing_service.py:29-51,500-545`).

The recommended launch structure remains close to the requested framework:

| Plan | Price | Honest launch position |
|---|---:|---|
| Forms | **$15/month** | Public forms, durable responses, response overview, and limited data tools |
| Website | **$20/month** | One Madar-hosted website, page builder, assets, and light forms |
| Business | **$25/month** | Website plus larger form/data allowances |
| Business Plus | **$30/month** | Business plus reservation requests and internal calendar |

These prices should initially be sold as manually approved pilot subscriptions with hard usage ceilings, not automatic recurring subscriptions. Before any paid launch, Madar should restore the production storage readiness check, verify the deployed migration ledger, schedule and monitor backups, decide whether to operate the notification worker, replace the conflicting price/plan sources, and enforce entitlements and quotas server-side.

This audit’s feature matrix contains **15 production-ready capabilities**, **12 implemented-but-incomplete capabilities**, **4 experimental capabilities**, **4 placeholder/UI-only capabilities**, and **10 planned-or-absent capabilities**. “Production-ready” means the implementation is coherent enough to sell after normal operational verification; it does not imply a legal compliance or uptime guarantee.

## 2. Git synchronization result

### Production checkout

| Check | Result |
|---|---|
| Initial branch | `main` |
| Initial tracked/untracked state | Clean; `git status --short` returned no output |
| Previous local commit | `92b90bcceda9405441f50f68ae69bbab8331373a` |
| Fetched `origin/main` | `92b90bcceda9405441f50f68ae69bbab8331373a` |
| Ahead/behind | `0 / 0` |
| Pull | Not required; local `main` was already current |
| Commits pulled | None |
| Final local commit | `92b90bcceda9405441f50f68ae69bbab8331373a` |

`git fetch --all --prune` was performed. Because production was neither behind nor diverged, `git pull --ff-only` was not run. No checkout, reset, stash, commit, or push occurred.

### Development checkout

The development checkout was inspected but not updated. It was clean on `builder-backend` at `3a84a286be8de435095c125fc7963a2f12a69e49`; its `origin/main` was `92b90bcceda9405441f50f68ae69bbab8331373a`. The comparison was `0 / 10`: development had no unique commits and was ten commits behind `origin/main`.

### Deployment automation

`madar-auto-deploy.timer` is enabled and invokes `/etc/systemd/system/madar-auto-deploy.service`, which runs `/usr/local/sbin/madar-auto-deploy` as the `madar` user with the production repository as its working directory. The wrapper fetches `origin/main` and, on a changed target, executes `/home/madar/docker_auto.sh`.

The deploy script builds and recreates the Compose stack, performs health checks, and has an automated rollback. It does **not** apply database migrations; migration commands are explicitly disabled. It also uses `git reset --hard` to the remote target after checking for tracked changes. That is an operational risk: it is not the same conservative fast-forward-only policy used for this audit and could replace a divergent local branch. The timer log observed during the audit reported `No update. Current commit: 92b90bc`; it did not deploy anything as a result of this audit.

GitHub workflow files run backend and frontend validation on repository events, but no repository evidence showed GitHub deploying production.

## 3. Architecture and ecosystem overview

### Application architecture

| Layer | Verified implementation | Evidence and implications |
|---|---|---|
| Frontend | React with Vite, route-based public/authenticated/admin UI | `frontend/package.json`; `frontend/src/App.jsx`; `frontend/src/routes/` |
| Backend | FastAPI application with auth, builder, public site, billing, calendar, e-commerce, notification, admin, and data-analysis routers | `backend/app.py:248-272`; `backend/routes/`; `backend/data_analysis/routes/` |
| Identity and primary data | Supabase Auth and Postgres accessed through Supabase clients/RPCs | `backend/services/supabase.py`; `backend/services/auth_service.py`; `database/migrations/` |
| Cache/rate limits/queues | Redis; rate-limit state and calendar/notification worker coordination | `backend/services/rate_limit_service.py`; `backend/workers/`; `docker-compose.yml` |
| File storage | Local mounted volumes for builder assets, private datasets, generated charts/reports, and optionally avatars; quota reservations in Postgres | `backend/services/storage_quota_service.py`; `backend/services/builder_asset_service.py`; `backend/data_analysis/services/storage_service.py`; `docker-compose.yml` |
| Public delivery | Nginx-built frontend, FastAPI public-site APIs, Madar subdomains | `frontend/nginx.conf`; `backend/routes/public_site_routes.py`; `backend/services/website_service.py` |
| Background work | Calendar sync worker normally present; notification delivery worker is a Compose profile and was not running | `backend/workers/calendar_sync_worker.py`; `backend/workers/notification_worker.py`; `docker-compose.yml:149-188` |

### Live production observation

The running Compose stack contained healthy backend, frontend, Redis, and calendar-sync-worker containers. The notification worker was absent. A read-only request to `http://127.0.0.1:8001/health/ready` returned HTTP 503 with these significant states:

- `database`, `redis`, `auth`, schema baseline, admin MFA policy, calendar configuration, calendar sync worker, and calendar queue: `ok`.
- `storage`: `unavailable`.
- AI generated-code execution guard: `disabled`.
- remote ingestion guard: `insecure`.
- parser isolation: `in_process`.
- notification worker and notification queue: `disabled`.
- backup freshness: `disabled`.

This is point-in-time production evidence, not merely source inference. It means the service may answer ordinary health checks while workflows depending on file storage are degraded. It also means the repository’s implemented notification and backup-readiness controls are not enabled in the observed deployment.

### Tenant and publication model

Madar creates a tenant/workspace and tenant membership for each platform account. Membership roles are owner, administrator, and member, and backend services apply tenant authorization. Separately, a published tenant website can have visitor accounts, site memberships, and project-defined roles. These are not the same as platform team members (`database/migrations/002_create_tenants_and_memberships.sql`; `database/migrations/059_add_builder_site_users.sql`; `backend/services/tenant_service.py`; `backend/services/builder_site_auth_service.py`).

The builder can persist multiple projects and revisions, but website publication resolves through one tenant `website_settings` record/subdomain and one published project binding. The safe commercial interpretation is **one simultaneously published Madar site per workspace**, not unlimited websites (`backend/services/builder_project_service.py`; `backend/services/website_service.py`; `database/migrations/032_create_builder_projects.sql`).

No custom-domain mapping or domain-verification system was found. Madar subdomains are implemented; customer-owned domains must not be advertised.

## 4. Verified feature inventory

### 4.1 Core platform

**Authentication and account management.** Email/password signup and login use Supabase Auth. Email verification, resend, password reset with nonce lifecycle, current-password verification, password change, refresh, and logout exist. Authentication is held in HttpOnly access/refresh/activity cookies; a JavaScript-readable signed CSRF cookie is bound to the session. Secure-cookie behavior is environment dependent and expected in production (`backend/routes/auth_routes.py`; `backend/routes/password_routes.py`; `backend/services/auth_service.py`; `backend/services/csrf_service.py`).

Signup requires an explicit Terms/Privacy checkbox and records a fixed terms version (`2026-07-13`) and server-side acceptance time. There is no customer self-service account deletion; account deletion is an administrative action (`frontend/src/components/AuthPages/SignUpPage.jsx`; `backend/services/onboarding_service.py`; `backend/services/admin_user_service.py`).

**MFA and sensitive administration.** TOTP enrollment, verification, factor listing/removal, login challenge, and AAL2 checks exist. Sensitive admin user, billing, and account-access actions enforce MFA/AAL2. Administrator account access uses an emailed short-lived code and separate access/session records with audit events (`backend/routes/mfa_routes.py`; `backend/routes/admin_account_access_routes.py`; `backend/services/admin_account_access_service.py`; `backend/tests/test_admin_mfa_aal2_enforcement.py`).

**Authorization.** Route and service tests cover ordinary users, tenant roles, and administrators. Database RLS and RPCs add defense in depth, although older technical reviews note that some direct database paths deserve hardening. This report treats application-supported flows as the product boundary, not arbitrary direct Supabase access (`backend/tests/test_authorization_matrix.py`; `database/migrations/045_add_platform_safety.sql`).

**Audit and rate limits.** Backend audit events sanitize metadata and hash identifiers. Redis-backed rate limits cover authentication, public submissions, data, uploads, and other expensive or sensitive paths. Production defaults can fail closed when Redis is unavailable (`backend/services/audit_log_service.py`; `backend/services/rate_limit_service.py`; `backend/tests/test_security_audit_events.py`).

### 4.2 Website and content tools

**Builder.** Projects, draft/published JSON, revisions, compare-and-swap persistence, publish/unpublish, archive, autosave recovery, and conflict handling exist. Same-browser tabs coordinate through browser channels; this is not multi-user live editing over WebSockets. The builder supports pages, navigation, themes, layout, text/media, forms, reservations, authentication blocks, and other content elements (`backend/routes/builder_routes.py`; `backend/services/builder_project_service.py`; `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`; `frontend/src/components/PageBuilder/core/`).

**Assets.** Images are type/size checked, randomized, tenant-scoped, registered, reference tracked, and quota accounted. The default builder image limit is 5 MB. Unreferenced-object cleanup primitives exist, but no active retention schedule was verified. Production’s current storage readiness is unavailable, so assets should not be sold until restored (`backend/services/builder_asset_service.py`; `backend/services/storage_quota_service.py`; `database/migrations/056_add_storage_quota_accounting.sql`).

**Public sites.** Published schemas are filtered before public delivery, use revision/cache identifiers, and can resolve by subdomain. Publish/unpublish and archive are implemented. There is no physical project delete route, custom domain support, page-view analytics, or SLA (`backend/routes/public_site_routes.py`; `backend/services/public_site_service.py`; `database/migrations/052_publish_validated_builder_schema.sql`).

**Forms.** Public forms validate required fields and payloads, apply a honeypot/minimum-elapsed spam check and Redis rate limits, use an idempotent database RPC, and persist tenant/project/form identifiers plus answers. Tenant users can list, search, filter, paginate, and update response status. No response deletion or CSV export was found in the response manager (`backend/routes/public_site_routes.py`; `backend/services/builder_submission_service.py`; `database/migrations/054_harden_builder_form_submissions.sql`; `frontend/src/components/PageBuilder/responses/`).

**Tests and quizzes.** The editor supports answer keys, timers, focus settings, retakes, and client-side grading. The authenticated builder preview implements fullscreen/tab/blur behavior. The real public form route submits answers through `TenantSiteRuntime`; the backend stores `quiz_result` as null and does not enforce grading or focus rules. No question shuffling/randomization implementation was found. Consequently “convert forms into tests,” “randomized questions,” and “tab-leave protection” are not reliable public product promises (`frontend/src/components/PageBuilder/preview/BuilderFormPreviewPage.jsx`; `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx`; `backend/services/builder_submission_service.py`).

**Photo proofing.** A photo-proofing block exists visually, but selected photos remain local React state and “submit” closes the UI without durable backend submission. It is UI-only/experimental (`frontend/src/components/PageBuilder/blocks/PhotoProofingBlock.jsx`; `frontend/src/components/PageBuilder/core/PageBuilder.elementRenderer.jsx`).

### 4.3 Scheduling and communication

**Reservations.** Published reservation blocks accept validated public requests, support custom fields, idempotency/request hashing, optional exclusive-slot collision prevention, cancellation tokens, customer cancellation, tenant list/detail/status management, and audit/notification records. No reservation deletion, export, monthly quota, or overage enforcement exists (`backend/services/builder_reservation_service.py`; `backend/routes/public_site_routes.py`; `database/migrations/057_add_builder_reservations.sql`; `frontend/src/components/PageBuilder/reservations/`).

**Calendar.** The internal calendar includes calendars, role-based membership, events, recurrence, history, tasks, task dependencies, availability, reservation overlays, reminders, ICS import/export, and provider connection/synchronization infrastructure. Source migrations 061–069 implement the model and queues. The observed production calendar configuration, worker, and queue were healthy (`backend/routes/calendar_routes.py`; `backend/services/calendar_service.py`; `backend/services/calendar_task_service.py`; `backend/workers/calendar_sync_worker.py`; `database/migrations/061_create_calendar_platform.sql` through `069_harden_calendar_task_outbound_sync.sql`).

Google and Microsoft OAuth/inbound event synchronization are configuration dependent. Task outbound synchronization is implemented for Google; Microsoft task parity was not found. The audit did not perform an external provider transaction, so provider sync should be labeled beta despite the healthy worker (`backend/services/calendar_provider_service.py`; `backend/services/calendar_sync_service.py`; `backend/services/calendar_task_sync_service.py`).

**Notifications and email.** In-app notifications and read/unread state are implemented. Web Push subscriptions and a delivery worker exist, and SMTP can send application transaction messages. However, the production notification worker/queue were disabled. Reservation confirmations and reminders may be enqueued without external delivery. Supabase separately sends authentication emails (`backend/routes/notification_routes.py`; `backend/services/notification_service.py`; `backend/services/email_service.py`; `backend/workers/notification_worker.py`).

No hosted tenant mailbox provisioning, mailbox UI, mailbox quota, custom email-domain linkage, or supported “business email” product exists in Madar. Host-level mail infrastructure is not proof of a Madar customer feature. WhatsApp behavior is limited to user-triggered `wa.me` sharing links; there is no WhatsApp Business API, webhook, message queue, template approval, delivery status, or conversation metering (`frontend/src/components/PageBuilder/tabs/PageBuilderPublishTab.jsx`).

### 4.4 Data and AI

**Data workspace.** Users can upload CSV/XLS/XLSX, ingest supported public URLs and public Google Sheets links, inspect fields/types/quality/missing values, apply cleaning operations, produce domain analyses, create visualizations, export files, and assemble reports. Uploaded files are private and tenant/user scoped; local browser state also uses IndexedDB. This is a capable analytics workspace, but storage is currently unavailable in production and parsing occurs in the web process (`backend/data_analysis/routes/`; `backend/data_analysis/services/`; `frontend/src/components/PageBuilder/DataAnalysisWorkspace/`).

There is **no Google Drive OAuth/private Drive integration**. A public Google Sheets URL importer is not equivalent: the sheet must be publicly retrievable and the server fetches that URL (`backend/data_analysis/services/data_loader_service.py`; `backend/data_analysis/services/url_ingestion_service.py`).

**AI analytics.** Madar has a bounded analytics assistant that works from compact dataset profiles and validated analysis operations. It is not a website customer-service chatbot. Gemini and mock planning paths exist; OpenAI is explicitly unimplemented in the planner despite the dependency/config surface, and no complete DeepSeek path was verified. Generated-code execution is guarded and was disabled in observed production. Daily atomic per-user message and code-generation limits exist, but named paid plans collapse to one generic “pro” allowance and usage is not metered in provider tokens/cost (`backend/data_analysis/services/ai_assistant_service.py`; `backend/data_analysis/services/ai_provider_service.py`; `backend/data_analysis/routes/analysis_routes.py`; `database/migrations/037_add_ai_usage_limits.sql`; `039_harden_ai_usage_accounting.sql`).

**OCR.** No OCR route, service, worker, provider integration, or language-specific validation was found. Arabic, English, and Hebrew OCR are roadmap concepts, not product features.

### 4.5 E-commerce

Migration 070, catalog APIs, dashboard screens, a public storefront, cache utilities, demo seed data, and tenant-scoped product/category/tag records exist. The storefront has a browser-local cart interaction, but there is no checkout, payment, order, fulfillment, shipment, customer account, or inventory-decrement workflow. E-commerce has no entitlement gate and migration 070 is not included in the documented production migration operator record reviewed in this audit. It is experimental and should remain off the launch pricing page (`database/migrations/070_create_ecommerce_catalog.sql`; `backend/routes/ecommerce_routes.py`; `backend/services/ecommerce_cache_service.py`; `frontend/src/components/DashboardBuilder/EcommercePage.jsx`; `frontend/src/components/PageBuilder/EcommerceStorefront.jsx`).

## 5. Feature maturity matrix

The following 45 rows are the basis for the counts in the executive summary.

| # | Capability | Status | Constraints/dependencies | Advertise and charge today? | Main evidence |
|---:|---|---|---|---|---|
| 1 | Email/password auth and sessions | **Production-ready** | Supabase availability; secure environment config | Yes | `backend/routes/auth_routes.py`; `backend/services/auth_service.py` |
| 2 | Email verification and password lifecycle | **Production-ready** | Auth email delivery through Supabase | Yes | `backend/routes/password_routes.py`; related tests |
| 3 | Tenant/workspace isolation and roles | **Production-ready** | No customer-facing team invitation workflow | Yes, as workspace isolation—not team management | `backend/services/tenant_service.py`; membership migrations |
| 4 | Profiles and avatars | **Production-ready** | Avatar storage configuration | Yes after storage recovery | `backend/routes/user_routes.py`; `backend/services/avatar_service.py` |
| 5 | TOTP MFA and AAL2 administration | **Production-ready** | Admin MFA policy configuration | Yes | `backend/routes/mfa_routes.py`; admin AAL2 tests |
| 6 | Onboarding and policy acceptance record | **Production-ready** | Hard-coded policy version needs operational process | Yes | `backend/services/onboarding_service.py` |
| 7 | Admin user/billing management | **Production-ready** | Internal operator capability, not customer feature | Internal only | `backend/routes/admin_user_routes.py`; `admin_billing_routes.py` |
| 8 | Time-bound admin account access | **Production-ready** | SMTP delivery and support procedure | Internal only | `backend/services/admin_account_access_service.py` |
| 9 | Security audit logging | **Production-ready** | Direct DB actions may bypass application audit | Yes as a control, not an absolute claim | `backend/services/audit_log_service.py` |
| 10 | Redis rate limiting | **Production-ready** | Redis; production fail-closed setting | Yes as a control | `backend/services/rate_limit_service.py` |
| 11 | Persistent page-builder projects | **Production-ready** | Large client surface; no real-time server collaboration | Yes | builder routes/services/frontend |
| 12 | Madar-subdomain publish/unpublish | **Production-ready** | One published site per workspace; no custom domain | Yes with qualification | public-site/website services |
| 13 | Public forms and durable submissions | **Production-ready** | No response export/delete or monthly entitlement | Yes with limits implemented first |
| 14 | Submission search/status management | **Production-ready** | Summary only, not advanced analytics | Yes | `frontend/src/components/PageBuilder/responses/` |
| 15 | Public reservations and cancellation | **Production-ready** | External emails disabled; no quota/export/delete | Yes as “request and manage bookings” after disclosure |
| 16 | Builder asset uploads | **Implemented but incomplete** | Live storage readiness unavailable; cleanup not scheduled | No until storage is healthy |
| 17 | Storage quota accounting | **Implemented but incomplete** | Global defaults, not plan-specific; no overage billing | Not as plan limits yet |
| 18 | Public-site visitor accounts and roles | **Implemented but incomplete** | Complex secondary identity model; needs operational UX review | Beta only |
| 19 | Quizzes/tests | **Implemented but incomplete** | Public grading/enforcement incomplete | Beta only |
| 20 | Public focus/tab-leave protection | **Implemented but incomplete** | Works in preview, not end-to-end public enforcement | No |
| 21 | Form response analytics | **Implemented but incomplete** | Counts/completion/filters only; no trends/CSV | Call “response overview,” not analytics suite |
| 22 | Internal calendar/events/tasks | **Implemented but incomplete** | Worker healthy; feature flag/config and broader acceptance needed | Business Plus pilot/beta |
| 23 | Reservation email confirmations/reminders | **Implemented but incomplete** | Notification worker disabled in production | No |
| 24 | Web Push | **Implemented but incomplete** | VAPID/config/worker/service-worker behavior | Beta only |
| 25 | Data import/cleaning/export | **Implemented but incomplete** | Storage unavailable; parser in-process; resource cost | Pilot/beta after recovery |
| 26 | Visualization and report builder | **Implemented but incomplete** | Storage/export capacity and retention need hardening | Pilot/beta |
| 27 | Billing state/manual plan request | **Implemented but incomplete** | No payment processor, renewal, invoice, cancellation, tax, refund | Manual pilot sales only |
| 28 | Google Calendar sync | **Experimental** | OAuth credentials, provider behavior, support, quotas | Free beta only |
| 29 | Microsoft Calendar sync | **Experimental** | OAuth credentials; no Google-task parity | Free beta only |
| 30 | AI analytics assistant | **Experimental** | Gemini configuration; coarse request limits; storage; cost metering absent | Opt-in beta with hard cap |
| 31 | Tenant e-commerce catalog/storefront | **Experimental** | Migration state uncertain; no transaction backend; no gate | No |
| 32 | “My Plan” usage/renewal dashboard | **Placeholder or UI-only** | Static sample limits/prices; not billing usage | No |
| 33 | Photo-proofing submissions | **Placeholder or UI-only** | Client state only; no persistence | No |
| 34 | Response “chatbot” summary | **Placeholder or UI-only** | Deterministic local text, not a chatbot service | No |
| 35 | Plan/user/submission/reservation usage meters | **Placeholder or UI-only** | UI values do not reflect enforced entitlements | No |
| 36 | Question randomization | **Planned or absent** | No shuffle/random assignment/persistence | No |
| 37 | Hosted business email/mailboxes | **Planned or absent** | No provisioning, UI, quota, domain, support | No |
| 38 | General/basic website chatbot | **Planned or absent** | Analytics assistant is not customer chat | No |
| 39 | Google Drive OAuth/private files | **Planned or absent** | Public Sheets importer only | No |
| 40 | OCR, including Arabic/English/Hebrew | **Planned or absent** | No OCR implementation or benchmarks | No |
| 41 | WhatsApp Business integration | **Planned or absent** | Share links only | No |
| 42 | Custom domains | **Planned or absent** | No mapping/verification/TLS workflow | No |
| 43 | Online payment/renewal/invoices/refunds | **Planned or absent** | Manual pending request only | No |
| 44 | Customer self-service closure/export | **Planned or absent** | Admin deletion only; fragmented exports | No |
| 45 | Advanced integrated analytics | **Planned or absent** | No cross-project funnels, scheduled reports, anomalies | No |

## 6. Current plan versus implementation gap analysis

| Proposed promise | Evidence-based result | Pricing consequence |
|---|---|---|
| Forms | Strong public collection and response management exists | Can anchor a `$15` plan after quotas |
| Forms converted into tests | Editor and preview are partial; public grading/results are incomplete | Do not include in launch copy; beta after end-to-end work |
| Randomized questions | Not found | Remove |
| Tab-leave protection | Preview-only behavior, not reliable public enforcement | Remove; never market as cheating prevention without clear limitations |
| Basic analytics | Response overview exists; generic data tools are richer but separate | Define narrowly; do not imply traffic or advanced analytics |
| Submission management | Implemented | Include |
| Public submission page | Published form URLs work | Include |
| Website/page builder | Implemented | Include |
| Reservations and calendar | Reservations are strong; calendar is implemented/config-dependent; notification delivery disabled | Include reservation management only in Plus; calendar/provider sync beta |
| 5 GB storage | Atomic quota engine exists and 5 GiB tenant default exists, but it is not plan-driven and live storage is unavailable | Do not promise until restored and entitlement assignment exists |
| Business email | No product implementation | Remove from every plan |
| Basic chatbot | No general chatbot; AI analytics is separate/experimental | Remove from every plan |
| Madar Drive | No distinct “Drive” product was verified | Rename to hosted storage only, with hard quota |
| Unlimited team users for `$5` | No user quota and no customer team-management workflow; platform and site users are conflated | Reject |
| Extra 10 GB + 20 users for `$5` | Neither entitlement is wired to billing; support and backup cost ignored | Split storage and users; use smaller enforced packs |
| Customer-owned Google Drive | No OAuth/private Drive support | Future add-on only |
| OCR in three languages | Absent | Future usage-based add-on after accuracy/cost benchmarks |
| WhatsApp integration | Only share links | Future add-on after official API implementation |
| Advanced analytics chatbot | Bounded dataset assistant exists experimentally | Opt-in beta, then usage-based add-on |

### Other omitted capabilities

The proposal under-values several genuine differentiators:

- Madar-subdomain website publishing and protected-site visitor accounts.
- Tenant-scoped durable form and reservation workflows with idempotency and rate limits.
- Internal calendar events, tasks, recurrence, dependencies, history, and ICS.
- CSV/Excel/public-Sheets import, cleaning, visualization, exports, and reports.
- MFA and audited time-bound administrator support access.

These should appear selectively, without turning the pricing page into a feature dump.

### “Unlimited users”

“Unlimited” is technically and financially unsound. Every user creates authentication, support, security, audit, notification, and potentially storage/AI load. More importantly, Madar does not currently expose a complete tenant-team invitation/removal/seat-count workflow. Published-site visitor users are a different model and must not be sold as workspace team seats. Launch plans should be single-operator until team management and server-side seat entitlements exist.

## 7. Cost and margin risks

| Cost/risk | Current control | Gap and pricing response |
|---|---|---|
| Hosted storage | Atomic tenant/user byte reservation; default 5 GiB/1 GiB | Not plan-specific; live storage unavailable; backup duplication increases real cost. Offer only hard caps after repair |
| File parsing and analysis | File-size limits and rate limits | Parsing runs in API process; spreadsheets and charts consume CPU/RAM. Cap uploads/jobs and isolate parsing before scale |
| AI/Gemini | Daily per-user request counts | No token, model, tenant-month, or dollar metering. Never bundle “unlimited”; use monthly hard cap and kill switch |
| OCR | None | Unknown provider/compute and language accuracy. Usage-based only after benchmark |
| Email | SMTP transaction service and Supabase auth mail | Notification worker disabled; no mailboxes. Separate transaction allowance from future hosted mailboxes |
| Calendar providers | Queue/worker and OAuth token storage | Provider quota, refresh failures, support burden, and Microsoft/Google asymmetry. Beta initially |
| Form/reservation traffic | Public rate limits and durable tables | No monthly tenant counters or entitlement enforcement. Add atomic counters before paid overages |
| Team seats | Membership records | No customer workflow/seat gate. Do not promise multiple or unlimited seats |
| Backups | Backup and isolated restore scripts | No verified schedule, retention, off-host encryption, restore history, or active freshness check. These are launch gates |
| Support | No SLA or staffed support process in code/docs | “Priority” is a business commitment. Founder must define channels/hours before publishing |
| Fraud/abuse | Rate limits, validation, audits | Public site/forms and future e-commerce create moderation/abuse cost. Add suspension and abuse operations |
| Payment/tax | Manual request only | Manual collection/reconciliation cost; taxes/currency/refunds undecided. Describe prices as USD and manually invoiced only after business/legal approval |

The proposed `$5` for 10 GB plus 20 users combines two different cost drivers and leaves almost no room for backup storage, support, and authentication overhead. A safer launch benchmark is `$5 per additional 5 GB` and, only after team functionality exists, `$3 per extra seat` or `$10 per five-seat pack`.

## 8. Recommended launch pricing

### Launch prerequisites

Do not publish these as paid generally available plans until:

1. Production readiness returns `storage: ok`.
2. The exact applied migration ledger is verified, including all migrations used by advertised features.
3. Backup scheduling, retention, off-host handling, and a successful restoration test are recorded; enable backup freshness monitoring.
4. One canonical plan schema replaces the conflicting public, dashboard, and backend schemas.
5. Server-side monthly counters and entitlements exist for projects/sites, submissions, reservations, storage, and modules.
6. The notification-worker decision is explicit. If it stays disabled, remove email-confirmation language.
7. Terms, tax/currency, cancellation, refund, and support commitments are founder/legal decisions.

Until those gates are complete, sell only manually approved pilots with usage reviewed by staff.

### Recommended plans

“Project” below means an active builder draft. The current product can store multiple projects but only one website is published per workspace. The limits are recommended entitlements; they are **not all enforced today** and require section 13’s work.

| | Forms | Website | Business | Business Plus |
|---|---:|---:|---:|---:|
| **Monthly price** | **$15** | **$20** | **$25** | **$30** |
| Target customer | Individual, survey owner, small organization | Individual or shop needing a simple public site | Small business needing site + forms/data | Service business taking booking requests |
| Published websites | 0 full sites; hosted form links | 1 Madar-subdomain site | 1 Madar-subdomain site | 1 Madar-subdomain site |
| Active projects | 1 form project | 3 | 5 | 8 |
| Active forms | 10 | 3 | 15 | 25 |
| Monthly form submissions | 1,000 | 500 | 2,500 | 5,000 |
| Tests/quizzes | Not promised; free beta when enabled per customer | Not included | Not promised; free beta | Not promised; free beta |
| Monthly reservations | 0 | 0 | 0 | 500 |
| Team users | 1 workspace operator | 1 | 1 | 1 |
| Madar-hosted storage | 1 GB | 2 GB | 5 GB | 5 GB |
| Google Drive | None; public Google Sheets link import where supported | None | None | None |
| Email allowance | Account/security service email only; no mailbox | Same | Same | Same; reservation email is not promised until worker is operational |
| Basic chatbot allowance | None | None | None | None |
| Analytics | Response overview; standard filters | Response overview for included forms | Response overview plus standard data import/cleaning/charts/exports | Business analytics plus reservation totals/status |
| Calendar | None | None | None | Internal calendar; Google/Microsoft connection labeled beta |
| Support | Standard email support* | Standard email support* | Standard email support* | Priority email support* |
| Overage behavior | Hard stop or `$5/1,000` submissions | Upgrade or submission pack | Packs or upgrade | `$5/500` reservations; other packs |

\*Support channels and response targets require founder approval. Do not publish a response-time promise until staff coverage exists.

### Why these upgrade steps work

- **Forms → Website:** adds a complete public-site builder and publishing.
- **Website → Business:** adds meaningful form volume, data analysis, charts, and larger storage.
- **Business → Business Plus:** adds reservation workflows and the internal calendar.

This is clearer than duplicating “business email” and “basic chatbot” across every tier. It also avoids claiming that every tool is available in every plan before entitlement enforcement exists.

### Important launch qualifications

- A “website” means one Madar subdomain, not a custom domain.
- Reservation means a request/management workflow, not payment or guaranteed appointment fulfillment.
- “Analytics” does not mean visitor/page-view tracking.
- Public Google Sheets import may expose data if customers make sheets public; it should not be presented as a secure Drive connection.
- Hosted storage limits should not appear until production storage is healthy and quotas are plan-assigned.
- There are no hosted business mailboxes.

## 9. Recommended add-ons and overages

| Add-on | Recommended price/limit | Launch state | Required implementation |
|---|---|---|---|
| Extra hosted storage | `$5/month` per 5 GB | Near-term | Plan quota assignment, billing counter, backup capacity, alerts, deletion UX |
| Extra team members | `$3/user/month`, or 5 seats for `$10/month` | Future | Invitation/removal, role UI, seat counter/gate, proration decision, audit |
| Extra form submissions | `$5` per 1,000/month | Near-term | Atomic tenant-month counters, dashboard meter, hard stop/grace policy |
| Extra reservations | `$5` per 500/month | Near-term | Atomic counters and enforcement |
| AI analytics | `$10/month` for 200 bounded questions; `$5` per extra 100, hard capped | Future paid beta | Tenant-month token/cost metering, supported-provider decision, budgets, consent/disclosure, kill switch |
| OCR | Indicative `$5` per 100 pages, finalized only after provider benchmark | Future | OCR implementation, per-language accuracy tests, page limits, malware isolation, retention, cost meter |
| Hosted email mailbox | Indicative `$5/mailbox/month` plus domain setup | Future | Provisioning, DNS/domain verification, anti-spam, storage quota, webmail/support, backup, abuse handling |
| WhatsApp Business | Indicative `$15/workspace/month` **plus Meta conversation/message fees** | Future | Official API, templates, webhook verification, consent, delivery state, billing pass-through |
| Custom domain | `$5/site/month`, or include one in Business Plus | Future | Domain verification, routing, certificates/edge automation, abuse and renewal handling |
| Google Drive private connection | `$5/workspace/month` | Future | OAuth scopes, encrypted tokens, file picker/sync, revocation, privacy review, quota/error UX |
| Advanced analytics chatbot | Same AI allowance or `$10/month` standalone | Future | Integrated cross-project dataset, tenant-month metering, evaluation, citations, safe exports |

Prices for external-provider features are product recommendations, not audited provider-cost facts. Before publication, Madar should measure actual provider, infrastructure, support, tax, and payment-collection costs and set a minimum gross-margin target.

## 10. Basic versus advanced analytics

### What exists now

**Form/reservation operational overview**

- Submission/reservation totals for the fetched result set.
- Search, status, completion, and field filters.
- Simple completion percentage and recent-response views.
- Reservation statuses and calendar overlay.

It lacks integrated date-trend charts, tenant-wide cross-form comparison, funnel metrics, and response CSV export.

**General data workspace**

- CSV/Excel/public Google Sheets ingestion.
- Field types, missingness, quality and descriptive summaries.
- Cleaning operations.
- KPI/grouping/trend/top-N/correlation/distribution operations for uploaded datasets.
- Multiple visualization types, report composition, and file export.

These are useful analysis tools, but they are not automatically connected to all Madar forms, sites, and reservations as one analytics product.

### Recommended definitions

| Level | Definition | Current status |
|---|---|---|
| **Response overview** | Total responses/reservations, status, completion, recent activity, standard filters | Implemented; use this phrase at launch |
| **Basic analytics** | Counts by date, simple trends, response summaries, basic charts, CSV export, standard date/status filters | Partially implemented; CSV and integrated trends need completion |
| **Advanced analytics** | Cross-form/project analysis, segmentation, period comparisons, conversion funnels, custom reports, detailed exports | Roadmap |
| **AI analytics** | Natural-language questions, AI summaries, anomaly suggestions, explainable/cited outputs | Experimental dataset assistant exists; integrated product is roadmap |
| **Automation** | Scheduled reports, alerts, anomaly monitoring | Absent |

“Basic analytics” should not imply website traffic/page-view analytics because Madar does not implement a site analytics collector. At launch, the pricing page should use **response overview**. Rename it to “basic analytics” only after date-series charts, filters, and CSV export are integrated and tested.

## 11. Pricing rollout roadmap

### Launch pricing

After the launch prerequisites in section 8:

- Forms `$15`: standard forms, response management/overview, limited data tools.
- Website `$20`: one Madar-subdomain website, three active projects, light forms.
- Business `$25`: one website, more projects/forms/submissions, standard data analysis, 5 GB storage.
- Business Plus `$30`: Business plus reservation requests and internal calendar.

Use manual subscription approval and invoice/collection processes while the payment system is absent. Do not describe plans as automatically renewing unless the actual commercial arrangement does.

### Near-term additions

| Capability | Work before sale |
|---|---|
| Basic analytics | Integrated date charts, consistent totals beyond current page, CSV export, tested filters |
| Plan limits | Canonical product catalog, tenant entitlements, atomic counters, UI meters, admin overrides, tests |
| Storage add-ons | Healthy storage probe, plan quota propagation, deletion/retention, backup capacity and alerts |
| Reservation emails | Deploy/monitor notification worker, SMTP deliverability, retry/dead-letter operations, templates |
| External calendar beta | Provider end-to-end tests, disconnect/revocation UX, error monitoring, documentation, support boundaries |
| Quizzes beta | Public grading/results, attempt persistence, randomization if promised, honest anti-cheating limitations |
| Data workspace | Restore storage, isolate resource-intensive parsing, retention/deletion, load tests |
| Team seats | Customer invitations, membership lifecycle, roles, seat enforcement and audit |

### Future paid add-ons

WhatsApp Business, OCR, hosted mailboxes, custom domains, private Google Drive, additional AI, and advanced analytics should remain roadmap items. Each needs the product, cost, privacy, support, and metering work in section 9. The e-commerce catalog should be a separate product decision and must not be sold until checkout-less catalog behavior or full commerce scope is deliberately defined.

## 12. Features that must not yet be advertised

Do not claim:

- Hosted business email or email mailboxes.
- Unlimited team users or even multi-seat plans before the customer team workflow exists.
- Question randomization.
- Reliable public tab-leave/anti-cheating protection.
- A general customer-facing/basic chatbot.
- Private Google Drive integration.
- OCR in any language.
- WhatsApp Business integration; a share link is not integration.
- Custom domains.
- Online checkout, card payment, automatic renewal, invoices, refunds, shipping, or order management.
- Advanced/cross-project analytics, automated anomaly detection, or scheduled reports.
- Guaranteed reservation confirmation emails while the notification worker is disabled.
- Production-ready e-commerce.
- Any uptime, backup frequency, restore guarantee, or support response time not supported by an operating process.
- “5 GB included” until storage readiness and plan-specific enforcement are operational.

## 13. Technical work required to enforce the plans

Priority order:

1. **Restore storage availability.** Diagnose the current readiness failure without weakening the probe. Verify builder uploads, private uploads, generated artifacts, quota finalization/release, and low-disk protections.
2. **Create one versioned product catalog.** Store canonical plan IDs, display names, prices, included modules, and limits server-side. Generate/consume it in public pricing, checkout requests, admin billing, “My Plan,” publish gates, and AI limit resolution.
3. **Add tenant-month usage ledgers.** Atomically count accepted form submissions, reservations, AI provider usage/tokens/cost, email sends, OCR pages, and relevant exports. Define UTC reset, idempotency, late events, and admin adjustments.
4. **Enforce module and quantity entitlements at the backend.** UI hiding is insufficient. Gate publishing, active projects, forms, reservations, storage reservation, calendar, AI, and future integrations.
5. **Implement grace/hard-stop behavior.** Specify warning thresholds, existing-data access, rejected writes, overage packs, downgrade behavior, canceled/past-due behavior, and audit events.
6. **Implement workspace team management.** Invitations, acceptance, role changes, removal, ownership transfer, last-owner protections, and server-side seat checks.
7. **Make usage visible.** Replace static `MyPlanPage` sample values with authoritative API data and show reset dates and consequences.
8. **Complete lifecycle controls.** Customer account closure, project/submission/reservation deletion, tenant export, storage-object cleanup, retention, and cancellation handling.
9. **Harden background operations.** Decide whether notification delivery is required; deploy it if so, monitor queues/dead letters, and align readiness. Add parser isolation and provider-failure monitoring.
10. **Operationalize backups.** Schedule, retain, encrypt off-host, test restore, record results, and enable freshness checks.
11. **Reconcile migrations.** Verify the production applied-migration ledger through every source migration used by an advertised feature. Auto-deployment currently does not apply migrations.
12. **Add acceptance and load coverage.** Browser E2E for published forms/quizzes/reservations, storage/concurrency tests, provider sync tests, and capacity tests tied to the chosen limits.

## 14. Final recommended pricing-page copy

The following is ready for frontend layout work **after** the launch prerequisites and founder decisions are resolved. It intentionally excludes unsupported features.

---

### Simple plans for the way you work

Build a site, collect responses, and manage your work from one place. All prices are monthly in USD. Plans are activated after your request is reviewed.

#### Forms — $15/month

For surveys, registrations, and information collection.

- Up to 10 active forms
- 1,000 submissions each month
- Hosted public form links
- Response search, filters, status, and overview
- Data import and standard analysis tools
- 1 GB hosted storage
- 1 workspace operator

**Choose Forms**

#### Website — $20/month

For individuals and small businesses that need a professional online presence.

- 1 website on a Madar subdomain
- Up to 3 active projects
- Visual page builder and image uploads
- Up to 3 forms and 500 submissions each month
- 2 GB hosted storage
- 1 workspace operator

**Choose Website**

#### Business — $25/month

For businesses that need a website, forms, and practical data tools.

- Everything in Website
- Up to 5 active projects
- Up to 15 forms
- 2,500 submissions each month
- Standard data cleaning, charts, and exports
- 5 GB hosted storage
- 1 workspace operator

**Choose Business**

#### Business Plus — $30/month

For service businesses that also manage booking requests and schedules.

- Everything in Business
- Up to 8 active projects
- Up to 25 forms
- 5,000 submissions each month
- Up to 500 reservation requests each month
- Reservation management and internal calendar
- 5 GB hosted storage
- 1 workspace operator
- Priority email support

**Choose Business Plus**

### Optional capacity

- 5 GB additional storage: `$5/month`
- 1,000 additional form submissions: `$5/month`
- 500 additional reservation requests: `$5/month`

Need a different limit? Contact Madar for a reviewed plan.

### Important notes

- Websites use a Madar subdomain. Custom domains are not currently included.
- Online payments, hosted email mailboxes, and WhatsApp Business messaging are not included.
- Google and Microsoft calendar connections may be offered separately as beta features.
- Availability, taxes, payment method, cancellation, and support terms are confirmed before activation.

---

Before publishing this copy, the frontend team must not remove the qualifications, and the founders/legal adviser must decide taxes, accepted payment method, refund/cancellation, support language, and whether “priority” has an operational definition.

## 15. Evidence appendix

### Important code and schema

| Area | Paths/symbols inspected |
|---|---|
| App/router topology | `backend/app.py:248-272`; `backend/routes/`; `backend/data_analysis/routes/` |
| Auth/session/CSRF | `backend/services/auth_service.py`; `backend/services/csrf_service.py`; `backend/routes/auth_routes.py`; `backend/routes/password_routes.py` |
| MFA/admin access | `backend/routes/mfa_routes.py`; `backend/services/admin_account_access_service.py`; admin routes and AAL2 tests |
| Tenants/roles | `backend/services/tenant_service.py`; `database/migrations/002_create_tenants_and_memberships.sql` |
| Billing | `backend/routes/billing_routes.py`; `backend/services/billing_service.py`; `database/migrations/016_create_features_table.sql`; `045_add_platform_safety.sql` |
| Current pricing UI | `frontend/src/content/pages/pricingContent.js`; `frontend/src/components/MainPages/BasePlansPage.jsx`; `frontend/src/components/DashboardBuilder/MyPlanPage.jsx` |
| Builder | `backend/routes/builder_routes.py`; `backend/services/builder_project_service.py`; `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`; `database/migrations/032_create_builder_projects.sql` |
| Publishing/public sites | `backend/routes/public_site_routes.py`; `backend/services/public_site_service.py`; `backend/services/website_service.py`; migrations 052–055 |
| Forms | `backend/services/builder_submission_service.py`; `frontend/src/components/PageBuilder/responses/`; `backend/tests/test_builder_form_submissions.py` |
| Quizzes/runtime | `frontend/src/components/PageBuilder/preview/BuilderFormPreviewPage.jsx`; `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx` |
| Reservations | `backend/services/builder_reservation_service.py`; reservation frontend; migrations 057–058; reservation tests |
| Calendar | `backend/routes/calendar_routes.py`; calendar services/workers; migrations 061–069; calendar tests |
| Notifications | `backend/routes/notification_routes.py`; `backend/services/notification_service.py`; `backend/workers/notification_worker.py`; `frontend/public/service-worker.js` |
| Storage/assets | `backend/services/storage_quota_service.py`; `backend/services/builder_asset_service.py`; migration 056; storage/upload tests |
| Data workspace | `backend/data_analysis/`; `frontend/src/components/PageBuilder/DataAnalysisWorkspace/`; data privacy/export/large-dataset tests |
| AI | AI services/routes; migrations 037 and 039; `backend/tests/test_ai_usage_routes.py` |
| E-commerce | migration 070; `backend/routes/ecommerce_routes.py`; cache service; e-commerce frontend and tests |
| Infrastructure | `docker-compose.yml`; backend/frontend Dockerfiles; health/readiness service; scripts under `scripts/` |
| Deployment | `/etc/systemd/system/madar-auto-deploy.service`; `/usr/local/sbin/madar-auto-deploy`; `/home/madar/docker_auto.sh` (read-only inspection) |
| Backup/restore | `scripts/backup_madar.sh`; `scripts/restore_madar.sh`; `scripts/verify_backup.sh`; `docs/backup-restore-runbook.md` |

### Representative tests

The audit used tests as corroborating evidence, not as proof of deployed behavior. Relevant suites include:

- `backend/tests/test_authorization_matrix.py`
- `backend/tests/test_security_foundation.py`
- `backend/tests/test_admin_mfa_aal2_enforcement.py`
- `backend/tests/test_builder_backend_hardening.py`
- `backend/tests/test_builder_form_submissions.py`
- `backend/tests/test_builder_reservations.py`
- `backend/tests/test_calendar_routes.py`
- `backend/tests/test_calendar_inbound_sync.py`
- `backend/tests/test_notification_worker.py`
- `backend/tests/test_storage_quota_service.py`
- `backend/tests/test_data_upload_privacy.py`
- `backend/tests/test_large_dataset_processing.py`
- `backend/tests/test_ai_usage_routes.py`
- `backend/tests/test_billing_publish_admin_safety.py`

### Commands and observations

Read-only inspection included:

```text
git status --short
git branch --show-current
git remote -v
git fetch --all --prune
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count HEAD...origin/main
git log --oneline --decorate --max-count=10
rg / rg --files searches across backend, frontend, migrations, tests, docs and scripts
docker compose ps
docker ps
systemctl status/cat for Madar deployment automation
curl http://127.0.0.1:8001/health/ready
```

No destructive migration, database write, service restart, deployment, secret-value output, test data mutation, commit, push, or pull was performed. Only this report was created.

## Final conclusion

Madar can support paid early-access customers, but the honest offer today is narrower than the proposed marketing list. The platform’s real value is the builder, Madar-hosted publication, durable forms and reservations, secure multi-tenancy, and practical data tools. Pricing should sell those outcomes with enforceable caps. It should not use “business email,” “unlimited users,” “basic chatbot,” Drive, OCR, WhatsApp, public anti-cheating, or advanced analytics as filler.

The `$15 / $20 / $25 / $30` ladder is viable if Madar first repairs live storage, operationalizes backups and notifications, reconciles migrations, centralizes product definitions, and implements tenant-level entitlements and metering. Until then, use manual pilot activation and explicitly review each customer’s usage rather than implying a fully automated subscription service.
