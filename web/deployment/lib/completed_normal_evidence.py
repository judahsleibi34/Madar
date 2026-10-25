"""Reuse exact executed application evidence without transferring its revision.

The approved plan pins the original files and their actual execution wrapper.
Changed image/source/input/runner identities fail; controller-only changes do
not relabel the accepted application as a new application build.
"""
import hashlib
import json
import os
import stat
from pathlib import Path
import re

from deployment.lib.provider_recovery_runtime import readonly_configuration,file_digest
from deployment.lib.completed_normal_profile import profile, MANUAL, APPLICATION, COMMERCIAL, FENCED, OUTBOX, RECONCILED

CASES=frozenset({'frontend_api_origin','backend_readiness','local_schema','existing_authentication',
    'original_mfa_aal2','aal1_privilege_denied','session_cookie_policy','tenant_isolation',
    'business_permissions','forms','reservations','builder','ecommerce','restricted_write_denial',
    'private_normal_write_activation','singleton_workers','required_integrations','rollback_current_data','learning_academy_referrals'})

def measured_record(binding):
    if (not isinstance(binding,dict) or set(binding)!={'path','sha256'}
            or not re.fullmatch('[0-9a-f]{64}',str(binding['sha256']))):
        raise RuntimeError('completed_upgrade_evidence_binding_invalid')
    path=readonly_configuration(Path(binding['path']),private=True)
    # Operator-owned evidence is mutable input, never a protected receipt.
    # Hash and deserialize exactly the same bounded capture; do not reopen a
    # pathname after authenticating its earlier contents.
    try:
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as source:
            measured=os.fstat(source.fileno())
            if not stat.S_ISREG(measured.st_mode) or not 0<measured.st_size<=2*1024**2:
                raise RuntimeError('completed_upgrade_evidence_size_invalid')
            body=source.read(measured.st_size+1)
    except OSError:raise RuntimeError('completed_upgrade_evidence_unavailable') from None
    if len(body)!=measured.st_size or hashlib.sha256(body).hexdigest()!=binding['sha256']:
        raise RuntimeError('completed_upgrade_evidence_bytes_changed')
    try:return json.loads(body)
    except (ValueError,TypeError):raise RuntimeError('completed_upgrade_evidence_invalid') from None

def verify_application_evidence(actor):
    if actor.contract.get('operation') == RECONCILED.operation:
        return verify_reconciled_application_evidence(actor)
    if profile(actor.contract) in (MANUAL,APPLICATION,COMMERCIAL,FENCED,OUTBOX):
        return verify_manual_application_evidence(actor)
    document=actor.document;contract=actor.contract
    bindings=document['application_evidence']
    if set(bindings)!={'115','136','execution'}:
        raise RuntimeError('completed_upgrade_application_evidence_inventory_invalid')
    execution=measured_record(bindings['execution'])
    result=execution.get('result',{});combined=result.get('existing_factor_verification',{})
    roots=combined.get('auth_storage_roots_preserved',{})
    if (execution.get('status')!='passed' or result.get('operation')!='actual-current-backup-private-native-restore'
            or result.get('production_modified') is not False or result.get('schema')!=136
            or result.get('native_login_and_aal2_verified') is not True
            or result.get('role_attributes_password_verifiers_and_grantors_verified') is not True
            or result.get('owners_and_acls_restored') is not True
            or combined.get('all_original_row_counts_preserved') is not True
            or not isinstance(roots,dict) or set(roots)!={'auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets'}
            or any(not isinstance(v,dict) or type(v.get('rows')) is not int or v['rows']<0
                or not re.fullmatch('[0-9a-f]{64}',str(v.get('root',''))) for v in roots.values())):
        raise RuntimeError('completed_upgrade_application_execution_incomplete')
    for schema in (115,136):
        report=measured_record(bindings[str(schema)])
        cases=report.get('cases',{})
        if (report!=combined.get('schema'+str(schema)) or report.get('source_sha')!=contract['candidate']['source_sha']
                or report.get('images')!=contract['candidate']['images'] or set(cases)!=CASES
                or any(not isinstance(v,dict) or v.get('verified') is not True or not v.get('observations') for v in cases.values())
                or cases['local_schema']['observations'].get('schema')!=schema
                or not re.fullmatch('[0-9a-f]{64}',str(report.get('runner_sha256','')))
                or not re.fullmatch('[0-9a-f]{64}',str(report.get('input_sha256','')))):
            raise RuntimeError('completed_upgrade_application_acceptance_incompatible')
    # Original acceptance covers bytes; remeasure runtime-selected index IDs
    # and immutable labels before any installer or candidate effect.
    artifacts=document['application_artifacts']
    for role in ('backend','frontend'):
        expected=contract['candidate']['images'][role]
        rows=json.loads(actor.runtime.command(['docker','image','inspect',artifacts[role]]))
        if len(rows)!=1 or rows[0]['Id']!=expected:
            raise RuntimeError('completed_upgrade_accepted_image_changed')
        labels=rows[0]['Config'].get('Labels',{})
        if (labels.get('org.opencontainers.image.revision')!=contract['candidate']['source_sha']
                or labels.get('com.madar.release.sha')!=contract['candidate']['source_sha']
                or labels.get('com.madar.release.built_at')!=artifacts['build_timestamp']
                or (role=='frontend' and labels.get('com.madar.frontend.api_origin')!='/api')):
            raise RuntimeError('completed_upgrade_accepted_image_provenance_changed')
    replica=document['node1_replica']
    if (set(replica)!={'host','filesystem_uuid','configuration_sha256'} or replica['host']!='madar-node1-lan'
            or replica['configuration_sha256']!=document['live_configuration_sha256']['node1_configuration']):
        raise RuntimeError('completed_upgrade_node1_binding_changed')
    return {'node1_replica':replica,'application_source_sha':contract['candidate']['source_sha'],
            'images':contract['candidate']['images'],'historical_evidence_relabelled':False}

