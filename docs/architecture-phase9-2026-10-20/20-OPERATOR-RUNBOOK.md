# Operator capabilities and stop rules

## INSPECT — no authority

Use the generic source validator and existing
`web/scripts/inspect_schema150_maintenance.py` for read-only source/journal
assessment. Journal status is historical evidence;it does not establish current
services,database compatibility or permission to resume. Never edit a status file
into an approval. Read exact-source GitHub checks and sanitized full-provider
artifacts separately from production evidence.

Production inspection must first bind the expected owned target;when an additional
PhaseIX label check failed,it stopped before SQL. Do not infer ownership from a
container name,guess labels or retry a broader query. Keep raw journals,role
verifiers,Auth/MFA/session data and private operational identifiers outside Git.
Use selected metadata fields rather than broad container/environment inspection.

## PREPARE — source and staging only

The workflow automatically checks out the exact source with full ancestry and
no persistent credential,uses the locked PG17 parser,waits for latest exact-head
independent CI,and downloads the authenticated candidate archive. Its read token
is unavailable to application/provider processes. Generated plans grant nothing.

Manual authorized staging uses a clean exact-source development checkout:

```bash
python3 web/scripts/fetch_full_provider_artifacts.py \
  --source-sha "$candidate_sha" \
  --directory "$HOME/madar-provider-artifacts-${candidate_sha:0:12}"
python3 web/staging/integration/full_provider_staging.py INSPECT \
  --source-sha "$candidate_sha" --history-base-sha "$reviewed_base_sha" \
  --artifacts "$HOME/madar-provider-artifacts-${candidate_sha:0:12}"
```

Use the read-only GitHub credential only for download,then remove it from the
child environment. Install only hash/lock-verified parser/browser tools in an
isolated development environment. Physical nodes refuse provider rehearsal.

## REHEARSE — positively owned synthetic target

Only the identified staging VM or dedicated GitHub-hosted runner may run:

```bash
python3 web/staging/integration/full_provider_staging.py REHEARSE \
  --source-sha "$candidate_sha" --history-base-sha "$reviewed_base_sha" \
  --artifacts "$HOME/madar-provider-artifacts-${candidate_sha:0:12}"
```

Require8GiB disk,2.2GiB available memory and free loopback22080/22443/22081.
A private lease serializes attempts. Existing namespaces/resources or consumed
artifact captures refuse rather than being adopted or deleted. Only this owned
project is stopped;named volumes and private failed work remain. No automatic
retry clears ambiguous queue/deletion state. Review sanitized failure phase and
private evidence before making a new independent attempt.

The ordinary native backup component command creates only its labeled network-
none temporary cluster and owned capture;it is not a production backup command:

```bash
python3 web/staging/integration/phase9_maintenance_backup.py REHEARSE
```

## EXECUTE — blocked

There is no PhaseIX production execution command. Schema150 is unregistered and
the root policy evaluator does not grant execution. Do not bypass that refusal,
install a test issuer/policy in production,restore generic role defaults,start old
workers at advanced schemas or replay consumed approvals. Complete the engineering
and independently controlled gates in the final matrix first.
