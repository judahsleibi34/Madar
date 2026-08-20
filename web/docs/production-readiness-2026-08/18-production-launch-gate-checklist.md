# Production launch gate checklist

Current live status is evidence-based and remains **NO-GO** for expansion to paying or sensitive customers. Development intent does not satisfy a production gate.

## Madar controlled beta — NO-GO now

Hard blockers: P0 credential rotation/runtime superuser removal; current coherent off-host/offline backup and isolated restore; current production readiness schema signal/deployment; root/firewall/SSH evidence; basic external monitoring; tenant-isolation certification for beta surface; safe hostile-file policy or uploads constrained to a proven safe subset; account/privacy/support disclosures. After those close, a small invited low-sensitivity beta may receive conditional approval with explicit quotas and rollback.

## Madar paying customers — NO-GO

All beta gates plus immutable controlled deployment, alert/on-call/SLOs, billing authority and entitlement failure tests, complete retention/export/delete, current dependency/security scan, Mailcow/email reliability if sold as dependency, performance/noisy-neighbor certification, recurring backup/restore proof and incident runbooks/tabletop.

## Madar sensitive business customers — NO-GO

All paying gates plus independent penetration test, complete ASVS Level-2-style evidence, hostile-content quarantine/scanning/parser sandbox and cookie-less asset delivery, security/audit-log controls, provider/subprocessor and contract/counsel approval, measured replacement-host recovery and stronger RPO/RTO appropriate to the offer.

## Briefedly developer/testing — CONDITIONAL GO

Synthetic/mock/test accounts and disposable data only. Preserve strict HTTPS/bearer policy; no private Gmail production data; no claim that production worker/schema is current. Development least-privilege roles and migration rehearsals remain usable.

## Briefedly private Gmail beta — NO-GO

P0 closure; off-host backup/restore; real authenticated HTTPS Ollama validation; production least-privilege roles/migrations/current backend+frontend+worker; PKCE and durable provider revocation retry; Google verified production project/brand/consent/Restricted-scope verification and designated security assessment; privacy lifecycle, AI prompt/evidence isolation, workspace penetration matrix, monitoring/alerts and incident route.

## Briefedly paying Gmail customers — NO-GO

All Gmail-beta gates plus commercial terms/support/SLO, measured Node B capacity/fairness, immutable deployment/rollback, recurring restore drills, external application/AI security testing, vulnerability/SBOM program, retention/export/delete certification and approved Limited Use/subprocessor/counsel materials.

## Server infrastructure host — NO-GO for sensitive expansion

Hard blockers: P0 recovery and credential closure; effective root-level SSH/firewall/Docker dual-stack verification and hardening; two-node/backup power design; Docker-root/Portainer/legacy dispositions; off-host monitoring; Mailcow coherent restore and perimeter review; patch/reboot program; physically separate encrypted recovery copies; replacement-host drill.

## Approval record

Each gate is signed by product, security, operations/SRE and privacy/counsel as applicable. Approval records exact Git/image/schema/config identity, test reports, known residual risk, capacity/tenant limits, rollback, start/end date and owner. Any identity drift or expired evidence reopens the relevant gate.
