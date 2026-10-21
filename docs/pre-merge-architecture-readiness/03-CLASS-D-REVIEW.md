# Class D dossier — prepared, not approved

Exact implementation source: `83dce3da2204980d5d89fc071cf1fc9fbe0b5cd0`. History base: `876b65e73ea8ceaf398145d8677019184798a95c`. All four SQL mirrors match. Classification uses hash-pinned pglast7.21/PostgreSQL17; no risk rule was changed.

| Transition | SQL SHA256 | Risk |
|---|---|---|
|146→147|`bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3`|D|
|147→148|`a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096`|D|
|148→149|`8ed767df57f5c02be50d83621fe45d314b3d1fdb42d2b7a470170519bdf1f869`|D|
|149→150|`63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722`|D|

## Operation and compatibility

147 changes delivery claims, claim generations and service-role mutation/EXECUTE privileges.
148 changes reservation status/capacity/reactivation RPC behavior and notification outbox effects.
149 changes outbox claims/resolution, delivery linkage, claim fencing and service-role RPC privileges.
150 changes deletion request/step ownership and effects/resources/subjects, local deletion RPCs, service-role grants and RLS. It also touches deletion-related tenant/user/assets/calendar cleanup.

The SQL source is authoritative for every function, relation, role and grant:
- [147 SQL](../../web/database/migrations/147_fence_notification_delivery_claims.sql) and [mirror](../../web/supabase/migrations/147_fence_notification_delivery_claims.sql).
- [148 SQL](../../web/database/migrations/148_guard_reservation_reactivation_capacity.sql) and [mirror](../../web/supabase/migrations/148_guard_reservation_reactivation_capacity.sql).
- [149 SQL](../../web/database/migrations/149_fence_notification_outbox_claims.sql) and [mirror](../../web/supabase/migrations/149_fence_notification_outbox_claims.sql).
- [150 SQL](../../web/database/migrations/150_fence_data_deletion_ownership.sql) and [mirror](../../web/supabase/migrations/150_fence_data_deletion_ownership.sql).

All four are transactional. The conservative classifier refuses the ordinary canonical additive envelope and identifies procedural SQL, runtime/authorization contracts and data/privilege mutations. Per-migration reasons:

- 147: alter_table_requires_live_lock_and_data_review; canonical_locked_schema_envelope_required; critical_runtime_or_authorization_contract; data_mutation_requires_volume_and_invariant_review; dynamic_or_procedural_sql_requires_review; privileged_or_runtime_contract_change; unrecognized_statement_LockStmt; unrecognized_statement_NotifyStmt; unrecognized_statement_TransactionStmt.
- 148: canonical_locked_schema_envelope_required; critical_runtime_or_authorization_contract; data_mutation_requires_volume_and_invariant_review; dynamic_or_procedural_sql_requires_review; privileged_or_runtime_contract_change; unrecognized_statement_NotifyStmt; unrecognized_statement_TransactionStmt.
- 149: alter_table_requires_live_lock_and_data_review; canonical_locked_schema_envelope_required; critical_runtime_or_authorization_contract; data_mutation_requires_volume_and_invariant_review; dynamic_or_procedural_sql_requires_review; privileged_or_runtime_contract_change; unrecognized_statement_LockStmt; unrecognized_statement_NotifyStmt; unrecognized_statement_RenameStmt; unrecognized_statement_TransactionStmt.
- 150: alter_table_requires_live_lock_and_data_review; canonical_locked_schema_envelope_required; create_table_outside_audited_additive_subset; critical_runtime_or_authorization_contract; data_mutation_requires_volume_and_invariant_review; dynamic_or_procedural_sql_requires_review; privileged_or_runtime_contract_change; row_security_contract_change; unrecognized_statement_LockStmt; unrecognized_statement_NotifyStmt; unrecognized_statement_TransactionStmt.

## Locks, preservation and failure requirements

These are coordinated, potentially blocking table/RPC/grant changes, not zero-downtime additive promises. Review explicit LOCK/ALTER/UPDATE/DO/function bodies and volume/lock budgets in the immutable SQL. Native tests exercise bounded lock contention, but no production lock-duration or capacity guarantee is established.

Preserve original roles/memberships/owners/ACLs, Auth/passwords/MFA, Storage metadata/bytes, tenant/business rows, sequences and queue ownership. Fence ingress, providers, all workers/supervisors and established sessions before capture/SQL. Require exact database/source/controller/images, a current authenticated original-state backup, independent receiver and independent restore prerequisites.

146 is the required origin.147/148/149 remain READ_ONLY/non-NORMAL. Final150 requires delivery/outbox/deletion protocols2/2/2. Published150 returns deletion protocol0 at151; no future application compatibility is invented.

Each committed boundary must be observed independently. Lost COMMIT acknowledgement is uncertain until fresh authoritative observation; do not replay consumed attempts, start old workers, restore broad grants, or roll an old backup over newer data. Resume only through fresh protected forward-repair admission.

## Acceptance and independent review

Native SQL rehearsal:208component executions passed, including actual SQL/process interruption and selected-row preservation. Its authority and backup/provider-supervisor endpoints are fixtures. Complete preserved running-application controller acceptance: **BLOCKED**. Independent real test-only issuer/handoff and receiver: **not demonstrated**. Current-source privileged reboot/full application restore: **not demonstrated**.

The existing CI `full_staging_exceptional_sql_requires_separate_review` refusal is correct. Ordinary application staging cannot substitute for exceptional preserved-data controller acceptance. A legitimate exceptional path must authenticate the exact plan, artifacts, disposable environment, independently controlled test authority, real controller receipts, preserved data and final protocols. This path is not yet implemented; no approval packet or green exceptional check is fabricated.

Independent semantic/release review and later production authorization remain pending. This dossier and a passing CI fixture cannot issue either authority.
