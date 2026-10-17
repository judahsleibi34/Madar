# Confirmed findings and limits

| Severity | Finding | Evidence | State |
| --- | --- | --- | --- |
| HIGH | Migration SQL bytes could change after checksum admission | Native21-case baseline:19pass/2fail; corrected21pass | Fixed in preview |
| HIGH | Calendar permission downgrade retained private details on another process | Native GoTrue login, real sharing API, editor→availability, baseline disclosure/candidate denial | Fixed in preview |
| HIGH | Schema148 outbox owners can finish/resolve superseded claims | Five native ownership invariants fail | Separate149 successor; absent from148 |
| HIGH | Delivery UPDATE revocation breaks deletion stop_queued_work at147/148 | Real runtime ACL denial plus application direct-update call path | Dedicated149 RPC under validation |
| HIGH | Provider writers remain unfenced during coordinated preservation interval | Live controller source has no complete provider lifecycle | BLOCKED |
| MEDIUM | Forward repair uses legacy preservation contract | Execute-path regression across MANUAL/COMMERCIAL/FENCED | Fixed |
| MEDIUM | PR-head CI identity differed from checked-out merge tree | Actual shell guards on temporary Git trees | Fixed |
| MEDIUM | Artifact path/inode changes after digest verification | Two self-consistent substitution regressions fail old source, pass frozen snapshots | Fixed |
| MEDIUM | Main has no enforced review/check rules | Read-only GitHub API:protected=false,rulesets=[] | Administrator action required |
| LOW | Historical operational metadata remains published | Private bounded history triage; no credential values exported | Forward redaction is not history removal |

No newly confirmed CRITICAL finding. Severity describes tested prerequisites,
not a claim of public exploitability. SQL and artifact substitution require an
operator-writable source path; independent image checks still constrain deployed
image identity. Service-role possession is privileged; no anonymous tenant
bypass was demonstrated. Each test uses synthetic fixtures.

The calendar change trades cached response latency for immediate permission
revalidation. No Redis delivery or invalidation guarantee is assumed.
