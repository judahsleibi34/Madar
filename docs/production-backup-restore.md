# Production Backup And Restore Runbook

This runbook defines the backup and restore readiness work required before a
Madar production launch. It does not prove that production backups are already
enabled. Record actual project settings, owners, backup locations, RPO, and RTO
during launch preparation.

## Scope

Backups must cover every durable data store used by the product:

- Supabase/Postgres database: application tables, RLS policies, functions,
  triggers, grants, migrations, audit logs, tenant data, builder projects,
  website settings, form submissions, billing feature state, MFA/security
  settings, notifications, and AI usage counters.
- Supabase Auth data: auth users, identities, password reset state, MFA factors
  if enabled, and auth configuration. Confirm the exact export and restore
  mechanism in the Supabase project before launch.
- Supabase Storage: the `avatars` bucket created by migration
  `022_create_avatars_storage_bucket.sql` and any future storage buckets.
- Public uploads: `PUBLIC_UPLOADS_DIR`, default `uploads`, including
  intentionally public builder assets.
- Private uploads: `DATA_UPLOAD_DIR`, default `private_uploads`, including
  CSV/XLS/XLSX data-analysis uploads and exported/user dataset files. This
  directory must not be publicly mounted.
- Private generated charts: `PRIVATE_CHARTS_DIR`, default
  `private_generated_charts`, including chart images and optional explorer HTML
  generated from private datasets. This directory must not be publicly mounted;
  charts and explorer HTML are served through authenticated visualization
  routes. Explorer HTML is dataset-derived and must remain private even when
  restored from backups.
- Avatar local fallback paths if configured by `AVATAR_UPLOAD_DIR`; the current
  code primarily uses Supabase Storage for avatars.
- Other generated files, if added later. Decide before launch whether generated
  artifacts are disposable cache artifacts or must be backed up.
- Runtime configuration references without secrets: expected env var names,
  container image tags, Compose/Kubernetes manifests, migration version, and
  deployment notes. Never store plaintext secrets in backup documentation.

## Backup Policy

Record the real launch values here before production:

| Item | Required Launch Value |
| --- | --- |
| Backup owner | TODO: name/team |
| Restore owner | TODO: name/team |
| Security approver | TODO: name/team |
| RPO | TODO: approved maximum data loss |
| RTO | TODO: approved maximum recovery time |
| Backup retention | TODO: duration and legal requirements |
| Backup encryption | TODO: provider/key-management details |
| Backup access group | TODO: least-privilege group |
| Restore rehearsal cadence | TODO: e.g. quarterly |

Minimum policy before launch:

- Confirm Supabase automatic backups are enabled for the production project.
- Confirm whether Supabase Point-in-Time Recovery is available for the selected
  plan and enable it if required by the approved RPO.
- Confirm how Supabase Auth and Storage are included in backups. Do not assume
  Postgres PITR alone covers Auth or Storage unless Supabase project
  documentation/settings prove it.
- Back up filesystem directories mounted by Docker Compose or infrastructure:
  `PUBLIC_UPLOADS_DIR`, `DATA_UPLOAD_DIR`, and `PRIVATE_CHARTS_DIR` if generated
  charts are classified as durable.
- Store backups encrypted at rest and in transit.
- Restrict backup access to production operators who also have approval to
  access customer data.
- Test restore into staging before first production launch and after any major
  schema/storage change.

## Supabase Backup And PITR Expectations

These items must be configured in Supabase project settings and verified before
launch:

1. Confirm the production project plan supports the required backup retention and
   PITR window.
2. Enable PITR if the approved RPO requires point-in-time restore.
3. Record the latest successful automatic backup timestamp.
4. Confirm database backups include `public` schema objects, RLS policies,
   functions, triggers, indexes, grants, and migration-created objects.
5. Confirm Supabase Auth recovery support for users, identities, and MFA state.
6. Confirm Supabase Storage backup/restore support for the `avatars` bucket.
7. Confirm who can initiate restore and what approval is required.

