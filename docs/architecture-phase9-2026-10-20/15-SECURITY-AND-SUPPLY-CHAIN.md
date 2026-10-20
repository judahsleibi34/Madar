# Security findings and trust boundaries

## Confirmed conditional cluster-scope admission gaps — MEDIUM

Component:`schema150_release.QUIESCENCE_SQL`,consumed by the concrete provider
adapter and native admission observer. The old query counted clients and prepared
transactions only in the application database. PostgreSQL roles/privileges are
cluster-wide; an unclassified administrative client or prepared transaction in
another database must not escape maintenance admission.

Native minimal marked PostgreSQL17 reproduction opened an idle connection in a
separately marked restore database in the same verified cluster. The unchanged
assertion requiring admission refusal failed:RuntimeError was not raised. A
second case prepared one owned update in that other database,then disconnected.
The old query reported prepared_transactions=0 rather than1. Both baseline tests
failed;the prepared update was explicitly rolled back by its owner in cleanup.
No production role/transaction/client was modified or terminated.

Correction:the150-only observer accounts for all other client backends and all
prepared transactions in the verified cluster. Field names,protocol checks,
queue/backlog assertions,statistics refresh and fresh-MVCC requirements remain.
The original client-exit fixture now closes its independent cross-database
monitor before demanding global quiescence. It still requires the actual guard
to refresh its statistics snapshot in the same transaction;no fixture-side refresh
or forced backend termination was added. Unknown activity blocks admission.

The operation is unregistered in source and was not installed or exploited in
production. This is a confirmed admission correctness defect with conditional
operational impact,not proof of an active production bypass. Full dormant writer,
background-provider and supervisor coverage remains an independent engineering
gate. Source/native tests do not establish that whole inventory is complete.

## Published deletion protocol horizon — compatibility blocker

The exact checksum-authenticated function from published migration150 returns2
only when core schema=150,and0 for a later version. A native synthetic marker
advance to151 returned0;the change was rolled back. SQL001–150 is unchanged.
The strict worker refusal is retained. A routine future151 full-application
release cannot be claimed against this origin merely because additive SQL and
minimal migration tests pass. A separately reviewed forward protocol-compatibility
contract is required;changing a privileged protocol function is not ClassA.
No fake protocol value,new real migration or active release target was introduced
just to make the future-version demonstration appear successful.

## Backup custody and source trust

Privileged role material is added only under protected admission staging after a
descriptor-relative copy of ordinary dump output. Its inner digest is persisted
separately and required by restore/replica consumers. Native object metadata is
retained but not automatically activated. Configuration hashes identify required
independent escrow,not recovered secret values. No new issuer,unrestricted repair
endpoint or arbitrary privileged SQL path exists.

The root policy pins the complete deployment/scripts/staging integration trees.
A newly imported helper cannot enroll itself by advancing the source base while
leaving an older workflow entrypoint unchanged. Policy matches still cannot
issue production authority. Independent review and current environment evidence
remain mandatory;main remains unprotected at baseline.

After correction,the same three native cases passed:idle foreign-database client
refusal,foreign prepared-transaction refusal,and the unchanged exact150 deletion
protocol horizon. The first post-fix fixture attempt raced PostgreSQL readiness;
the fixture now waits for final TCP readiness rather than the image's transient
initialization socket. Private startup logs are retained before owned cleanup.
