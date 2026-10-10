"""Validate retained actual executions without expanding their proven scope.

Engineering logs and agent-authored PASS packets are not accepted. Every record
is root-protected, hash-bound, tied to immutable executed source and its exact
isolated argv. Validation changes no record, checkpoint, runtime or database.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from deployment.lib.provider_recovery_runtime import protected, file_digest, digest

PREPARATION = Path('/var/lib/madar-control-plane/normal-local-preparation')
RESTORE = PREPARATION/'native-restore-execution-7qk3iqoh/execution.json'
CHECKPOINT = PREPARATION/'checkpoint-20261008T224529Z'
MFA = PREPARATION/'existing-mfa-runner-emk5jg74/actual-execution.json'
MFA_SHA = 'a48becd2235ceef0b36d8fefa4c0dc383b256570b40d589c3f6a7f5163171e07'
RECONCILIATION = PREPARATION/'local-reconciliation-runner-fx_e0aha/actual-execution.json'
HASH = re.compile(r'[0-9a-f]{64}')


def actual_inline_execution(path, expected_hash, operation, entry, *, source_directory=None):
    path=protected(Path(path),private=True)
    if not HASH.fullmatch(str(expected_hash)) or file_digest(path)!=expected_hash:
        raise RuntimeError('actual_execution_record_changed')
    record=json.loads(path.read_text())
    if source_directory not in {None,'source'}:raise RuntimeError('actual_execution_source_layout_invalid')
    source_root=path.parent if source_directory is None else path.parent/'source'
    if (record.get('operation')!=operation or type(record.get('exit_code')) is not int
            or record['exit_code']!=0 or record.get('stderr')!=''
            or record.get('argv')!=['/usr/bin/python3','-I','-B',str(source_root/entry)]):
        raise RuntimeError('actual_execution_not_successful')
    try:
        start=datetime.fromisoformat(record['started_at']);finish=datetime.fromisoformat(record['finished_at'])
        if start.tzinfo is None or finish.tzinfo is None or not start<=finish<=datetime.now(timezone.utc):
            raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise RuntimeError('actual_execution_time_invalid') from None
    files=record.get('source_files')
    if not isinstance(files,dict) or entry not in files:
        raise RuntimeError('actual_execution_source_missing')
    for relative,expected in files.items():
        relative_path=Path(relative)
        if (not isinstance(relative,str) or relative_path.is_absolute() or '..' in relative_path.parts
                or relative_path.as_posix()!=relative or not HASH.fullmatch(str(expected))):
            raise RuntimeError('actual_execution_source_invalid')
        source=protected(source_root/relative_path,private=True)
        if source.stat().st_mode&0o200 or file_digest(source)!=expected:
            raise RuntimeError('actual_execution_source_changed')
    # Stdout is retained from actual subprocess execution, including stage rows.
    # No caller-supplied report or transferred source-SHA claim is consulted.
    try:
        rows=[json.loads(line) for line in record['stdout'].splitlines()]
        if not rows or not all(isinstance(row,dict) for row in rows):raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise RuntimeError('actual_execution_transcript_invalid') from None
    return rows[-1],record


def verify_original_factor_execution(manifest_sha256):
    report,_=actual_inline_execution(MFA,MFA_SHA,'actual-private-existing-checkpoint-mfa',
        'web/scripts/verify_existing_checkpoint_mfa.py')
    factors=report.get('existing_factor_verification',{})
    if (report.get('checkpoint_manifest_sha256')!=manifest_sha256 or report.get('schema')!=115
            or factors.get('original_verified_factors_exercised')!=2
            or factors.get('original_factor_aal2_verified') is not True
            or factors.get('original_password_verifiers_restored_in_private_copy') is not True
            or report.get('production_modified') is not False
            or report.get('customer_passwords_used') is not False
            or report.get('application_migrations_executed') is not False
            or report.get('original_checkpoint_modified') is not False
            or report.get('application_acceptance_proven') is not False):
        raise RuntimeError('actual_original_factor_scope_invalid')
    return {'original_factors':2,'private_original_factor_aal2':True,
        'current_application_acceptance':False,'execution_sha256':MFA_SHA}


def verify_local_reconciliation_execution(plan):
    compensated=(getattr(plan,'candidate_destination',None) or {}).get('post_compensation')
    from deployment.lib.active_recovery_resumption import controller_revision
    source_sha=controller_revision(plan)
    if compensated and not re.fullmatch('[0-9a-f]{40}',source_sha):
        raise RuntimeError('actual_reconciliation_source_invalid')
    path=RECONCILIATION
    if compensated:
        namespace=PREPARATION/('local-post-compensation-reconciliation-'+source_sha)
        if not HASH.fullmatch(str(plan.reconciliation_execution_sha256)):
            raise RuntimeError('actual_reconciliation_record_hash_invalid')
        index=json.loads(protected(namespace/('index-'+plan.reconciliation_execution_sha256+'.json'),private=True).read_text())
        path=Path(index.get('execution',''))
        if (set(index)!={'execution'} or path.name!='actual-execution.json' or path.parent.parent!=namespace
                or not re.fullmatch('run-[0-9a-f]{12}',path.parent.name)):
            raise RuntimeError('actual_reconciliation_record_path_invalid')
    report,_=actual_inline_execution(path,plan.reconciliation_execution_sha256,
        'root-supervised-current-local-read-only-reconciliation','web/scripts/observe_current_local_reconciliation.py',source_directory='source')
    packet=report.get('snapshot',{})
    roots=packet.get('table_roots',[])
    if (report.get('operation')!='actual-current-local-read-only-reconciliation'
            or report.get('retained_inputs')!=plan.retained_inputs or report.get('schema')!=115
            or report.get('production_modified') is not False or report.get('consumers_started') is not False
            or report.get('business_writes_enabled') is not False or report.get('authorization_issued') is not False
            or packet.get('schema')!=115 or packet.get('migration_executed') is not False
            or packet.get('customer_data_modified') is not False or packet.get('database_restore_performed') is not False
            or not roots or len({row.get('table') for row in roots})!=len(roots)
            or any(set(row)!={'table','count','sha256'} or not isinstance(row['table'],str)
                or type(row['count']) is not int or row['count']<0 or not HASH.fullmatch(str(row['sha256'])) for row in roots)
            or digest(packet)!=report.get('snapshot_sha256')):
        raise RuntimeError('actual_reconciliation_scope_invalid')
    # A repeatable-read snapshot is not a durable source fence, nor a claim that
    # auth/session tables cannot subsequently change while business writes deny.
    return {'schema':115,'tables':len(roots),'snapshot_sha256':report['snapshot_sha256'],
        'source_fence_proven':False,'authorization_issued':False}
