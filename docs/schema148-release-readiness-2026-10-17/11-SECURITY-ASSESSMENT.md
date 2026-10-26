# Security assessment

| Priority | Finding / state | Evidence / remaining action |
|---|---|---|
| P0 previously fixed in210 | Expired worker could acknowledge newer owner's delivery | Baseline146 repro;147 native tests reject sent/retry/dead/revoked, direct legacy writes denied |
| P0 previously fixed in210 | Cancelled exclusive reservation reactivated into occupied slot |148 native concurrency/capacity tests retained |
| P1 addressed in source | Ordinary migration admission intentionally cannot run coordinated147 | Exact protected profile5, fresh authorization, digest policy, guarded executor; ordinary loader still refuses |
| P1 addressed in source | Source-overlay labels were insufficient fresh artifact acceptance | Authenticated GitHub run/artifact digest + exact image/lock inputs; no local PASS self-authentication |
| P1 addressed in source | Docker-only inventory misses manual workers or unrelated consumers | Host PID positive control/cgroups; strict reviewed native credential-scope exclusion; unknowns block |
| P1 addressed in source | Historical preservation counted only selected Auth/Storage tables | New profile snapshots all Auth/Storage tables; native mutation detection |
| P1 unresolved | Service-role BYPASSRLS increases application authorization reliance | Native bidirectional project IDOR/user spoof/admin rejection passes; blanket RLS rewrite not attempted |
| P1 unresolved | Main unprotected; token lacks repository admin | Exact required job contexts in final CI evidence; independent admin must configure rules |
| P1 unresolved | Required protected controller/current-data acceptance absent | Source only, no install/production mutation; independent approval required |

No new cross-tenant/financial defect was confirmed in the executed native cases.
This does not certify every endpoint or tenant domain. No secret rotation, real
payment, production signing token or production customer repair was performed.
Unknown provider delivery outcomes remain a duplicate-delivery risk, not a
justification to bypass fencing. Fresh CI artifact integrity is source/workflow
binding, not an independent review or production deployment credential.

## Newly confirmed operational correctness defect

Actual fresh c3 native worker inspection showed sent40/processed2. Queue polling
used STATE.update(get_queue_metrics()), overwriting acknowledged-delivery process
counters with historical outbox sent/failed/dead gauges. A new regression test
reproduced sent40 after provider acceptance plus ownership loss, with no successful
acknowledgement. The correction copies only named queue gauges and separately
namespaced delivery gauges; successful-send/failure counters retain process event
semantics. No SQL, provider action, lease or ownership rule changes. Native poll
coverage exercises a real expired/reclaimed DB claim through the complete loop.
This is an observability/integrity reporting correction, not evidence of a second
business write or false durable delivery status.

Final real native HTTP extension proves bidirectional foreign read/delete denial
with exact foreign-row equality, legitimate own archive, path-user spoofing denial
and immediate disabled-membership read/write denial while the GoTrue JWT remains
valid. Real application CSRF cookie/header is obtained; the initial missing-token
403 was a test-fixture error and assertions were retained. No entitlement policy
was disabled or synthetic paid subscription activated. Broader domain coverage
remains PARTIAL.
