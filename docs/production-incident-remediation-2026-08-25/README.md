# Madar production incident remediation

This directory is the source of truth for the 2026-08-25 failed-deployment incident and controlled recovery/promotion.

- [Executive summary](00-executive-summary.md)
- [Timeline](01-incident-timeline.md)
- [Root cause](02-root-cause-analysis.md)
- [Production baseline](03-production-baseline.md)
- [Runtime configuration](04-runtime-config-remediation.md)
- [CSRF secret](05-csrf-secret-remediation.md)
- [Remote ingestion](06-remote-ingestion-policy.md)
- [Deployment path](07-deployment-path-remediation.md)
- [Retry-storm prevention](08-auto-deploy-retry-storm-fix.md)
- [Release identity](09-immutable-release-validation.md)
- [Database migration](10-database-migration-state.md)
- [CSP/frontend](11-csp-frontend-remediation.md)
- [Staging rehearsal](12-staging-rehearsal.md)
- [Production promotion](13-production-promotion.md)
- [Post-promotion validation](14-post-promotion-validation.md)
- [systemd state](15-systemd-final-state.md)
- [Rollback state](16-rollback-state.md)
- [Tests](17-test-results.md)
- [Remaining risks](18-remaining-risks.md)
- [Final readiness](19-final-production-readiness.md)
- [Login API-origin regression](20-login-api-origin-regression.md)
- [Supabase Secret API Key compatibility](21-supabase-secret-key-compatibility.md)
- [Supabase compatibility production promotion](22-supabase-compatibility-production-promotion.md)
- [Supabase Secret API key rotation cutover](23-supabase-secret-rotation-cutover.md)

No secret values are recorded in these reports.
