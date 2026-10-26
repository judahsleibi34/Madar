# Independent engineering review

Three separate automated review contexts inspected artifact/readiness trust,
consumer/control-plane recovery and outbox/SQL ownership. This is additional
engineering evidence; independent human authorization remains mandatory.

Actual source reviewed includes schema148_release/consumers/artifacts/readiness,
completed_normal_forward/execution/migration/evidence/database/backup,
migration_executor, claim/finish/materialization SQL, worker/service propagation,
request_security, cache and commercial feature enforcement.

Confirmed corrections on the preview:

- Forward completion omitted its selected operation contract and applied legacy
  preservation defaults. Actual execute-path tests cover all retained profiles.
- Application CI tested a merge ref while artifacts/provenance bound PR head.
  Exact checkout and clean-head checks now agree.
- ZIP hash/path reuse allowed a changed archive to be parsed/imported after
  authentication. Bounded unnamed snapshots now bind every consumption step.
- SQL execution reopened a checked pathname after backup/guard callbacks. Native
  tests reproduced execution of changed bytes; immutable captured SQL fixes it.
- Per-process calendar cache retained permission-filtered private details after
  another process downgraded calendar membership. Native Auth/API regression
  confirms authoritative recomputation masks those details immediately.

Residual findings are explicit release blockers: unfenced outbox resolver and
deletion queue ACL compatibility at148; a separate149 successor is under test.
Provider writer lifecycle is not implemented in the privileged coordinator.
Readiness now records this as a separate missing prerequisite.

No confirmed new CSRF bypass was established. Explicit invalid Origin does not
fall back to Referer. Commercial enforcement=false still intentionally grants
capabilities except ledger holds; no production flag value or billing activation
was changed. Catalog cross-process TTL invalidation remains incomplete.

No production exploitation, controller installation, grant issuance, migration
or service restart was performed. Full boot/systemd acceptance remains untested.
