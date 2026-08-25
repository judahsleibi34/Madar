# Staging rehearsal

Before production mutation, the exact immutable candidate was exercised on Node 1 staging with disposable PostgreSQL 17, staging Redis/storage, loopback-only slots, and no customer traffic.

Evidence included candidate liveness/readiness/version, frontend availability, worker separation, schema 81→82→83, migration locks/checksums, traffic switch, rollback, retained artifacts, bad-SHA suppression, concurrent deploy rejection, and interruption recovery.

Production-specific rehearsal used a non-production CSRF secret, `APP_ENV=production`, remote ingestion disabled, exact schema range, and the real candidate SHA. The active slot survived all production candidate failures before switch.
