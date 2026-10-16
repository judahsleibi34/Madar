# Initial risk register and backlog

| Priority | Finding | Initial status / action |
| --- | --- | --- |
| P1 | Production-like startup accepts disabling CSRF origin check or allowing missing origins; trusted origin list hides unsafe FRONTEND_URLS validation | Reproduce and reject unsafe configurations, test adversarial origins |
| P1 | Catalog cache miss can race invalidation and republish stale catalog/settings | Reproduce interleaving, prevent stale publication |
| P1 | Backend CI silently omits21 function-style tests, including cache/notification/draft regressions | Convert to existing unittest conventions and add future discovery guard |
| P1 | Staging synthetic facade uses historical schema81/83 and cannot establish full native provider parity | Build isolated current-schema integration checks with synthetic fixtures; report limits |
| P1 | Service-role access bypasses RLS; full route/worker tenancy audit incomplete | Preserve existing tenant guards, expand selected adversarial tests; no blanket RLS changes |
| P1 | Commercial override grants broad capabilities when disabled | Intentional operator policy in source; preserve holds, report unresolved operational gate |
| P1 | Backup creation alone does not prove application restore | Run isolated synthetic backup/restore and report exact scope |
| P2 | Process-local invalidation and calendar tenant-generation dictionary can grow without bound | Bound fencing state; record multi-process consistency limitation |
| P2 | Public registry unavailable in staging | Offline immutable image transfer; distinguish dependency verification from fresh build |

No claim of complete security audit or production readiness. Authentication/MFA already have dedicated server enforcement and assurance-binding tests; run them before making a current-status assertion.
