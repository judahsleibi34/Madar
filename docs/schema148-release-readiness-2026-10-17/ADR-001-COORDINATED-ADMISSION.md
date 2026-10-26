# ADR001 — extend the existing protected coordinator

Status: implemented in source, independent review required; production unselected.

Context: PR210's147 fencing deliberately revokes legacy delivery mutation and
refuses processing rows. Generic automatic migration cannot safely coordinate
workers, ambiguous provider effects, boot recovery or post-commit148 repair.
The deployed146 application/controller differs from both PR heads.

Decision: add exact version5 completed-NORMAL146→148 maintenance profile. Retain
existing protected authorization/installation/locks/backup/replica/READ_ONLY/
promotion/boot ownership primitives. Admit exact immutable147 then148 only with
fresh authorization and live consumer/database guard. Historical profiles and
ordinary migration refusal stay fixed. Preserve all Auth/Storage table roots
for this new profile. Separately bind fresh CI archive source, configuration and
single-OCI-manifest runtime identities; requery artifact and application CI.

Alternatives: generic auto SQL would bypass coordinated semantics; an independent
root deployment script would duplicate authority; broad backward compatibility
would restore unsafe legacy writes; rewriting workers/queue/provider is unnecessary.
Blindly resetting processing rows cannot prove external provider outcome.

Benefits: narrow auditable source change, durable fencing retained, genuine
commit-boundary tests, no new queue/database/dependency or privileged entrypoint.
Costs: conservative quiescence may delay maintenance; exact identity/ownership and
current-data acceptance require operator work. Target native containerd identity
is explicit; other image-store behavior fails closed until independently validated.
Risks: complete privileged reboot/controller/current-data integration is not
established by synthetic SQL/transport fixtures. At-least-once providers can
accept before acknowledgement fails. Unknown consumers/outcomes block release.

Migration impact: no historical SQL modified and no149 added.147 irreversible
compatibility boundary for legacy workers;148-only completed NORMAL/rollback.
Before commit source changes can be withdrawn; after147 use approved compatible
forward repair. Do not restore old grants or overwrite customer data as rollback.
