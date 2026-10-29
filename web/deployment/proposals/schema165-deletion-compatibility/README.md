# Review proposal: schema165 deletion compatibility

This directory is an unselected review proposal, outside both canonical migration
trees and every operational manifest. The owner authorized preparation only on
2026-10-29. Execution, publication as canonical migration165, changes to existing
SQL/checksums, and expanding Milestone C's target beyond164 are not authorized.

The current canonical160 function returns ownership protocol2 only at160. No
published161–164 migration changes it. A healthy schema164 deletion consumer
therefore cannot pass the existing protocol contract. Reporting protocol2 from
application metadata, ignoring the database's0, or editing160 would be incorrect.

The proposed successor changes the database contract only at its own165 target.
It intentionally does not reinterpret161–164 as accepted writable states and
does not admit arbitrary future versions. Existing function ownership and ACLs
must survive CREATE OR REPLACE; protocol2 consumers keep their ownership fences.

Before this proposal can become an executable canonical migration, independent
review must accept all of the following on real preserved data: exact original
function definition/owner/ACL and native protocol observations; current roles and
RLS; complete deletion coverage for Sheets/webhook/dashboard/report metadata and
private artifacts; cancellation/finalization and ambiguous external effects;
tenant isolation; notification/outbox protocols; resource/lock budgets; fresh
backup plus independent restoration; compatible candidate and every worker;
approved staged release selection, administrator approval, and actual recovery.
The SQL below is not evidence that any of those gates passed.

Milestone C's accepted target remains164. Its C2 application acceptance remains
blocked until an independently approved scope and compatibility repair resolve
this conflict. Nothing here opens schema160 or production admission.
