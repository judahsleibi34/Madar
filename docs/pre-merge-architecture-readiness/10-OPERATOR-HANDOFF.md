# Handoff: engineering incomplete

This is an evidence handoff, not a merge or production-release request.
Saliba and Judah should first examine the exact missing calls in
[protected acceptance](04-PROTECTED-RELEASE-ACCEPTANCE.md), then the
[Class D dossier](03-CLASS-D-REVIEW.md), [security scope](06-SECURITY-REVIEW.md)
and [merge safety](09-MERGE-SAFETY.md).

Critical code paths: `CompletedNormalUpgrade._execute`, inventory/candidate
admission binding, concrete provider journal and borrowed locks, authenticated
backup/receiver, parent-owned SQL dispatch, private acceptance delegates,
`CompletedNormalWriteHandoff.guard/grant`, worker/proxy activation and boot repair.
The two reliability fixes do not substitute for those unfinished connections.

No candidate installed controller, current-schema approval, receiver acceptance,
independent test handoff or complete release receipt is supplied. Never execute
historical recovery tools or public write probes to compensate for these gaps.

Continue only in the canonical workspace. Preserve the independent checkout,
all historical SQL and private evidence. A full rehearsal must start from a
running146 application with original synthetic Auth/MFA/Storage/business data,
use the existing controller and separate real test-only issuer/receiver, and
end with protected activation and critical fault/reboot acceptance.

Independent gates remain Saliba/Judah review, administrator repository/webhook
controls, current-production recovery/replica acceptance, maintenance approval,
controller/migration authorization and separate automation activation.