Do not launch production until the actual Supabase project settings have been
checked and recorded in the launch evidence.

## Manual Backup And Export Steps

Use provider-native backups as the source of truth. Manual exports are an
additional safety net before risky operations such as migrations.

Database manual export:

1. Identify the source environment and migration version.
2. Export schema and data with an approved database tool or Supabase-supported
   export workflow.
3. Store the export in the approved encrypted backup location.
4. Record checksum, export timestamp, source project, and operator.
5. Verify the export can be read by restoring it to a temporary or staging
   database.

Filesystem/object manual export:

1. Export `PUBLIC_UPLOADS_DIR`.
2. Export `DATA_UPLOAD_DIR`.
3. Export `PRIVATE_CHARTS_DIR` only if generated charts are classified as
   durable.
4. Export Supabase Storage buckets, including `avatars`, using the approved
   provider workflow.
5. Preserve file metadata where possible.
6. Record counts, total bytes, checksums or manifest hashes, and export time.

Configuration reference export:

1. Export env var names and non-secret operational values.
2. Record the secret manager path names or key aliases, not secret values.
3. Record container image tags and deployment commit SHA.
4. Record currently applied migration files from `database/migrations` and
   `supabase/migrations`.

## Restore To Staging Procedure

Use this procedure for every restore rehearsal and before high-risk production
changes.

1. Open an incident/change ticket for the rehearsal.
2. Select a backup source and record its timestamp.
3. Provision or reset the staging restore target.
4. Restore the Supabase/Postgres database into staging.
5. Restore Supabase Auth data if the provider workflow supports it. If not,
   record the limitation and test application data integrity with staging auth
   accounts.
6. Restore Supabase Storage buckets such as `avatars`.
7. Restore filesystem directories:
   - `PUBLIC_UPLOADS_DIR`
   - `DATA_UPLOAD_DIR`
   - `PRIVATE_CHARTS_DIR` if durable
8. Deploy the matching backend/frontend version or a controlled restore-test
   build.
9. Set staging env vars to point only at staging resources. Never point staging
   app instances at production storage, auth, or databases.
10. Run post-restore validation checks from this document.
11. Record results in the restore rehearsal log.
12. Destroy temporary restore targets when no longer needed, according to the
   approved data-handling policy.

## Emergency Restore To Production Procedure

Use only for an approved production incident. Prefer restoring to a new
environment and switching traffic after validation when time allows.

1. Declare incident owner, communications owner, database owner, and application
   owner.
2. Stop or restrict writes if continued writes would corrupt recovery. Examples:
   maintenance mode, backend scale-down, write route block, or proxy rule.
3. Record current production state: commit SHA, image tags, migration version,
   backup timestamps, and affected data stores.
4. Choose the restore point based on incident timeline and approved RPO.
5. Obtain required approval for production restore.
6. Restore database from Supabase backup/PITR or approved export.
7. Restore Auth and Storage according to Supabase-supported procedures.
8. Restore public/private upload directories from encrypted backup.
9. Apply only migrations that match the restored application version.
10. Run post-restore validation checks.
11. Re-enable traffic gradually.
12. Monitor error rates, login, signup, public site rendering, data upload/read,
    and audit logs.
13. Record final restored timestamp, known data loss window, customer impact, and
    follow-up tasks.

## Pre-Migration Backup Checklist

Complete before applying migrations to staging or production:

- Identify migration files to apply from `database/migrations` and
  `supabase/migrations`.
- Confirm both migration trees are aligned or document the authoritative source.
- Run migrations on a blank database.
- Run migrations on a copy of staging or production-like data.
- Confirm latest automated database backup completed successfully.
- Take or identify a manual pre-migration backup/export when the change is
  destructive or high-risk.
