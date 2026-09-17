# Madar pre-GO readiness evidence

This directory is the current operator-facing evidence set for the 2026-08-25 Node 1 staging hardening campaign. Start with `00-executive-summary.md`, use `18-operational-runbooks.md` during incidents, and use `23-production-promotion-readiness.md` for the controlled future production promotion. Historical audit directories remain evidence, not current runbooks.

The only intentionally deferred launch prerequisites are authorized commercial mappings for the 12 real tenants, dedicated physical backup media with a full replacement-host restore, and the future provider-neutral payment gateway. No production assignment, traffic switch, customer deletion, or external-provider call is performed by this evidence set.

## Current source-of-truth index

- Decision and gate status: `00-executive-summary.md`, `20-findings-register.md`, `21-updated-g1-g23-scorecard.md`
- Staging deploy/migration/rollback: `02-staging-architecture.md` through `05-rollback-failure-injection.md`
- Security and lifecycle: `06-two-tenant-adversarial-e2e.md` through `08-auth-mfa-security-validation.md`
- Storage, Redis, workers, and health: `09-storage-quota-validation.md` through `12-observability-alerting.md`
- Capacity, database, configuration, integrations, and supply chain: `13-performance-load-capacity.md` through `17-supply-chain-ci.md`
- Incident response: `18-operational-runbooks.md`
- Exact validation: `19-full-test-results.md`
- Controlled future promotion: `23-production-promotion-readiness.md`
- Deferred prerequisites and next actions: `22-deferred-prerequisites.md`, `24-next-actions.md`

Earlier audit/remediation directories are historical evidence and must not be used as current operational instructions where they conflict with this index.
