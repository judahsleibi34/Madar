# Security verification: ASVS 5, WSTG, tenant and AI testing

Status: **REQUIRES EXTERNAL ASSESSMENT** for final launch evidence. No live production attack was performed.

Baseline: OWASP ASVS 5.0.0 Level-2-style assurance, using versioned identifiers (`v5.0.0-*`). Code presence alone is never runtime proof. The authoritative ASVS release was checked 2026-08-19 at <https://github.com/OWASP/ASVS/releases>. Manual testing follows the current OWASP Web Security Testing Guide at <https://owasp.org/www-project-web-security-testing-guide/>.

## ASVS evidence register

| ASVS area | Madar | Briefedly | Required evidence/gap |
|---|---|---|---|
| V1 encoding/sanitization | PARTIAL | PARTIAL | hostile builder/email/AI output corpus and browser runtime checks |
| V2 validation/business logic | PARTIAL | PARTIAL | bounds, duplicate JSON, workflow abuse, concurrent quota/job tests |
| V3 web frontend | PARTIAL | PARTIAL | DOM XSS/open redirect/service-worker/browser-storage manual testing |
| V4 API/web services | PARTIAL | PARTIAL | complete endpoint inventory, mass assignment, pagination/rate tests |
| V5 file handling | FAIL/PARTIAL | N/A/PARTIAL | Madar quarantine/scanning/sandbox is a launch blocker; MIME/email attachments assessed separately |
| V6 authentication | PASS WITH EVIDENCE/PARTIAL | PASS WITH EVIDENCE/PARTIAL | runtime MFA/recovery/session/provider tests and deterministic admin recovery |
| V7 session management | PARTIAL | PARTIAL | multi-replica revocation, cookie/header runtime proof |
| V8 authorization | PASS WITH EVIDENCE/PARTIAL | PASS WITH EVIDENCE/PARTIAL | executable full tenant/workspace matrix plus external IDOR review |
| V9 self-contained tokens | PARTIAL | PARTIAL | key lifecycle, audience/issuer/replay and rotation ceremony |
| V10 OAuth/OIDC | PARTIAL | FAIL/PARTIAL | Briefedly PKCE/revocation retry and Google verification; Madar calendar provider drills |
| V11 cryptography | PARTIAL | PARTIAL | key custody/rotation/backup escrow and algorithm/config evidence |
| V12 secure communication | PARTIAL | PARTIAL | dual-stack/TLS/origin/Tailscale/Ollama gateway runtime proof |
| V13 configuration | PARTIAL | PARTIAL | immutable config, least secrets, debug/error/header/CORS runtime matrix |
| V14 data protection | PARTIAL | PARTIAL | lifecycle, log/cache/browser/provider/backup deletion certification |
| V15 secure coding/architecture | PARTIAL | PARTIAL | threat models, dependency controls and hostile worker boundary |
| V16 logging/error handling | PARTIAL | PARTIAL | redaction, tamper resistance, retention and incident usefulness tests |
| V17 WebRTC | NOT APPLICABLE | NOT APPLICABLE | re-evaluate if introduced |

Exact requirement-level rows must be generated from the versioned ASVS file and linked to test/evidence IDs before external assessment. Current classifications are domain-level triage, not certification.

## Manual WSTG/penetration plan

Test a production-shaped isolated environment for information gathering/configuration, identity/auth/session/MFA/recovery, authorization/IDOR, input/SQL/command/template injection, SSRF/redirects, XSS/CSP/clickjacking, CSRF/CORS, file upload/path/symlink/parser, business logic/races/quotas, WebSockets/service worker/cache, error/log leakage, TLS/DNS/origin bypass, container/network boundaries and dependency outage. Use two fully independent tenants/workspaces and every role. Destructive/exploit tests stay isolated.

The tenant matrix in document 05 is mandatory. Evidence includes request/response metadata, unchanged aggregate counts, audit outcome, cache key/state and DB constraints without customer values.

## Briefedly AI/LLM threat matrix

| Threat | Test | Required control |
|---|---|---|
| prompt injection/system-prompt extraction | adversarial email instructions and encoded variants | source is untrusted data; structured prompt boundary; no tools/secrets; output validation |
| evidence-ID fabrication/hallucination | demand nonexistent/cross-workspace IDs, empty/partial import | server verifies every evidence reference belongs to allowed input; uncertainty/incomplete status |
| cross-workspace leakage | simultaneous jobs, cache/model-context reuse and guessed IDs | per-job bounded context, scoped queries/keys, no shared conversational state |
| unsafe rendered output | model HTML/Markdown/script/links | safe rendering/sanitization/CSP; no authoritative business action from model text |
| resource exhaustion | huge prompts/output, concurrency, retry storm | byte/token limits, quotas, fair queue, timeouts/cancel, bounded retries |
| transport/token/log compromise | wrong cert/token, redirects, gateway/proxy logs | HTTPS verification, bearer auth, no query fallback/body logs, rotation, constrained Tailscale grants |
| poisoned model/supply chain | wrong model/checksum/runtime | approved model/checksum inventory, access-controlled pull/update, evaluation before promotion |

Final launch requires independent application penetration testing and Google's designated restricted-scope assessment for Briefedly. Findings enter the master register with owner and retest evidence.
