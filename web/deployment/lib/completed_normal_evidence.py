"""Reuse exact executed application evidence without transferring its revision.

The approved plan pins the original files and their actual execution wrapper.
Changed image/source/input/runner identities fail; controller-only changes do
not relabel the accepted application as a new application build.
"""
import json
from pathlib import Path
import re

from deployment.lib.provider_recovery_runtime import readonly_configuration,file_digest

CASES=frozenset({'frontend_api_origin','backend_readiness','local_schema','existing_authentication',
    'original_mfa_aal2','aal1_privilege_denied','session_cookie_policy','tenant_isolation',
    'business_permissions','forms','reservations','builder','ecommerce','restricted_write_denial',
    'private_normal_write_activation','singleton_workers','required_integrations','rollback_current_data','learning_academy_referrals'})

def measured_record(binding):
    if (not isinstance(binding,dict) or set(binding)!={'path','sha256'}
            or not re.fullmatch('[0-9a-f]{64}',str(binding['sha256']))):
        raise RuntimeError('completed_upgrade_evidence_binding_invalid')
    path=readonly_configuration(Path(binding['path']),private=True)
    if file_digest(path)!=binding['sha256']:
        raise RuntimeError('completed_upgrade_evidence_bytes_changed')
    try:return json.loads(path.read_text())
    except (ValueError,TypeError):raise RuntimeError('completed_upgrade_evidence_invalid') from None

def verify_application_evidence(actor):
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