- Export affected filesystem/object storage if migration changes file references.
- Confirm rollback plan and restore point.
- Confirm maintenance window and operator availability.
- Confirm no plaintext secrets are included in backup artifacts.

## Post-Restore Validation Checklist

Run these checks after every staging rehearsal and production restore:

- Backend health checks pass: `/health/live` and `/health/ready`.
- Frontend loads and points at the expected backend origin.
- Login works for a test user.
- Admin access works for an approved test admin.
- Tenant onboarding works in staging or a non-production test tenant.
- Existing tenant dashboard loads.
- Published public site loads at `/site/<subdomain>/`.
- Builder project list, edit, and publish flows can read restored data.
- Public form submission capture works in staging.
- Form submission review works for an authenticated tenant member.
- Avatar URLs and Supabase Storage objects resolve as expected.
- Public builder assets under `/uploads/tenant_*/builder_assets/*` resolve.
- Private data uploads are not reachable through `/uploads`.
- Data-analysis upload, read, export, and chart generation work.
- Explorer HTML, if generated, is reachable only through authenticated
  tenant/user-scoped routes and includes attachment/CSP/nosniff/no-referrer/frame
  protection headers.
- Audit logging writes new events.
- Notification tables and web push subscriptions, if enabled, are intact.
- AI usage counters, if enabled, are present and bounded by expected limits.
- RLS policies are enabled on sensitive tables and direct anon/auth access is as
  expected.
- Row counts for critical tables match the backup manifest within expected
  variance.
- Sample tenant IDs, user IDs, builder project IDs, and form submission IDs match
  source records.
- Application logs show no repeated database, storage, auth, or migration errors.

## Data Integrity Verification

For every restore, record:

- Backup timestamp and restore completion timestamp.
- Critical table row counts before and after restore.
- Checksums or manifest hashes for exported filesystem directories.
- Count and total bytes for Supabase Storage buckets and local upload folders.
- Spot checks for representative tenants:
  - tenant row
  - user row
  - active membership
  - website settings
  - builder project
  - published site data
  - form submissions
  - private uploaded dataset, if applicable
- Known gaps, skipped checks, and reasons.

## Security Notes

- Backups contain customer data and must be treated as production-confidential.
- Do not store Supabase keys, JWTs, SMTP passwords, cookie secrets, or service
  role keys in this repository or in restore logs.
- Use least-privilege access and time-bound access for backup retrieval.
- Encrypt backups at rest and in transit.
- Prefer restore into isolated staging networks with production email/SMS/push
  delivery disabled.
- Scrub or destroy temporary restore environments after validation.
- Keep audit evidence for who accessed backup data and why.

## Restore Rehearsal Log Template

Copy this section for each rehearsal.

### Restore Rehearsal: YYYY-MM-DD

| Field | Value |
| --- | --- |
| Date | TODO |
| Environment | TODO: staging / temporary restore |
| Backup source | TODO: backup ID, timestamp, storage location reference |
| Restore target | TODO: project/database/storage target |
| Person responsible | TODO |
| Approver | TODO |
| Application commit/image | TODO |
| Database migration version | TODO |
| RPO tested | TODO |
| RTO measured | TODO |
| Final result | TODO: pass/fail/partial |

Steps performed:

1. TODO
2. TODO
3. TODO

Validation checks:

- [ ] Backend health checks passed.
- [ ] Auth/login validated.
- [ ] Admin access validated.
- [ ] Tenant dashboard validated.
- [ ] Public site validated.
- [ ] Builder data validated.
- [ ] Form submissions validated.
- [ ] Supabase Storage/avatar objects validated.
- [ ] Public uploads validated.
- [ ] Private uploads validated and not publicly served.
- [ ] Data-analysis upload/read/export validated.
- [ ] Audit logging validated.
- [ ] Critical row counts compared.
- [ ] Storage/file manifests compared.
- [ ] Logs reviewed.

Issues found:

- TODO

Follow-up tasks:

- TODO