def verify_complete_rehearsal(actor):
    if actor.contract.get('operation') == RECONCILED.operation:
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        validate_provider_preparation(actor.contract)
        # A fresh genesis report cannot fill the independently protected
        # preserved-application/issuer/restore/reboot acceptance boundary.
        raise RuntimeError('schema160_protected_rehearsal_acceptance_required')
    if profile(actor.contract) in (MANUAL,APPLICATION,COMMERCIAL,FENCED,OUTBOX):
        return verify_manual_controller_validation(actor)
    record=measured_record(actor.document['complete_rehearsal'])
    expected={'operation':'actual-private-completed-normal-upgrade','controller_sha':actor.contract['candidate']['controller_sha'],
        'source_bundle_sha256':actor.document['source_bundle_sha256'],'application_sha':actor.contract['candidate']['source_sha'],
        'images':actor.contract['candidate']['images'],'production_modified':False,'starting_schema':115,'final_schema':136}
    if any(record.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('completed_upgrade_rehearsal_source_binding_changed')
    gates={'historical_admission','candidate_staging','exclusive_write_handoff','singleton_workers','bridge_publication',
        'controller_installation','pre_migration_backup','migration_116_136','schema136_application','forward_resumption',
        'post_migration_backup','independent_restore','node1_replication','backup_timers','docker_restart','host_boot',
        'failure_compensation','interrupted_execution'}
    if (record.get('status')!='passed' or set(record.get('gates',{}))!=gates
            or any(row.get('verified') is not True or not row.get('observations') for row in record['gates'].values())
            or actor.document['complete_rehearsal']['sha256']!=actor.contract['rehearsal_sha256']):
        raise RuntimeError('completed_upgrade_complete_rehearsal_required')
    return record


def verify_manual_application_evidence(actor):
    """Reuse actual144 image execution and unchanged SQL, without relabelling.

    This is component acceptance, not a complete deployment/reboot rehearsal.
    The separately approved maintenance plan must disclose that distinction.
    """
    contract=actor.contract;selected=profile(contract);document=actor.document
    bindings=document['application_evidence']
    target=str(selected.target)
    expected_bindings=({target,'runner'} if selected is APPLICATION else {target,'sql','runner'})
    if selected in (FENCED, OUTBOX):expected_bindings.add('provenance')
    if set(bindings)!=expected_bindings:
        raise RuntimeError('completed_manual_application_evidence_inventory_invalid')
    report=measured_record(bindings[target]);cases=report.get('cases',{})
    runner=readonly_configuration(Path(bindings['runner']['path']),private=True)
    if (file_digest(runner)!=bindings['runner']['sha256'] or report.get('runner_sha256')!=bindings['runner']['sha256']
            or report.get('operation')!=f'schema{selected.target}-network-none-exact-image-acceptance'
            or report.get('status')!='passed' or report.get('production_modified') is not False
            or report.get('schema')!=selected.target or report.get('source_sha')!=contract['candidate']['source_sha']
            or report.get('images')!=contract['candidate']['images'] or set(cases)!=CASES
            or any(v.get('verified') is not True or not v.get('observations') for v in cases.values())
            or cases['local_schema']['observations'].get('schema')!=selected.target
            or report.get('isolation',{}).get('interfaces')!=[[1,'lo']]
            or report.get('last_readiness',{}).get('ready') is not True):
        raise RuntimeError('completed_manual_application_acceptance_incompatible')
    sql={} if selected is APPLICATION else measured_record(bindings['sql'])
    if selected is MANUAL and (sql.get('scope')!='private-current-backup-seven-migration-rehearsal'
            or sql.get('starting_schema')!=selected.source or sql.get('final_schema')!=selected.target
            or sql.get('manifest_sha256')!=contract['migration_manifest_sha256']
            or sql.get('production_modified') is not False or sql.get('invalid_indexes')!=0
            or sql.get('original_data_changes')!=['public.application_schema_state']
            or any(sql.get(k) is not True for k in ('original_owner_preserved','auth_storage_roots_preserved',
                'unrelated_acl_preserved','migration139_acl_tightening_verified'))
            or sql.get('forward_resume',{}).get('status')!='completed'):
        raise RuntimeError('completed_manual_sql_evidence_incompatible')
    if selected is COMMERCIAL and (
            sql.get('scope')!='private-current-backup-commercial-migration-rehearsal'
            or sql.get('starting_schema')!=selected.source or sql.get('final_schema')!=selected.target
            or sql.get('manifest_sha256')!=contract['migration_manifest_sha256']
            or sql.get('production_modified') is not False or sql.get('invalid_indexes')!=0
            or any(sql.get(k) is not True for k in ('original_rows_preserved',
                'auth_storage_roots_preserved','price_book_delta_verified'))
            or sql.get('forward_resume',{}).get('status')!='completed'):
        raise RuntimeError('completed_commercial_sql_evidence_incompatible')
    if selected in (FENCED, OUTBOX) and (
            sql.get('scope')!='private-current-backup-coordinated'+str(selected.target)+'-rehearsal'
            or sql.get('starting_schema')!=146 or sql.get('final_schema')!=selected.target
            or sql.get('manifest_sha256')!=contract['migration_manifest_sha256']
            or sql.get('production_modified') is not False or sql.get('invalid_indexes')!=0
            or any(sql.get(k) is not True for k in ('original_rows_preserved','auth_storage_roots_preserved',
                'protocol2_verified','legacy_writes_denied','reservation_guard_verified','interruption_matrix_verified','full_auth_storage_inventory_verified'))
            or sql.get('forward_resume',{}).get('status')!='completed'):
        raise RuntimeError('schema148_current_data_evidence_incompatible')
    if selected is OUTBOX and any(sql.get(key) is not True for key in (
            'outbox_protocol2_verified','deletion_consumption_fenced','provider_lifecycle_verified')):
        raise RuntimeError('schema149_current_data_evidence_incomplete')
    if selected in (FENCED, OUTBOX):
        from deployment.lib.schema148_artifacts import verify_provenance
        verify_provenance(actor,measured_record(bindings['provenance']))
    artifacts=document['application_artifacts']
    for role in ('backend','frontend'):
        rows=json.loads(actor.runtime.command(['docker','image','inspect',artifacts[role]]))
        if len(rows)!=1 or rows[0]['Id']!=contract['candidate']['images'][role]:
            raise RuntimeError('completed_upgrade_accepted_image_changed')
        labels=rows[0]['Config'].get('Labels',{})
        if selected in (FENCED, OUTBOX) and (labels.get('com.madar.build.mode')!='fresh-locked-ci' or labels.get('com.madar.staging.build_mode')):
            raise RuntimeError('schema148_source_overlay_is_not_release_provenance')
        if (labels.get('org.opencontainers.image.revision')!=contract['candidate']['source_sha']
                or labels.get('com.madar.release.sha')!=contract['candidate']['source_sha']
                or labels.get('com.madar.release.built_at')!=artifacts['build_timestamp']
                or role=='frontend' and labels.get('com.madar.frontend.api_origin')!='/api'):
            raise RuntimeError('completed_upgrade_accepted_image_provenance_changed')
    replica=document['node1_replica']
    if (set(replica)!={'host','filesystem_uuid','configuration_sha256'} or replica['host']!='madar-node1-lan'
            or not re.fullmatch('[0-9a-f-]{36}',str(replica['filesystem_uuid']))
            or replica['configuration_sha256']!=document['live_configuration_sha256']['node1_configuration']):
        raise RuntimeError('completed_upgrade_node1_binding_changed')
    return {'node1_replica':replica,'application_source_sha':contract['candidate']['source_sha'],
        'images':contract['candidate']['images'],'historical_evidence_relabelled':False,
        'complete_upgrade_rehearsal':False,'production_envoy_tested_in_this_run':False}


def verify_manual_controller_validation(actor):
    """Exact-source CI plus actually executed focused controller checks.

    A manual maintenance operation has a distinct approval scope. No old full
    rehearsal is reused to attest new executables, and no untested restart or
    combined private deployment is represented as PASS.
    """
    selected=profile(actor.contract)
    if selected not in (MANUAL,APPLICATION,COMMERCIAL,FENCED,OUTBOX):raise RuntimeError('completed_manual_validation_operation_invalid')
    expected_mode='component-verified-application-update' if selected is APPLICATION else 'component-verified-maintenance'
    if (actor.document.get('validation_mode')!=expected_mode
            or actor.document.get('complete_upgrade_rehearsal') is not False
            or actor.document.get('real_restart_rehearsal') is not False):
        raise RuntimeError('completed_manual_validation_scope_invalid')
    record=measured_record(actor.document['controller_validation'])
    if (record.get('operation')!='exact-source-focused-controller-validation'
            or record.get('controller_sha')!=actor.contract['candidate']['controller_sha']
            or record.get('status')!='passed' or record.get('production_modified') is not False
            or type(record.get('tests_run')) is not int or record['tests_run']<1
            or record.get('failures')!=0 or record.get('errors')!=0
            or actor.document['controller_validation']['sha256']!=actor.contract['rehearsal_sha256']):
        raise RuntimeError('completed_manual_controller_validation_incomplete')
    for relative,expected in record.get('source_files',{}).items():
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts or file_digest(actor.package/'source'/path)!=expected:
            raise RuntimeError('completed_manual_controller_validation_source_changed')
    if not record.get('source_files'):
        raise RuntimeError('completed_manual_controller_validation_source_missing')
    ci=measured_record(actor.document['controller_ci'])
    if set(ci)!={'backend','frontend'}:
        raise RuntimeError('completed_manual_controller_ci_missing')
    workflow_names={'backend':'Backend Check','frontend':'Frontend Check'}
    for name,run in ci.items():
        if (run.get('headSha')!=record['controller_sha'] or run.get('status')!='completed'
                or run.get('conclusion')!='success' or run.get('workflowName')!=workflow_names[name]
                or not re.fullmatch(r'https://github\.com/judahsleibi34/Madar/actions/runs/[0-9]+',str(run.get('url','')))):
            raise RuntimeError('completed_manual_controller_ci_incomplete')
        # Requery the trusted repository, rather than trusting a local CI PASS
        # packet. The root operation uses the existing madar GitHub identity;
        # tokens and arbitrary URLs are never passed through the plan or logs.
        observed=json.loads(actor.ops.command('completed_manual_ci_'+name,[
            '/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','run','view',run['url'].rsplit('/',1)[1],
            '--repo','judahsleibi34/Madar','--json','headSha,status,conclusion,workflowName,url']).stdout)
        if observed!=run:
            raise RuntimeError('completed_manual_controller_ci_changed')
    return record


FRESH_WORKFLOW = '.github/workflows/full-provider-staging.yml'
FRESH_NAME = 'Fresh Application Staging'
FRESH_SERVICES = frozenset({'postgres','redis','auth','rest','storage','gateway',
    'backend','frontend','accepted-frontend','notification-worker','calendar-sync-worker','deletion-worker'})


def verified_fresh_application(actor, binding, image_binding, image_receipt):
    """Authenticate ordinary fresh acceptance; never certify a protected upgrade.

    Fixed GitHub API requery + a bounded authenticated ZIP prevent a mutable
    caller PASS packet from authorizing its own source or runtime. The caller
    must independently authenticate candidate image bytes as well.
    """
    from deployment.lib.schema148_artifacts import REPOSITORY, authenticated_archive
    from deployment.lib.migration_inventory import strict_json
    from deployment.lib.completed_normal_admission import validate_provider_preparation
    if validate_provider_preparation(actor.contract) is not RECONCILED:
        raise RuntimeError('schema160_application_profile_required')
    if (not isinstance(binding,dict) or set(binding)!={'archive','artifact_id','run_id'}
            or any(type(binding[k]) is not int or binding[k]<=0 for k in ('artifact_id','run_id'))):
        raise RuntimeError('schema160_fresh_evidence_binding_invalid')
    if (not isinstance(image_binding,dict) or set(image_binding)!={'archive','artifact_id','run_id'}
            or any(type(image_binding[k]) is not int or image_binding[k]<=0 for k in ('artifact_id','run_id'))):
        raise RuntimeError('schema160_fresh_image_binding_changed')
    source=actor.contract['candidate']['source_sha']

    def api(endpoint):
        raw=actor.ops.command('schema160_fresh_evidence',[
            '/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','api',
            'repos/'+REPOSITORY+'/actions/'+endpoint],timeout=30).stdout
        if len(raw)>2*1024**2:raise RuntimeError('schema160_fresh_api_response_limit')
        packet=strict_json(raw.encode())
        if not isinstance(packet,dict):raise RuntimeError('schema160_fresh_api_invalid')
        return packet

    def observe():
        artifact=api('artifacts/'+str(binding['artifact_id']))
        run=api('runs/'+str(binding['run_id']))
        latest=api('workflows/full-provider-staging.yml/runs?head_sha='+source+'&per_page=100').get('workflow_runs',[])
        if (not isinstance(latest,list) or not latest or len(latest)>100
                or any(not isinstance(r,dict) or type(r.get('id')) is not int for r in latest)
                or max(r['id'] for r in latest)!=run.get('id')
                or type(run.get('id')) is not int or run.get('id')!=binding['run_id'] or run.get('head_sha')!=source
                or type(run.get('run_attempt')) is not int or run['run_attempt']<1
                or run.get('status')!='completed' or run.get('conclusion')!='success'
                or run.get('path')!=FRESH_WORKFLOW or run.get('name')!=FRESH_NAME
                or run.get('repository',{}).get('full_name')!=REPOSITORY
                or run.get('head_repository',{}).get('full_name')!=REPOSITORY
                or type(artifact.get('id')) is not int or artifact.get('id')!=binding['artifact_id'] or artifact.get('expired') is not False
                or artifact.get('workflow_run',{}).get('id')!=run['id']
                or artifact.get('workflow_run',{}).get('head_sha')!=source
                or artifact.get('name')!=f"full-provider-{source}-{run['id']}-{run['run_attempt']}"
                or type(artifact.get('size_in_bytes')) is not int or not 0<artifact['size_in_bytes']<=2*1024**2
                or not re.fullmatch('sha256:[0-9a-f]{64}',str(artifact.get('digest')))):
            raise RuntimeError('schema160_fresh_api_identity_changed')
        image_artifact=api('artifacts/'+str(image_binding['artifact_id']))
        image_run=api('runs/'+str(image_binding['run_id']))
        if (type(image_run.get('id')) is not int or image_run.get('id')!=image_binding['run_id']
                or image_run.get('head_sha')!=source or image_run.get('status')!='completed'
                or image_run.get('conclusion')!='success'
                or image_run.get('path')!='.github/workflows/schema148-artifacts.yml'
                or image_run.get('name')!='Schema148 Candidate Artifacts'
                or image_run.get('repository',{}).get('full_name')!=REPOSITORY
                or image_run.get('head_repository',{}).get('full_name')!=REPOSITORY
                or type(image_run.get('run_attempt')) is not int or image_run['run_attempt']<1
                or image_run['run_attempt']!=image_receipt.get('run_attempt')
                or image_artifact.get('name')!=f"schema148-candidate-{source}-{image_run['id']}-{image_run['run_attempt']}"
                or type(image_artifact.get('id')) is not int or image_artifact.get('id')!=image_binding['artifact_id']
                or image_artifact.get('expired') is not False
                or image_artifact.get('workflow_run',{}).get('id')!=image_binding['run_id']
                or image_artifact.get('workflow_run',{}).get('head_sha')!=source
                or not re.fullmatch('sha256:[0-9a-f]{64}',str(image_artifact.get('digest')))):
            raise RuntimeError('schema160_fresh_image_binding_changed')
        return artifact,run,image_artifact,image_run

    before=observe();artifact,run,image_artifact,image_run=before
    path=readonly_configuration(Path(binding['archive']),private=True)
    with authenticated_archive(path,artifact['digest'],max_bytes=artifact['size_in_bytes']) as archive:
        entries=archive.infolist()
        if (len(entries)!=1 or entries[0].filename!='full-provider-acceptance.json'
                or entries[0].is_dir() or stat.S_ISLNK(entries[0].external_attr>>16)
                or entries[0].flag_bits&1 or not 0<entries[0].file_size<=512*1024):
            raise RuntimeError('schema160_fresh_archive_inventory_invalid')
        report=strict_json(archive.read(entries[0]))
    expected={'version':1,'status':'PASS','source_sha':source,'schema':160,
        'acceptance_kind':'fresh_application','origin_schema':None,
        'existing_database_upgrade_accepted':False,'protected_controller_execution':False,
        'production_authorized':False,'source_overlay_used':False,
        'native_auth_mfa_refresh_csrf_storage_notifications_readiness':True,
        'native_tenant_read_write_isolation':True,'images':actor.contract['candidate']['images'],
        'worker_protocols':{'delivery':2,'outbox':2,'deletion':2},
        'artifact_id':image_binding['artifact_id'],'run_id':image_binding['run_id'],
        'run_attempt':image_receipt['run_attempt'],'archive_sha256':image_artifact['digest']}
    if (not isinstance(report,dict) or any(report.get(k)!=v for k,v in expected.items())
            or any(type(report.get(k)) is not type(v) for k,v in expected.items())
            or report.get('protected_upgrade_status')!='BLOCKED_DEFERRED'
            or not isinstance(report.get('runtime'),dict) or set(report['runtime'])!=FRESH_SERVICES
            or any(type(x) is not int or x!=2 for x in report.get('worker_protocols',{}).values())):
        raise RuntimeError('schema160_fresh_report_incompatible')
    for name,row in report['runtime'].items():
        role='backend' if name in {'backend','notification-worker','calendar-sync-worker','deletion-worker'} else (
            'frontend' if name in {'frontend','accepted-frontend','gateway'} else None)
        if (not isinstance(row,dict) or not re.fullmatch('[0-9a-f]{64}',str(row.get('id')))
                or row.get('running') is not True or row.get('health') not in ('healthy','not-configured')
                or role is not None and row.get('image')!=actor.contract['candidate']['images'][role]
                or name=='redis' and row.get('image')!=actor.contract['candidate']['redis_image']):
            raise RuntimeError('schema160_fresh_runtime_incompatible')
    if observe()!=before:raise RuntimeError('schema160_fresh_evidence_changed_during_capture')
    return {'fresh_application_accepted':True,'preserved_upgrade_accepted':False,
        'authority_issued':False,'source_sha':source,'schema':160,
        'artifact_id':artifact['id'],'run_id':run['id'],'run_attempt':run['run_attempt'],
        'archive_sha256':artifact['digest']}


def verify_reconciled_application_evidence(actor):
    from deployment.lib.completed_normal_admission import validate_provider_preparation
    from deployment.lib.schema148_artifacts import verify_provenance
    if validate_provider_preparation(actor.contract) is not RECONCILED:
        raise RuntimeError('schema160_application_profile_required')
    from deployment.lib.schema160_release import captured_source
    captured_source(actor.package/'source')
    bindings=actor.document['application_evidence']
    if not isinstance(bindings,dict) or set(bindings)!={'provenance','fresh_application'}:
        raise RuntimeError('schema160_application_evidence_inventory_invalid')
    image_binding=measured_record(bindings['provenance'])
    receipt=verify_provenance(actor,image_binding)
    if receipt.get('build_timestamp')!=actor.document['application_artifacts']['build_timestamp']:
        raise RuntimeError('schema160_application_build_timestamp_changed')
    fresh=verified_fresh_application(actor,measured_record(bindings['fresh_application']),image_binding,receipt)
    replica=actor.document['node1_replica']
    if (set(replica)!={'host','filesystem_uuid','configuration_sha256'} or replica['host']!='madar-node1-lan'
            or not re.fullmatch('[0-9a-f-]{36}',str(replica['filesystem_uuid']))
            or replica['configuration_sha256']!=actor.document['live_configuration_sha256']['node1_configuration']):
        raise RuntimeError('schema160_application_receiver_binding_changed')
    return {'node1_replica':replica,'application_source_sha':actor.contract['candidate']['source_sha'],
        'images':actor.contract['candidate']['images'],'historical_evidence_relabelled':False,
        'fresh_application':fresh,'complete_upgrade_rehearsal':False,'node1_recovery_accepted':False}
