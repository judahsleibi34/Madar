# Madar ecosystem readiness audit — executive summary

Audit date: 2026-08-24 UTC  
Node: `madarserver` (Node 1 only)  
Development: `builder-backend` at `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df`  
Production: `main` at the same commit  
Launch classification: **NO-GO**  
Overall readiness score: **58/100**

## Decision

Madar should not host paying multi-tenant customers in its current condition. No demonstrated cross-tenant content disclosure was found: live catalog checks found no duplicate host mappings, no publication/tenant ownership mismatch, no duplicate tenant settings, and two sampled published sites returned distinct bound publication identities. The hardened `hostname -> tenant -> site -> project -> publication` path remains substantially intact.

The NO-GO comes from six High issues with direct evidence:

1. Automatic deployment and rollback failed in production on 2026-08-23. The timer then retried builds repeatedly. The rollback rebuilds old source instead of selecting a prebuilt immutable image and has no database compatibility transaction.
2. Five live published projects contain 68 `quizCorrectAnswer` fields. A safe unauthenticated production GET confirmed the answer-key field is returned publicly. The backend always stores `quiz_result: null`; focus, timer, scoring, and attempt controls are browser-only.
3. Entitlement compatibility grants almost every catalog capability to unmigrated tenants. Production has 11 tenants, zero active canonical subscriptions, and zero active legacy feature tenants, so commercial enforcement is not effective.
4. Admin MFA login proceeds with ordinary cookies when no verified factor exists or factor lookup fails. Sensitive admin routes do independently require AAL2, but the login policy is not fail-closed.
5. Email notification delivery is not configured. Production has three real dead email deliveries with `smtp_not_configured`; readiness still reports ready.
6. A fresh local backup exists and verifies, but no Madar backup schedule, off-host encrypted generation, complete provider-compatible restore, or replacement-host recovery proof exists.

## Direct answers to the launch questions

| Question | Answer |
| --- | --- |
| Can Madar safely host real paying customers today? | **No.** The six High blockers above make launch unsafe or commercially unreliable. |
| Can one tenant receive another tenant's content? | **No exploit was demonstrated.** Strong tenant filters, atomic publication binding, database uniqueness, and live integrity checks support isolation. This is not a proof of absence; authenticated adversarial E2E coverage remains incomplete. |
| Can it deploy reliably? | **No.** A real deployment failed readiness and its automatic rollback also failed. |
| Can it safely roll back? | **No.** The current script rebuilds old source, does not retain a verified prior image, and cannot reverse or prove compatibility with database migrations. |
| Can it recover from database/server loss? | **Not fully.** A partial public-schema/files restore was rehearsed historically, but Supabase Auth/Storage/Vault/platform recovery and replacement-host recovery remain unproven. |
| Are backups real/current/restorable? | A complete 2026-08-23 local generation is real and its 92 checksums pass. It is manual, local, unencrypted by the tool, not scheduled, and not proven as a full service restore. |
| Are auth, MFA, CSRF, CORS, entitlements enforced? | Cookies, CSRF, exact-origin CORS, and sensitive-route AAL2 are strong. MFA login and canonical entitlements are not fail-closed. |
| Are public sites isolated? | The main published path is strong. The bootstrap endpoint reads mutable branding rather than snapshot branding; one live brand and one logo mismatch exist. |
| Are uploads/quotas trustworthy? | The 25 MiB image limit is exact and layered. Atomic quota RPCs are sound. Cleanup is not scheduled, 52 expired assets remain, avatars bypass quota accounting, and host files are broadly readable (`0644`). |
| Can forms/tests/reservations handle abuse/concurrency? | Forms/reservations have rate limits, idempotency and advisory-lock serialization. Quiz/test behavior is not server-enforced and answers are public. |
| Are workers production-ready? | Processes are healthy and push/internal delivery has succeeded, but SMTP is unavailable and health checks mask some delivery/dependency failures. |
| Are Critical/High issues unresolved? | **0 Critical; 6 High.** |
| Is Node 1 adequately resourced? | Present load/disk headroom is adequate for the small current workload, conditionally. Swap use reached 1.8 GiB and Docker build cache is 81.21 GiB (65.89 GiB reclaimable). No 1,000-tenant capacity proof exists. |
| What prevents GO? | Deployment/rollback failure, public quiz answers and browser-only tests, non-enforcing entitlements, MFA login gap, dead email delivery, and incomplete DR. |

## Score deductions

| Area | Weight | Earned | Primary deduction |
| --- | ---: | ---: | --- |
| Security/authentication | 15 | 9 | Admin login and factor-removal AAL fail-open paths |
| Tenant isolation | 15 | 13 | No demonstrated tenant leak; service-role architecture and incomplete adversarial E2E remain |
| Data/database integrity | 10 | 8 | Strong constraints; lifecycle and external-system atomicity gaps |
| Deployment/rollback | 10 | 2 | Confirmed failed rollback, retry storm, no immutable artifact |
| Backups/recovery | 10 | 3 | Valid local capture; no schedule/off-host/full restore |
| Builder/publication | 8 | 6 | Strong publication RPC; mutable bootstrap mismatch |
| Storage/uploads | 7 | 4 | Exact limits/atomic quota; cleanup, avatars, host modes |
| Forms/reservations | 5 | 2 | Reservations strong; quiz system unsafe |
| Notifications/workers | 5 | 2 | Workers/push run; email dead and readiness masks it |
| Tests | 5 | 3 | Broad suites; two deterministic frontend failures and timing flakiness |
| Observability/operations | 4 | 2 | Structured logs/IDs; no alerting and false-green dependencies |
| Performance/capacity | 3 | 2 | Current headroom; large bundles/cache and no load proof |
| Code quality | 3 | 2 | Good domain tests but oversized central modules |
| **Total** | **100** | **58** | Severe gates override the numeric score |

## Evidence limits

No production mutation, account creation, email, billing action, publish, upload, or reservation was performed. `/etc/cloudflared/config.yml` is root-only and could not be read; production routing was instead verified through systemd journal evidence, loopback bindings, and safe external HTTPS GETs. Authenticated cross-tenant attacks and a full restore require a purpose-built isolated environment and are marked not verified.
