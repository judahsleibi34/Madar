# Findings status

| Finding / gate | Prior state | Current status | Evidence | Remaining work |
| --- | --- | --- | --- | --- |
| MADAR-BILL-001 | PARTIALLY FIXED / High | **PARTIALLY FIXED** | 12/12 inventoried; fail-closed authority retained; transaction-safe dry-run-first tool and DB uniqueness added | **BLOCKED ON AUTHORIZED COMMERCIAL MAPPING**: 0 approved, 12 decisions required; apply and verify later |
| G15 Billing/entitlements | BLOCKED | **BLOCKED** | No permissive fallback and no invented assignment | Authorized complete mapping, peer review, production apply, post-apply capability/quota continuity verification |
| MADAR-DATA-001 | UNCHANGED / Medium | **FIXED IN VALIDATED DEVELOPMENT CANDIDATE** | Durable schema 83 saga, worker, retries, provider steps, late Auth cleanup, verification, RLS, tests and PG17 rehearsal | Controlled promotion/activation and non-customer operational exercise; policy gaps remain explicit |
| G22 Privacy/data lifecycle | BLOCKED | **PASS WITH CONDITIONS** for the development candidate | User/tenant flows are distinct, durable, idempotent, observable, and verified | Production remains unchanged; approve retained-class policies and exercise deployed worker before customer use |

Global production readiness remains NO-GO because G15, G16, and G18 remain blocked and this candidate is not deployed.
