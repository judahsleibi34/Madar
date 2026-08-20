# Multi-tenant and workspace isolation verification matrix

## Test method

For every row create Tenant/Workspace A and B, same-role users, UUID-shaped guessed IDs, deleted/stale objects, and where schema permits duplicate/ambiguous state. Exercise list/detail/create/update/delete, child attachment, indirect reference, export, background job, cache, and public-resolution paths. Assert 404 for non-enumerating object access, 403 only where existence disclosure is intentional, no B row mutation, no B quota/job effect, and no B identifier/body in logs or responses.

Roles: `U0` unauthenticated, `U1` unrelated authenticated, `M` member, `A` tenant/workspace admin, `O` owner, `S` support/global admin. Support context must never silently become ordinary customer context; global operations require explicit AAL2 and audit.

## Madar matrix

| Object/path | Positive authority | Mandatory negative cases | Current evidence | Gap/status |
|---|---|---|---|---|
| account/profile | self; explicit global admin | U1/M/A cannot read/update/delete B identity | auth/profile/admin suites | manual session replay and account export drill |
| membership/roles | O/A by policy | member cannot promote; A tenant cannot assign B user/project; last/global admin protected | authorization matrix, tenant-user, site-member tests | duplicate invitation/concurrency E2E |
| projects/drafts | project role in tenant | guessed B ID, B revision, B role, cross-tenant copy/attach | builder hardening and authorization suites | full API corpus test |
| publication snapshots | project publisher | publish/activate B; stale revision; bind B snapshot/site; replay old ETag | publication isolation and publish safety | external cache runtime test |
| websites/hostnames/subdomains | authorized tenant/project | ambiguous/duplicate mapping, wrong bound project, Unicode/case/trailing-dot collision | public-site code and website tests | DB duplicate-injection integration test |
| pages/header/footer/settings | selected publication only | mix live B settings/page into A snapshot; duplicate route/home | public-site and renderer tests | two known renderer failures remain |
| forms | published A form | reference B form/project/publication; guessed ID; stale form | form-submission suite | browser/manual malformed payload corpus |
| submissions/tests/results | tenant dashboard permission | read/export/delete B; client-forged answer/result; CSV formula | form tests and export neutralization | retention/delete end-to-end |
| reservations/availability | published block and tenant operators | B block/project; double-book; cancel token replay; timezone boundary | reservation RPC/tests | PostgreSQL simultaneous-booking certification |
| calendar/events/tasks | member/visibility/role | B calendar/event/task/dependency/OAuth state; cache key collision | calendar authorization/routes/cache tests | provider webhook/manual multi-tenant drill |
| OAuth connections | owning user/tenant authority | consume B state/connection/token; callback user mismatch | calendar OAuth tests | provider-side revocation/outage drill |
| assets/storage objects | tenant/project ownership | B asset ID in draft/publication; direct download; replacement/delete; symlink path | asset registry/upload/storage/public routes | cookie-less origin and hostile corpus |
| storage reservations/accounts | tenant/user scope | consume/release B reservation; concurrent overquota; negative bytes | quota/accounting tests | production-shaped concurrent DB test |
| datasets/charts/reports | tenant/user/project scope | B dataset/cache/chart/file path; cross-user private report | data privacy/cache/report tests | lifecycle reconciliation drill |
| analytics/events | selected site/tenant | inject/read B event; cache key omission; unbounded anonymous flood | route/static review | dedicated isolation/abuse integration suite |
| notifications/preferences/push | tenant/user target | subscribe/read/action B; forged action URL; cross-tenant dedupe | notification suites | real push-provider manual test |
| entitlements/AI usage | tenant subscription/account | forged plan/add-on; consume B quota; concurrent reservations | entitlement/token suites | payment-authority integration absent |
| audit/support/admin | AAL2 global or consent session | support cookie on builder/admin; cross-tenant destructive action; log secret | admin access/MFA/audit suites | second-admin recovery ceremony |
| cache/ETag/browser state | tenant/project/publication/user key | replay B response; user/tenant switch; stale localStorage; service-worker auth cache | cache/runtime/recovery tests | browser cross-profile/manual cache test |

Mandatory Madar integration scenario: create colliding resource identifiers wherever possible; make A reference B through every foreign-key-like request field; assert request rejection and unchanged aggregate counts for both tenants. Create duplicate hostname/project/page/form state directly only in a disposable DB and prove public resolution fails closed.

## Briefedly matrix

| Object/path | Positive authority | Mandatory negative cases | Current evidence | Gap/status |
|---|---|---|---|---|
| workspace | membership; O/A mutation | U0/U1 cannot enumerate/read/update/delete B | auth/workspace suite | external manual enumeration |
| membership/role | O/A policy | member promotion/removal; cross-workspace user/child | auth/workspace suite | concurrent last-owner test |
| Gmail connection | O/A provider operator | M cannot connect/search/import/disconnect; A cannot use B connection | Gmail foundation tests | PKCE and revocation retry not implemented |
| OAuth nonce/state | initiating user/workspace | callback user/workspace/provider mismatch, expiry, replay, concurrent consume | durable nonce tests | PKCE verifier storage required |
| threads/messages | workspace member by documented collaboration policy | U1 or A member with B IDs; mixed connection/thread child | Gmail and composite-FK tests | production constraint migration pending |
| import jobs/background jobs | initiating workspace authority | claim/status/cancel B job; target-key collision; lease theft | durable/postgres job tests | per-workspace fairness metrics |
| reports/sources | workspace member | B report/source/message; fabricated evidence ID; mixed FK | AI report/composite-FK tests | adversarial semantic red-team corpus |
| sessions | self | token/session of B; revoked/token-version replay; CSRF cross-user | auth/security suites | multi-replica revocation test |
| rate buckets | scoped subject/workspace/global | cause B-only denial; evade by worker/process; bucket collision | rate-limit tests | distributed capacity test |
| exports/deletion/retention | recent-password O/self policy | retrieve B artifact; delete B; expired URL; worker retry cross-scope | privacy lifecycle tests | live worker/schema and backup-aging proof |

## Required role matrix

Every endpoint is exercised as U0, U1, member, admin, owner, and support/global admin if present. Positive tests prove the least privileged intended role works. Negative tests assert response, database aggregate, filesystem/object aggregate, queue aggregate, audit event, and cache behavior. Never grant broader DB privileges to make these tests pass.

## Certification gate

`PASS WITH EVIDENCE` requires isolated PostgreSQL/Supabase-shaped runtime tests, not mock-only evidence; exact code/image/schema identity; no unexpected query/log content; and a manual WSTG-style IDOR review. Existing unit tests are substantial but do not yet constitute final tenant penetration certification.
