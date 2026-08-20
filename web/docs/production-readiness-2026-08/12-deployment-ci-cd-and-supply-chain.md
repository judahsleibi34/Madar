# Deployment, CI/CD, and supply-chain target

Status: **READY** for repository implementation; production credentials and deployment are excluded.

## Immutable promotion flow

```text
pull request
  -> pinned tests and lint/type/static analysis
  -> tenant/workspace isolation + migration rehearsal
  -> Python/npm advisories + secret scan + SAST
  -> container scan + SBOM
  -> reproducible image build
  -> sign/attest and record immutable digest/provenance
  -> protected production environment approval + concurrency lock
  -> preflight + current off-host backup gate
  -> migrator-only schema step
  -> digest deployment
  -> readiness + smoke + tenant-negative canary
  -> record runtime identity or rollback/forward repair
```

Production must not normally build mutable source. A registry holds current and previous-good immutable images. Compose/deployment references digests, records source SHA/SBOM/provenance/schema compatibility, and refuses floating tags. Database migrations declare expand/contract compatibility; irreversible changes require a tested forward-repair path and backups rather than an untested downgrade promise.

## GitHub controls

Use protected branches, required reviews/checks, CODEOWNERS for auth/migrations/deploy/security policy, GitHub Environments with explicit production approval, deployment concurrency, and least-privilege short-lived OIDC credentials where the registry/provider supports them. No production secret belongs in forks, PR workflows, repository variables, images, artifacts, test logs, or Compose output. Self-hosted runners must not run untrusted PR code on a host with production network/secrets.

## Required checks

- Python and npm lockfile-based unit/integration/security suites; PostgreSQL-backed tests for production semantics.
- tenant/workspace authorization matrix and migration from a sanitized production-shaped schema revision;
- secret scanner over commits and generated artifacts with verified redaction;
- Python/npm advisory reports with triage and expiration, not blind auto-upgrade;
- Dockerfile/Compose policy, image CVE scan, OS-package inventory, SBOM (CycloneDX or SPDX), signature/attestation and digest;
- license and new-dependency owner review; disallow unexpected Git/path dependencies and install scripts;
- production-shaped config validation using placeholders, never resolved production secrets.

## Deployment gates and rollback

Preflight captures current SHA, image digest, schema, services/workers, health and rollback image. It requires a verified off-host recovery point, valid secret references, available disk, migration rehearsal, secure Ollama path for Briefedly, and P0 approval. One lock prevents timers/operators/CI racing. Deploy one boundary at a time; migration credentials never reach runtime. Readiness gates promotion. Roll back code only when schema remains backward-compatible; otherwise execute the rehearsed forward repair. Automatic deploy remains disabled until this flow is proven.

## Supply-chain register

Inventory every base/application/service image and replace floating production tags only through reviewed updates and tested digests. Preserve Mailcow's vendor-supported update model and local dirty diff separately. Generate SBOMs for Madar/Briefedly images, track critical/high advisories with owner/due date/exploitability, scan OS packages, and record provenance. A zero-vulnerability build is not assumed; accepted risk must expire.

## Validation without production authority

Development workflows may use synthetic secrets, disposable PostgreSQL/Redis, mocked provider APIs and registry dry-runs. Before enabling CI, review permissions (`contents: read` by default), action SHAs, artifact confidentiality, cache poisoning, fork behavior and log redaction. Production environment/secrets and deploy permissions remain a later maintenance/provider gate.
