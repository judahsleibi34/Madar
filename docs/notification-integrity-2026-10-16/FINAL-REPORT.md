# Notification ownership and native business-integrity follow-up

## Outcome and repository

The confirmed schema 146 notification ownership defect is corrected by new
migration 147 and generation-aware workers. Native business testing found and
fixed a second defect: cancelled exclusive reservations could be reactivated
into occupied slots. New migration 148 serializes that path with creation.
No inventory/payment code defect was confirmed in the executed tests.

- Parent: PR 209, baseline f65aa4722674cd63dbebbc5139a35a67e99ecee9 (unmerged).
- Separate branch: `codex/notification-claim-fencing-20261016`.
- Worktree: `/home/madar/Madar-notification-fencing-20261016`.
- Follow-up draft PR: https://github.com/judahsleibi34/Madar/pull/210, targeting
  PR 209's branch. Merge the dependency first, then retarget this follow-up to main.
  No merge or production promotion was performed.
- Implementation commits: b0934400 (ownership), 94dcbd81 (reservation/native business),
  9c084293 (guarded native cutover). Subsequent report commits change evidence only.
- Exact deployed/tested application source: 9c084293d5583a18cb59a6478684ae2ed980219d.
  Final documentation head is recorded in the PR and final response.

## Database correction and source contracts

`147_fence_notification_delivery_claims.sql`:

- Persistent nonnegative bigint claim_generation, incremented atomically on claim.
- Versioned claim/finish RPCs; server-clock leases and retry availability.
- Finish acquires the row lock, samples clock_timestamp AFTER waiting, then
  atomically checks delivery ID, generation, processing status and live lease
  before sent/retry/dead/revoked mutation. Superseded/expired/completed claims fail
  with notification_delivery_claim_lost and leave the row unchanged.
- Legacy claim/finish execution and direct service-role queue writes revoked;
  old function bodies also reject. Security-definer resolution/cleanup preserved.
- Migration locks core schema/table and refuses ALL processing rows, including
  expired legacy sends. Transaction abort/disconnect restores 146 and its ACLs.
- Protocol 2 workers carry the generation, reject malformed claims before delivery,
  probe only after authority permits consumption, retain healthy READ_ONLY standby
  behavior, and never fall back to an unfenced finish.
- Lost/failed acknowledgements are not counted sent or used to finalize reminders;
  no immediate resend. Ownership-loss/acknowledgement-failure counters added.

`148_guard_reservation_reactivation_capacity.sql`:

- Status RPC takes the same per-block advisory lock as create, then row lock,
  rechecks tenant/identity and overlap before active status and email intent.
- Free/adjacent/nonexclusive behavior retained. Direct runtime UPDATE revoked;
  normal production SDK paths already use security-definer RPCs.
- API reports occupied slots as 409 without private provider detail.
- No automatic historical-overlap repair or inventory/payment function rewrite.

| Migration | SHA256 |
| --- | --- |
|147 |bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3 |
|148 |a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096 |

Both are byte-identical database/Supabase mirrors with new pinned manifests and
candidate validators. 001–146, committed 147 artifacts and active release 146 are
unchanged. 147 is coordinated/policy none: the automatic executor explicitly
rejects its manifest. 148 is a separate unselected repair requiring 147 first.
Source gates admit only these exact additional namespaces/checksums; no protected
controller/runtime authorization or active release selection was broadened.

## Exact executed validation

| Check | Result and scope |
| --- | --- |
| Baseline reproduction | Original 146 accepted stale attempt 1 after attempt 2 reclaim; reproduced before upgrade |
| Native migration/upgrade checks |5 PASS: baseline, live/expired processing refusal, DDL/ACL/schema rollback, disconnect rollback, wrong source refusal |
| Native notification fencing |17 PASS: all four stale outcomes; expired unreclaimed lease; live owner outcomes; retries/dead letter; wrong/null/foreign claims; concurrent claims/finishes; reclaim race; post-lock clock; role denial; process crashes/restarts; provider acceptance ambiguity; repeat migration refusal |
| Native business integrity |22 PASS: 9 reservation/capacity/role tests, 8 stock/order/COD tests, 5 checkout/payment/refund tests |
| Final hermetic backend |3691 collected, 727 conditional skips, 2964 executed PASS, 62.929s; external attempts/sites empty |
| Staging safety |12 PASS; included in broad suite.146 consumer rejection, unmarked refusal, before 147/after 147/after 148 mismatch handling, unverified checkpoint admission refusal |
| Hosted backend |Backend Check 38927327897 PASS on 9c084293, fresh locked image, full suite, pip check and 115/145/146/147/148 SQL stages |
| Source gates |Dependency locks, mirrors, transition ordering, forward-release contract, tracked-secret hygiene and diff checks PASS; historical 013/014 warnings retained |
| Frontend |No frontend/dependency changes; frontend suite not rerun in this follow-up. Real native frontend API proxy smoke passed |

Commands:

```bash
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
# In the locked CI test image, with the workflow fixture mounts:
python scripts/run_tests_no_external_network.py
BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash web/scripts/rehearse_migration_147.sh
BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash web/scripts/rehearse_migration_148.sh
```

