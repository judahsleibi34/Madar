# Production Launch Checklist

This checklist is a launch gate for Madar production readiness. It is not
evidence that production is ready by itself; record actual values, links,
approvals, and test results during launch preparation.

## Ownership

| Area | Owner | Backup Owner | Status |
| --- | --- | --- | --- |
| Product launch approval | TODO | TODO | TODO |
| Backend/API | TODO | TODO | TODO |
| Frontend | TODO | TODO | TODO |
| Supabase/Postgres/Auth/Storage | TODO | TODO | TODO |
| Upload storage | TODO | TODO | TODO |
| Security/secrets | TODO | TODO | TODO |
| Monitoring/on-call | TODO | TODO | TODO |

## Backup And Restore

- [ ] Backup policy confirmed and documented in
  `docs/production-backup-restore.md`.
- [ ] Supabase automatic backups confirmed in production project settings.
- [ ] Supabase PITR support/window confirmed or risk accepted by launch owner.
- [ ] Supabase Auth backup/restore expectations confirmed.
- [ ] Supabase Storage backup/restore expectations confirmed.
- [ ] Public upload backup for `PUBLIC_UPLOADS_DIR` confirmed.
- [ ] Private upload backup for `DATA_UPLOAD_DIR` confirmed.
- [ ] Private generated chart/file retention decision recorded for
  `PRIVATE_CHARTS_DIR`.
- [ ] Restore rehearsal completed in staging.
- [ ] Restore rehearsal result logged in
  `docs/production-backup-restore.md` or linked launch evidence.
- [ ] RPO approved and recorded.
- [ ] RTO approved and recorded.
- [ ] Backup access is least-privilege and audited.

## Database And Migrations

- [ ] Authoritative migration process confirmed for `database/migrations` and
  `supabase/migrations`.
- [ ] Migrations tested on a blank database.
- [ ] Migrations tested on a copy of staging or production-like database.
- [ ] Pre-migration backup checklist completed.
- [ ] Rollback plan reviewed.
- [ ] RLS policies reviewed for sensitive tables.
- [ ] Direct anon/authenticated Supabase table access reviewed.
- [ ] Migration drift check completed against target environment.

## Storage And Data Privacy

- [ ] `PUBLIC_UPLOADS_DIR` points only to intentionally public assets.
- [ ] `DATA_UPLOAD_DIR` points to private storage and is not publicly mounted.
- [ ] `PRIVATE_CHARTS_DIR` points to private storage and is not publicly mounted.
- [ ] `/uploads` serves only public assets.
- [ ] Data-analysis CSV/XLS/XLSX uploads cannot be fetched from `/uploads`.
- [ ] Dataset-derived generated charts cannot be fetched from `/generated_charts`.
- [ ] Dataset-derived explorer HTML is served only through authenticated routes
  as an attachment with CSP, nosniff, no-referrer, and frame-deny headers.
- [ ] Supabase `avatars` bucket policy reviewed.
- [ ] Local Docker volumes or production persistent volumes are backed up.
- [ ] Horizontal scaling storage behavior is understood and documented.

## Environment And Secrets

- [ ] Production `FRONTEND_URLS` contains only production frontend origins.
- [ ] Production `VITE_API_URL` points to the production API origin.
- [ ] `COOKIE_SECURE=true`.
- [ ] `COOKIE_SAMESITE` value is approved for the deployment topology.
- [ ] CSRF settings are production-appropriate.
- [ ] Supabase URL and keys are present in the production secret manager.
- [ ] Service role key access is restricted.
- [ ] `TRUSTED_PROXY_IPS` contains only real proxy/tunnel peers.
- [ ] Rate limits are enabled and configured.
- [ ] Builder asset and avatar upload burst limits are configured.
- [ ] Visualization generation uses short-window per-user and per-tenant burst
  limits only; no daily visualization quota is configured unless explicitly
  approved as a product requirement.
- [ ] AI usage limits are configured if AI provider routes are enabled.
- [ ] AI routes have both daily plan quotas and short-window abuse rate limits.
- [ ] Billing launch mode is explicitly approved.
- [ ] No plaintext secrets are committed or copied into docs.

## Application Validation

- [ ] Backend image builds successfully.
- [ ] Frontend image builds successfully.
- [ ] Backend relevant test suite passed.
- [ ] Frontend build passed.
- [ ] `git diff --check` passed before release.
- [ ] Health checks verified: `/health/live` and `/health/ready`.
- [ ] Backend smoke tests run against the target environment.
- [ ] Signup/login/logout/session refresh verified.
- [ ] Admin access verified.
- [ ] Tenant onboarding verified.
- [ ] Dashboard loads for a tenant user.
- [ ] Builder project create/edit/publish verified.
- [ ] Public site route `/site/<subdomain>/` verified.
- [ ] Public form submission flow verified.
- [ ] Form submission review/status update verified.
- [ ] Avatar upload/read verified.
- [ ] Data upload/read/export verified.
- [ ] Spreadsheet exports verified to prefix formula-like CSV/XLSX cell values
  with a single quote before users open exported files, including backend
  exports and browser-side saved dataset/form-response downloads.
- [ ] Audit logs verified.

## Monitoring And Operations

- [ ] On-call owner assigned.
- [ ] Production log access verified.
- [ ] Error-rate monitoring configured.
- [ ] Latency monitoring configured.
- [ ] Supabase availability/error monitoring configured.
- [ ] Redis/rate-limit health monitoring configured if Redis is used.
- [ ] Disk or object-storage utilization alerts configured.
- [ ] Backup failure alerts configured.
- [ ] Security event/audit log review process defined.
- [ ] Incident escalation path documented.

## Final Launch Approval

| Gate | Approved By | Date | Notes |
| --- | --- | --- | --- |
| Security | TODO | TODO | TODO |
| Backup/restore | TODO | TODO | TODO |
| Database/migrations | TODO | TODO | TODO |
| Application readiness | TODO | TODO | TODO |
| Monitoring/on-call | TODO | TODO | TODO |
| Product/business | TODO | TODO | TODO |

Launch decision:

- [ ] Approved to launch.
- [ ] Approved with documented exceptions.
- [ ] Not approved.
