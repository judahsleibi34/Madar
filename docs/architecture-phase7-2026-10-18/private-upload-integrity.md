# Private upload acknowledgement integrity

## Confirmed failure and scope

The privileged-client review found a separate HIGH data-integrity defect in
`academy_owner_service.upload_document` and `elearning_forms_service.submit`.
Both handlers deleted staged private bytes and released quota on any metadata
RPC exception. An exception after commit therefore removed bytes referenced by
committed document or response metadata.

The diagnostic uses actual PostgreSQL17/schema150, real service-role metadata
RPCs, current membership/resource fixtures and two independent database
connections. It closes the autocommitted mutation connection before injecting a
lost-response exception. The observer then checks the committed storage key and
the existence of its bytes in a real, owned temporary filesystem. This tests the
service's cleanup decision; it is **not** a live Supabase Storage acceptance test
or an end-to-end authorization claim. Entitlement/provider configuration gates
are isolated for the diagnostic. No customer data or external provider is used.

Before repair: **2 FAIL,0 errors,0 skips,1.806 seconds**. The observer saw one
committed academy document and one committed learning-form file at schema150;
both referenced byte files were absent. A prior loader-only setup attempt failed
before running the diagnostic because the non-root test image could not read
public source directories; its evidence was retained separately and permissions
were corrected. It is not counted as a product failure.

## Repair

The two services separate storage staging from metadata execution. Before
metadata is attempted, storage failures retain their existing cleanup path.
After it is attempted, an exception or malformed acknowledgement does not prove
transaction rollback: bytes and their quota are retained, with no automatic RPC
replay and no destructive decision based on a possibly racing absence read.

Both handlers return HTTP503 with `detail.code=private_upload_outcome_unknown`.
The response identifies the generated document or response; Forms also returns
the caller's submission idempotency key. The text says the outcome is uncertain
and asks the caller to check existing records. It does not report success or a
definite transaction failure. No storage key or provider exception is exposed.
Logs contain a bounded event name and exception class, without file content,
tenant labels, submitted answers or credentials.

Successful academy acknowledgements must identify this invocation's document
and provide the public metadata projection. File-bearing Forms acknowledgements
must contain a UUID and an actual boolean duplicate flag; new responses must
identify this invocation's response. A confirmed duplicate of a different
response may clean only the newly generated response-owned file keys. A
duplicate acknowledging this same response retains its potentially referenced
bytes. Fileless Forms errors retain their existing behavior.

The repair does not change migrations001–150, database grants, entitlement
rules, controller authority or production configuration.

## Executed verification

```text
python -m unittest tests.test_learning_private_upload_ack_database \
  tests.test_academy_owner_tools tests.test_elearning_forms \
  tests.test_elearning_recording_validation -v
```

After repair: **70 PASS,0 failures,0 skips,2.331 seconds**. This run includes the
same two native metadata/byte-survival assertions, unchanged. Their exception
expectation now checks the explicit unknown-outcome HTTP503 instead of exposing
the injected transport exception. Independent metadata remained schema150 with
one document and one Forms file, and both referenced byte files survived.

Two additional acknowledged-success unit cases were then added without changing
service code, followed by a final run:

```text
python -m unittest tests.test_academy_owner_tools tests.test_elearning_forms \
  tests.test_elearning_recording_validation -v
```

**70 PASS,0 failures,0 skips,2.108 seconds**. The native two and the final unit70
cover72 distinct cases; the earlier combined70 overlaps the final unit run and
must not be added to it as independent coverage. Focused tests also cover
uncertain/malformed acknowledgements, quota retention, no automatic replay,
duplicate cleanup boundaries, pre-metadata storage failure, and normal success.

The native fixture was positively marked
`madar-phase7-private-upload-ack-synthetic`; the opt-in environment variable is
`LEARNING_PRIVATE_UPLOAD_SYNTHETIC_DATABASE_DSN`. The diagnostic also accepts
the existing CI fixture's exact `madar-notification-synthetic-rehearsal` marker;
these are the only allowed markers, with the unchanged disposable-database
helper enforcing loopback identity before fixture writes. PostgreSQL was restricted to
network-none,512MiB,.5CPU,PIDs128 and a1GiB owned tmpfs; the bounded read-only test
container shared only that isolated network namespace. Memory and image
availability were checked before creation. Both owned containers were removed
after each native run; retained staging services, databases and object stores
were not modified. The final unit-only container used network-none. Evidence
logs remain private and outside Git. A cached dependency image was used; this
is source regression evidence, not fresh final-image or production acceptance.

The existing `web/scripts/rehearse_migration_147.sh` schema150 section now invokes
these two diagnostics **after** its existing legacy/deletion and business/calendar
cases. Its new invocation uses the same marked fixture at loopback55448, provider
placeholder credentials, read-only source and a128MiB writable temporary
filesystem; no external provider is called. Existing assertions and SQL are
unchanged. `bash -n web/scripts/rehearse_migration_147.sh` passes. CI wiring is
distinct from a fresh hosted run; this review has not rerun the entire harness.
A new standalone schema150 fixture with the CI marker was also exercised:
**2 PASS,0 failures,0 skips,1.638 seconds**. The independent observer again saw
one document and one Forms file, and both byte-survival assertions passed.
That fixture used isolated namespace loopback5432 rather than the CI harness's
host loopback55448; no host port was published. Its owned containers were
removed afterward. This validates the strict marker path and test behavior,
not execution of all earlier harness sections.

The unchanged privileged inventory checker passes78 paths; its focused suite
passes8 tests. `git diff --check` and compilation of the changed services and
native diagnostic pass.

## Remaining limits and recovery

The conservative error contract may retain unreferenced bytes and quota even
after a definite database rejection returned through the attempted RPC path.
There is no new automated orphan collector or durable reconciliation ledger in
this repair. Keeping uncertain bytes prevents confirmed data loss; it does not
prove the upload completed or provide exactly-once storage behavior.

Reconciliation must use the returned operation identity and tenant/resource
scope, compare authoritative metadata/storage identity and hash, and establish
that no mutation can still commit before deleting an unreferenced object or
releasing quota. A single empty read is insufficient. Forms retries must retain
the original submission key and content; acknowledged duplicate responses use
the existing idempotency contract. Document uploads do not yet provide a
client-selected idempotency key, so callers must inspect the application's
documents before creating another upload. Existing missing-byte references need
separate owner-approved recovery from retained backups if available; this source
repair cannot recreate previously deleted content.

No production mutation, repair or release approval was performed. Fresh exact
source CI, independent review and normal governed release gates remain required.