The 147 standalone rehearsal ran first. 148 performs the full 146→147 ownership
suite, proves 148 function/ACL/schema rollback, applies 148, runs 22 business tests
and rejects a second 148 application. Final exact-source native times: 0.208s for
upgrade, 11.389s for fencing, 3.308s for business. These are test durations, not
latency/capacity or production measurements. Existing 115/145/146 suites also ran
in hosted CI. Every native connection verifies loopback and the synthetic marker.
All PostgreSQL test resources have CPU/memory/PID limits and owned cleanup.

Process-crash tests run real Python worker batches against native PostgreSQL
through a SQL RPC adapter; they deliberately terminate the process after claim
or synthetic provider acceptance and restart it. The separate native-provider
smoke below proves the actual PostgREST/SDK worker path. No real SMTP, push or
financial gateway was used for failure injection.

## Full native staging and preservation

The existing owned synthetic project on madar-staging was explicitly upgraded
146→147→148 using source-pinned SQL. The helper pauses only owned writers, refuses
processing deliveries, creates a private logical backup and compares all 176
non-core public/Auth/MFA/Storage tables plus 21 sequences. Only the newly added
notification generation field when starting146 and core schema state are excluded.
**Preservation PASS.** Checkpoints bind backup/migration hashes; failed preservation
blocks admission. Old writers restart on failure only if schema remains146;
after 147 they remain stopped for forward repair. Verified148 re-entry was a no-op.

Exact9c084293 source was built/deployed. Actual real-provider acceptance:

- Native Auth password/invalid JWT/TOTP/admin AAL1 denial/AAL2/CSRF/MFA replay/refresh
  checks PASS, plus private Storage and mediated legacy avatar bytes.
- Durable intent/replay and actual protocol 2 worker delivery PASS through PostgREST.
- Protocol RPC returned 2; legacy claim 403, legacy finish 403, direct delivery PATCH 403.
- Protocol 2 SQL recovery rejected all four stale outcomes, retained retry/dead-letter
  behavior; fixtures rolled back and worker resumed.
- Runtime schema bounds 148..148, readiness true, worker consuming, nine owned
  services running, one new generation-fenced delivery sent.
- API image sha256:3de4a885250c279e015d9e3539393e285fa847d890cb0700a295519556acca49.
- Actual component restore PASS at 148:177 tables, 21 sequences, six object byte
  inventories and four MFA factors; 18.344s database/object phase. Independent
  database/object copies retained. This is same-cluster roles/component recovery,
  not full restored-app/off-host/PITR or production RPO/RTO proof.

Original staging-data services and production were untouched. Staging retained
roughly 3949MiB available RAM and no swap use at observation. Existing private
credentials/Auth state were preserved without being rotated or copied into reports.
The historical ownership marker contains146; observed schema is independently 148.

## Required future rollout

1. Review/land PR 209 first, then retarget/review PR 210. These are unselected source
   candidates, not an ordinary rolling production release or approval request.
2. Prepare accepted immutable images and separately reviewed target 148 admission
   under the existing protected controller, current-data rehearsal, backup and
   operational authorization. Existing active release 146 is not silently widened.
3. Establish exclusive worker ownership; stop old consumers, prevent resurrection
   and drain legacy claim/finish transactions and in-flight provider requests.
   Reconcile every processing delivery, including expired/unknown accepted sends.
   Never blindly reset an ambiguous send to pending to satisfy the migration.
4. Execute the approved coordinated SQL. Before147 commits, refusal/disconnect
   preserves 146. After147 commits, old workers are forbidden; failure in148 is
   forward-repair-required with writers held, not an old-worker rollback.
5. Verify target 148, original data/Auth/MFA/Storage, grants and real protocol 2
   delivery before activating only the accepted new worker generation. Observe
   ownership-loss/acknowledgement errors, queue health and actual processing.
6. Retain committed schema on application rollback; use only a compatible fenced
   worker image. Do not down-migrate147, re-enable legacy writes, forge authority
   or restore stale customer data to undo application changes.

No production migration, data write, service restart, billing activation, controller
installation, write grant, release promotion, DNS/firewall or tunnel change was
performed. No protected production receipt/controller file was edited.

## Unresolved risks and limits

- Fencing protects canonical database state, **not exactly-once external delivery**.
  Accepted SMTP/push plus lost acknowledgement can duplicate on retry. Native
  crash tests explicitly show two effects without provider idempotency and one
  with a stable-key synthetic provider. Existing SMTP/push do not promise that
  contract; reconciliation/duplicate-aware operations remain necessary.
- This is a coordinated cutover. A nonquiescent old-worker rolling deployment is
  unsupported, and post-147 rollback to protocol 1 is unsafe. Future production
  target 148 admission and full maintenance/interruption rehearsal remain gates.
- Historical reservation overlaps were not inspected/repaired in production.
  Capacity tests prove the existing exclusive-one-slot model, not arbitrary seats.
- Canonical SQL checkout/payment effects were tested; real gateway signature,
  settlement, live billing and every commerce workflow are not certified.
- Only per-recipient delivery acknowledgement is newly fenced. Resolver-outbox
  ownership, other queues, complete tenant/financial audit and wider architecture
  roadmap remain separate workstreams.
- Full product browser E2E, restored-app/offsite/PITR acceptance and production
  performance objectives remain incomplete. Source-overlay staging dependency
  bases remain distinct from hosted fresh locked builds and production provenance.

Both confirmed defects are corrected and tested in development/staging. The branch
is ready for review. Production rollout remains unexecuted and approval-gated.
