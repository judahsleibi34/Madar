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

## Operator evidence checksum/read race — conditional admission defect

The previous evidence loader hashed an operator-owned pathname,then reopened it
to parse JSON. A deterministic replacement between those operations returned
unreviewed replacement data. The preserved assertion failed against the old
implementation. The correction hashes and deserializes one bounded no-follow
regular-file byte capture. The original race,same-inode rewrite after capture,
symlink,FIFO,empty and oversized cases now refuse substitution. No protected
authorization was created or production controller changed.



PhaseIX full-provider CI requires the accepted native OCI manifest identities;
it never substitutes build-host configuration IDs after import. A reproduced
classic-store refusal led to explicit empty-daemon containerd-store preparation
only on disposable GitHub runners,with a root-private original configuration
preimage and failure restoration. Physical nodes and the shared staging VM
refuse that preparation. Remaining mutable checkout/setup-node Actions are
pinned to their officially observed commit IDs. Selected native browser checks
use locked dependencies,a synthetic private fixture and verified loopback/source
identity. Bounded progress and sanitized failure reports contain no credentials,
exception messages or raw provider logs;completed evidence follows observed
owned-service shutdown. These CI privileges are not release authority.

## Unclassified replication-mode SQL writer — confirmed conditional admission defect

A real database-mode replication connection in the marked PostgreSQL17 fixture
reported `walsender`,executed and observed an owned UPDATE,and rolled it back.
The unchanged assertion requiring admission refusal failed against the prior
client-only guard. No customer data or production session was involved.



PhaseIX native testing reproduced a replication-mode PostgreSQL connection that
could UPDATE an owned fixture while reporting backend_type=walsender;the prior
client-only admission check accepted it. Schema150 now measures unknown database
workers,including replication senders,at migration and private recovery boundaries
instead of asserting unknown_writers=0. Only pinned core housekeeping and the
observer's PID-bound parallel workers are excluded;NULL/unclassified types deny.
Streaming senders require a separate positive replica/consumer contract;none is
exempted to manufacture readiness. Dormant host/extension/supervisor inventory
and full protected controller acceptance remain independent unmet gates.

The same native suite now passes5cases:actual replication-writer refusal,
foreign-database client refusal,foreign prepared-transaction refusal,published150
protocol horizon,and NULL/parallel-leader classification. A transport-isolated
component test also proves private recovery measures the writer count rather
than inventing zero. These are native/component results,not a complete writer
inventory or an installed production controller acceptance.
