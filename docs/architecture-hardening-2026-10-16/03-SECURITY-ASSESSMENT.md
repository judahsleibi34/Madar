# Security findings and remediation status

This is a prioritized partial assessment, not an exhaustive certification.
No new confirmed P0 exposure was established. Incomplete coverage is not evidence
that other P0 issues are absent.

| Severity / priority | Finding | Disposition and evidence |
| --- | --- | --- |
| High/P1 | Production-like startup accepted CSRF disabled/missing-origin bypass; trusted-origin override concealed unsafe frontend origins | FIXED in runtime_config; both origin lists validated and bypass configs rejected. Adversarial tests and full suite PASS. Effective inspected production settings were already safe. |
| High/P1 | Malformed explicit Origin could fall back to trusted Referer; inconsistent cookie origin parsing | FIXED shared strict parser, no fallback for explicit malformed/null origin, staging secure-cookie default and consistent boolean handling. Valid Referer compatibility retained for absent Origin. |
| High/P1 integrity | In-flight cache reads republished after invalidation/clear | FIXED active fill fences for ecommerce/calendar; direct public settings/bounds generation guard. Thread/route race tests PASS. Current requests and cross-process TTL staleness remain. |
| High/P1 assurance |21 top-level tests silently missed by CI discovery | FIXED four modules converted with assertions preserved and explicit entitlement fixtures; AST guard added. |
| High/P1 | Privileged service-role queries bypass RLS | UNRESOLVED boundary risk, not a demonstrated all-route exploit.144 public tables have RLS; service_role BYPASSRLS confirmed read-only. Selected native tenant reads PASS, full route/worker/write audit incomplete. |
| High/P1 operational | main protected:false; repository rulesets empty | UNRESOLVED, GitHub API verified; credential can push but lacks admin. Requires owner ruleset/protection, not merely documentation. |
| High/P1 operational | COMMERCIAL_ENTITLEMENTS_ENFORCED=false in effective production | UNRESOLVED intentional all-capabilities operator policy. No live assignments/charging/enforcement change made. Native staging uses true and commercial readiness passed. |
| High/P1 reliability | Notification finish RPC lacks claim ownership/version | UNRESOLVED confirmed native FAIL in schema146/migration073; stale attempt1 completion accepted after attempt2 reclaimed the processing row. Needs compatible forward migration/worker rollout and concurrency proof. |
| Medium/P2 | Migration test DSN could select unverified/remote data | FIXED loopback/hostaddr/database-marker guard on every commercial fixture connection. Refusal tests and actual SQL rehearsals recorded. |
| Medium/P2 | Load probe follows redirects/environment proxy | FIXED no redirect/no proxy opener, finite timeout and safe URL validation; actual loopback redirect destination never called in regression test. |
| Medium/P2 | CI checkout credentials persisted; default token permissions broad | FIXED backend/frontend workflow contents:read, persist-credentials:false. Repository settings and mobile workflow were not changed by inference. |
| Medium/P2 | Calendar fill metadata retained per invalidated tenant | FIXED only active fill state retained/cleaned on success/error; bounded-cache TTL behavior preserved. |
| Medium/P2 | In-process cache invalidation does not reach other processes | UNRESOLVED TTL-limited consistency; no distributed invalidation claim. |
| Medium/P2 | Full native upload/SSRF/Auth/OAuth/AI adversarial audit incomplete | UNRESOLVED; preserve existing controls, no unrestricted model tools or new dependencies introduced. |

## Native authentication and authorization checks

Real GoTrue password success/failure, invalid JWT rejection, TOTP enrollment and
verification, AAL1 privileged denial/AAL2 admission, password-login MFA restriction,
origin403, pending-session single use/replay denial, refresh rotation and actual
admin browser login passed. Secure/HttpOnly/SameSite=Lax cookies and JS inability
to read access cookie passed on TLS staging. Effective production SameSite=None
is a different cross-origin configuration; no claim it was exercised in staging.
Two-tenant project reads and spoofed tenant/user inputs were tested natively.
No admin gate was removed or replaced by frontend visibility.

Private native Storage anonymous denial and mediated legacy synthetic avatar
access passed; the broader managed asset lifecycle/signature/quota/GC matrix
remains partial. No published customer asset or production object was modified.

## Secrets and privilege boundaries

Staging secrets generated privately; no production data or credential copied.
Source secret-file hygiene passed; this narrow checker is not a full historical
secret scan. Reports exclude auth material, private SQL query text and fixture
credentials. Restore archives stay private on VM. Production protected controller,
receipts, write authority, network, service state and migrations were untouched.
Only read-only metadata/configuration values from an explicit nonsensitive
allowlist were reported. Production file-only config validation is PARTIAL because
effective multi-layer settings and unavailable E2E fixture keys are not all in
that file. No false readiness PASS is inferred.
