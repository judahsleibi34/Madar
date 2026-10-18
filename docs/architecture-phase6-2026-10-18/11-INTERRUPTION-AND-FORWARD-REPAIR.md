# Interruption boundaries

| Boundary | Proven/required behavior | Evidence scope |
| --- | --- | --- |
| Before150commit | SQL error/disconnect rolls back DDL,ACL and schema together to149 | native PASS |
| After150commit/lost reply | Actual150 persists;repeat migration refuses;no invented rollback | native PASS |
| Expired original request/step | Successor generation and step attempt remain unchanged | native PASS |
| Local step crash | Original intent-free idempotent operation resumes under successor,bounded by request attempts | native PASS |
| External intent/response loss | Durable uncertainty blocks automatic resend/finalization;manual review | native PASS with synthetic provider |
| Repeated begin/completion | Begin acknowledges same active step;completion cannot overwrite committed output | native PASS |
| Before/after147/148/149 | Retained commit/rollback/fencing tests remain mandatory | retained native PASS on drafts;exactCI pending |
| Provider fence/private resume/activation crash | Intent survives;fresh observation and authority required;no blind replay | model PASS |
| Real systemd/host reboot/proxy/grant interruption | Must preserve maintenance and never resurrect old workers | BLOCKED/not executed |

After a committed fencing migration,legacy worker/grant restoration is prohibited.
No database down migration or automatic customer restore exists. Forward repair
needs new independent authority and verified actual schema/artifacts/preserved
preimages. Consumed protected credentials and historical receipts are not replayed
or overwritten. A candidate source policy does not authorize production effects.
