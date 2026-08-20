# P0 remediation executive summary

Audit/remediation date: 2026-08-18 UTC

## Outcome

P0 STATUS: **BLOCKED**

The development implementation, least-privilege database design, current local recovery points, and isolated migration/restore rehearsals are complete. Production was deliberately left unchanged because two mandatory gates cannot currently be satisfied:

1. there is no configured off-host backup destination or restricted backup credential; and
2. there is no reachable authenticated HTTPS Ollama gateway with a validated certificate and application token for a real production preflight.

Rotating/revoking credentials or reconciling Briefedly production before those gates would violate the approved safety order. The current sensitive-production posture therefore remains **NO-GO**.

## Finding status

| Finding | Status | Evidence summary |
|---|---|---|
| AUDIT-SEC-001 | BLOCKED | Credential classes and consumers are inventoried, but provider-side rotation/revocation was not performed. During remediation, a separate hardcoded host PostgreSQL administrator password was accidentally rendered in the tool transcript; it is now an additional incident credential class. |
| MADAR-DB-001 | PARTIALLY FIXED | Development Compose removes the direct PostgreSQL URL from all Madar runtime services; call-graph review confirms it is operator-tooling-only. Production containers still receive the old credential because the production gate failed. |
| BRF-DB-001 | PARTIALLY FIXED | Owner/migrator/runtime/backup role SQL and tests pass on restored clones. Production `briefedly_app` remains a superuser because no production mutation was authorized past the failed gate. |
| DR-001 | PARTIALLY FIXED | Fresh Madar and Briefedly local backups exist and isolated restores were demonstrated. No off-host copy, schedule, or Mailcow-consistent backup exists. |
| BRF-OPS-001 | BLOCKED | Current source, five migrations, worker, role split, and rollout were rehearsed. Live production remains at the old schema/runtime with no worker. |
| BRF-DEP-001 | PARTIALLY FIXED | Current source now requires authenticated HTTPS for remote Ollama and sends a bearer token. No real gateway endpoint/token was available for production-shaped connectivity verification. |

## Material achievements

- Fresh coherent Madar recovery set with database, builder assets, private uploads, generated artifacts, avatars, manifest, and checksums.
- Fresh Briefedly custom-format PostgreSQL dump with checksum and structural verification.
- Madar partial isolated restore plus exact asset/registry reconciliation.
- Briefedly isolated restore, five-revision upgrade, fresh zero-to-head upgrade, downgrade/forward rehearsal, and data-count preservation.
- Tested Briefedly least-privilege role architecture with negative DDL/admin assertions.
- Strict Ollama transport configuration and authenticated request support implemented in development.
- Migration credentials separated from runtime credentials in Briefedly Compose and deploy tooling.
- Madar runtime services explicitly drop the direct PostgreSQL variable in development Compose.

## Immediate operator decisions required

1. Provision an encrypted, versioned, off-host destination and restricted credentials.
2. Provision an authenticated HTTPS Ollama gateway (or a local authenticated proxy with a constrained Tailscale leg) and provide the application token through protected configuration.
3. Schedule a maintenance window for Mailcow’s supported consistency-aware backup procedure.
4. Provide Supabase/provider authority for coordinated key rotation and old-key revocation.
5. Approve the bounded production change plan only after every checklist item in `09-production-change-plan.md` is green.

No production database role, schema, application credential, container, or service was changed. No production deployment was performed.
