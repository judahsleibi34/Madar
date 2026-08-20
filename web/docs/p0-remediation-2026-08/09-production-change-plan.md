# Production change plan

This plan is prepared but not authorized for execution until every gate is green.

## Global preconditions

- verified current local recovery points;
- verified encrypted off-host copies with remote object/version identity;
- approved Mailcow recovery execution gate;
- protected replacement credentials available without appearing in CLI arguments/logs;
- approved maintenance window and operator presence;
- deployment locks acquired and auto-deploy races prevented;
- old image IDs/digests recorded and retained;
- rollback/forward-repair decision recorded.

## Madar gate

- [x] current coherent local backup exists and checksums pass;
- [~] restore verified for public schema/files; full Supabase platform restore remains unavailable;
- [x] direct SQL call paths inventoried;
- [x] development runtime removes direct PostgreSQL URL;
- [x] auth/tenant/builder/forms/reservations/storage/billing/workers/readiness regression suite covered;
- [x] runtime service credential-propagation regression test passes;
- [ ] off-host copy exists and verifies;
- [ ] provider-side replacement credentials exist;
- [ ] provider-compatible full restore path is proven;
- [ ] old credential revocation test is ready with provider authority.

### Madar bounded sequence

1. Confirm off-host backup and recovery owner.
2. Issue operator-only replacement DB credential; do not inject it into runtime.
3. Deploy Compose override to API/notification/calendar one service at a time.
4. Verify direct URL absent/empty, readiness, auth, tenant isolation, billing/quota, queues, and logs.
5. Rotate service-role/anon keys using provider-supported overlap and defined session impact.
6. Revoke exposed direct credential and terminate old sessions.
7. Prove old credentials fail.
8. Retire or re-encrypt historical environment copies.

## Briefedly deployment gate

- [x] current local production DB backup exists;
- [x] dump integrity and isolated restore pass;
- [x] five-migration rehearsal passes;
- [x] proposed runtime role is non-superuser;
- [x] migrator works and runtime cannot migrate/DDL;
- [x] source DB container no longer receives application/Gmail/encryption/Ollama env;
- [x] production-shaped backend and worker validate authenticated HTTPS configuration;
- [x] auth/session/CSRF, OAuth, imports/reports, privacy, and PostgreSQL tests pass;
- [x] migration forward-repair policy documented;
- [x] post-deploy health checks defined;
- [ ] encrypted off-host copy exists and verifies;
- [ ] real authenticated HTTPS Ollama gateway connectivity passes for backend and worker;
- [ ] current production image IDs/digests are retained in an approved rollback record;
- [ ] maintenance window is approved.

### Briefedly bounded sequence

1. Disable/rule out deployment races and acquire lock.
2. Record SHA, image IDs, Compose identity, DB revision, service state, and aggregate data counts.
3. Reverify local and off-host backups.
4. Verify real Ollama TLS identity/token/model readiness from backend and worker images.
5. Create DBA/owner/migrator/runtime/backup roles using protected environment injection.
6. Test runtime positive and negative operations without removing legacy access.
7. Drain writes and run Alembic as migrator.
8. Verify target revision, ownership, grants, constraints, and aggregates.
9. Start backend using runtime credential; verify `/status`, auth/session/CSRF and logs.
10. Start worker using runtime credential; verify heartbeat, lease, and a synthetic non-customer job.
11. Update frontend; verify headers and browser smoke flows.
12. Cut DB backup tooling to backup role.
13. Rotate/disable/rename legacy bootstrap role and terminate its sessions.
14. Prove old identity fails; inspect logs.
15. Record final SHA/image/config/revision/service identity.

## Rollback/forward repair

Before migrations create new-version data, old images may be restarted against a schema-compatibility assessment. After new writes, do not blindly downgrade. Keep the DB at the migrated schema and forward-repair application/migration defects, restoring from verified backup only for catastrophic unrecoverable corruption with explicit data-loss acknowledgement.

## Current decision

**DO NOT DEPLOY.** Required external gates are red.
