"""Attest the completed local NORMAL controller/application split, read-only.

Historical authorization is DATA, never approval for installation or startup.
The original full controller bytes and publication/completion are mandatory.
"""
import hashlib
import json
from pathlib import Path
import re

from deployment.lib.active_recovery_resumption import ROOT,load_saved_resumption_plan,controller_revision
from deployment.lib.active_recovery_inputs import INPUTS
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation')

def seal_compatible_release(contract, root, state_root):
    """Link current mutable release state to genuine immutable completion DATA."""
    from deployment.lib.completed_normal_admission import digest
    from deployment.lib.control_plane_upgrade import atomic_json
    if __import__('os').geteuid()!=0:
        raise RuntimeError('completed_compatible_root_required')
    root=Path(root);state_path=Path(state_root)/'state.json'
    completion=protected(root/'normal-completion.json',private=True)
    value=json.loads(completion.read_text());candidate=contract['candidate']
    if (root.name!=digest(contract) or value.get('context_sha256')!=root.name
            or value.get('mode')!='NORMAL' or value.get('schema')!=136
            or value.get('application_sha')!=candidate['source_sha']
            or value.get('controller_sha')!=candidate['controller_sha']):
        raise RuntimeError('completed_compatible_completion_invalid')
    state=json.loads(readonly_configuration(state_path,private=True).read_text())
    known=state.get('known_good_release') or {}
    if (state.get('active_slot')!=candidate['slot'] or known.get('slot')!=candidate['slot']
            or known.get('sha')!=candidate['source_sha'] or known.get('schema')!=136
            or state.get('in_progress_release') or state.get('rollback_failure')
            or 'completed_normal_upgrade' in known):
        raise RuntimeError('completed_compatible_release_state_invalid')
    known['completed_normal_upgrade']={'context_sha256':root.name,'completion_sha256':file_digest(completion)}
    atomic_json(state_path,state)

def attest_compatible_runtime(operations,state,production_sha,installed_sha):
    """Read-only attestation of the ordinary release after admitted completion.

    A mutable state marker selects a protected record; it supplies no authority.
    The original receipt, full frozen bytes, installed tree, genuine SQL record,
    boot controls, current grant and exact runtime all remain mandatory.
    """
    from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,verify_history
    from deployment.lib.completed_normal_boot_installation import CompletedNormalBootInstallation
    from deployment.lib.completed_normal_boot_actor import verify_live_configuration
    from deployment.lib.completed_normal_database import observe_native,require_normal_migration_boundary
    from deployment.lib.compatible_normal_boot import CompatibleNormalBoot
    from deployment.lib.emergency_routing_repair import Runtime
    from deployment.lib.active_recovery_inputs import controller_tree_digest
    from scripts.continue_completed_normal_upgrade import measure
    known=state.get('known_good_release') or {};marker=known.get('completed_normal_upgrade')
    if (not isinstance(marker,dict) or set(marker)!={'context_sha256','completion_sha256'}
            or any(not re.fullmatch('[0-9a-f]{64}',str(v)) for v in marker.values())):
        raise RuntimeError('completed_compatible_marker_invalid')
    root=ADMISSIONS/marker['context_sha256']
    authorization=json.loads(protected(root/'operator-authorization.json',private=True).read_text())
    source_hash=authorization.get('source_bundle_sha256');plan_hash=authorization.get('plan_sha256')
    package=BASE/('normal-source-'+str(source_hash))
    document,source=measure(package,source_hash,plan_hash)
    contract=dict(document['admission_contract'],plan_sha256=digest(document));candidate=contract['candidate']
    expected_authorization={'operation':OPERATION,'context_sha256':digest(contract),'plan_sha256':digest(document),
        'source_bundle_sha256':document['source_bundle_sha256'],'controller_sha':candidate['controller_sha'],
        'application_sha':candidate['source_sha']}
    def guard():
        if (digest(contract)!=root.name or authorization!=expected_authorization
                or json.loads(protected(root/'operator-authorization.json',private=True).read_text())!=authorization
                or measure(package,source_hash,plan_hash)!=(document,source)
                or production_sha!=installed_sha or installed_sha!=candidate['controller_sha']
                or operations.repository_head()!=production_sha or operations.installed_sha()!=installed_sha
                or controller_tree_digest()!=candidate['controller_tree_sha256']):
            raise RuntimeError('completed_compatible_controller_changed')
        verify_live_configuration(document);verify_history(contract)
        admission=json.loads(protected(root/'admission.json').read_text())
        if admission.get('operation')!=OPERATION or admission.get('contract')!=contract:
            raise RuntimeError('completed_compatible_admission_changed')
    guard()
    body=protected(root/'normal-completion.json',private=True)
    completion=json.loads(body.read_text())
    if (file_digest(body)!=marker['completion_sha256'] or completion.get('operation')!=OPERATION
            or completion.get('context_sha256')!=root.name or completion.get('schema')!=136
            or completion.get('mode')!='NORMAL' or completion.get('controller_sha')!=installed_sha
            or completion.get('application_sha')!=candidate['source_sha']
            or completion.get('images')!=candidate['images'] or completion.get('customer_database_restored') is not False
            or known.get('sha')!=candidate['source_sha'] or known.get('slot')!=candidate['slot']
            or state.get('active_slot')!=candidate['slot'] or known.get('schema')!=136
            or known.get('schema_compatible_min')!=115 or known.get('schema_compatible_max')!=136
            or state.get('in_progress_release') or state.get('rollback_failure')):
        raise RuntimeError('completed_compatible_release_changed')
    for kind in ('backend','frontend','worker'):
        if (known.get('images') or {}).get(kind)!=document['application_artifacts'][kind]:
            raise RuntimeError('completed_compatible_images_changed')
    backup=json.loads(protected(root/'post-migration-backup.json',private=True).read_text())
    if (completion.get('backup')!=backup or backup.get('schema')!=136
            or backup.get('restore',{}).get('status')!='logical_database_and_file_restore_passed'
            or backup.get('restore',{}).get('backup_schema')!=136
            or backup.get('node1',{}).get('checksum_exit_code')!=0):
        raise RuntimeError('completed_compatible_backup_changed')
    CompletedNormalBootInstallation(contract,document,package,guard,operations).installed()
    runtime=Runtime();schema=observe_native(contract,runtime)
    require_normal_migration_boundary(contract,schema,root,operations.state_root)
    def forbidden(*args,**kwargs):raise RuntimeError('completed_compatible_readonly_effect_forbidden')
    kernel=CompatibleNormalBoot(contract,source_guard=guard,native_verifier=lambda:observe_native(contract,runtime),
        publish_authority=forbidden,compensate_current_data=forbidden,runtime=runtime,state_root=operations.state_root)
    kernel.round(normal=True)
    runtime_record=json.loads(protected(root/'candidate-runtime.json',private=True).read_text())
    if known.get('worker_generation')!=runtime_record['worker_generation']:
        raise RuntimeError('completed_compatible_worker_generation_changed')
    guard()
    return {'application_sha':candidate['source_sha'],'controller_sha':installed_sha,'completion_root':str(root),
        'completion_sha256':marker['completion_sha256'],'completed_compatible_upgrade':True,'schema':schema}

def historical_source(plan):
    """Measure old frozen bytes as DATA, without importing historical code."""
    package=BASE/('normal-source-'+plan.source_bundle_sha256)
    body=protected(package/'source-bundle.json',private=True).read_bytes()
    if hashlib.sha256(body).hexdigest()!=plan.source_bundle_sha256:
        raise RuntimeError('completed_normal_historical_source_changed')
    manifest=json.loads(body)
    if manifest.get('version')!=1 or manifest.get('source_sha')!=controller_revision(plan):
        raise RuntimeError('completed_normal_historical_source_invalid')
    files=manifest.get('files',{})
    source=package/'source'
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if not files or set(files)!=actual:raise RuntimeError('completed_normal_historical_inventory_changed')
    for relative,expected in files.items():
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts or path.as_posix()!=relative or path.suffix in {'.pyc','.pyo'}:
            raise RuntimeError('completed_normal_historical_path_invalid')
        target=protected(source/path,private=True)
        if target.stat().st_mode&0o200 or file_digest(target)!=expected:
            raise RuntimeError('completed_normal_historical_bytes_changed')
    return manifest

def attest_split(state,root,production_sha,installed_sha):
    root=Path(root)
    if root.parent!=ROOT or not re.fullmatch('[0-9a-f]{64}',root.name):
        raise RuntimeError('completed_normal_root_invalid')
    plan=load_saved_resumption_plan(root)
    if (plan.digest!=root.name or production_sha!=installed_sha
            or controller_revision(plan)!=installed_sha):
        raise RuntimeError('completed_normal_controller_role_changed')
    known=state.get('known_good_release') or {}
    if (state.get('active_slot')!=plan.candidate_destination['slot'] or known.get('slot')!=state['active_slot']
            or known.get('sha')!=plan.source_sha or known.get('images')!=plan.candidate_images
            or known.get('provider')!='local' or known.get('schema')!=115
            or known.get('schema_compatible_min')!=115 or known.get('schema_compatible_max')!=115
            or state.get('in_progress_release') or state.get('rollback_failure')):
        raise RuntimeError('completed_normal_release_role_changed')
    receipt=json.loads(protected(root/'authorization.json',private=True).read_text())
    events=[json.loads(line) for line in protected(root/'events.jsonl',private=True).read_text().splitlines()]
    completion=json.loads(protected(root/'normal-completion.json',private=True).read_text())
    if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=plan.digest
            or receipt.get('source_bundle_sha256')!=plan.source_bundle_sha256 or not events
            or events[-1].get('phase')!='normal' or any(row.get('plan_sha256')!=plan.digest for row in events)
            or completion.get('operation')!='completed-normal-local-continuation'
            or completion.get('plan_sha256')!=plan.digest or completion.get('source_sha')!=plan.source_sha
            or completion.get('source_bundle_sha256')!=plan.source_bundle_sha256
            or completion.get('schema')!=115 or completion.get('images')!=plan.candidate_images
            or completion.get('database_restore_performed') is not False):
        raise RuntimeError('completed_normal_execution_changed')
    bound=completion.get('retained_execution_files',{})
    if set(bound)!={'normal-acceptance.json','post-cutover-backup.json','installed-controller.json','worker-owner.json','normal-publication.json'}:
        raise RuntimeError('completed_normal_execution_incomplete')
    for name,expected in bound.items():
        if file_digest(protected(root/name,private=True))!=expected:
            raise RuntimeError('completed_normal_execution_bytes_changed')
    source=historical_source(plan)
    if protected(INPUTS['controller']).read_text().strip()!=installed_sha:
        raise RuntimeError('completed_normal_installed_provenance_changed')
    for relative,expected in source['files'].items():
        if relative.startswith('web/deployment/') and relative!='web/deployment/bin/madar-install-control-plane':
            if file_digest(protected(INPUTS['controller'].parent/relative.removeprefix('web/deployment/')))!=expected:
                raise RuntimeError('completed_normal_installed_bytes_changed')
    publication=json.loads(protected(root/'normal-publication.json',private=True).read_text())
    outputs=publication.get('published_sha256',{})
    if set(outputs)!={'production_configuration','backup_configuration','release_state','traffic'}:
        raise RuntimeError('completed_normal_publication_incomplete')
    for key,expected in outputs.items():
        if file_digest(readonly_configuration(INPUTS[key],private=True))!=expected:
            raise RuntimeError('completed_normal_publication_changed')
    return {'application_sha':plan.source_sha,'controller_sha':installed_sha,'completion_root':str(root),
        'original_plan_sha256':plan.digest,'completion_sha256':file_digest(root/'normal-completion.json')}

def discover_split(operations,state,production_sha,installed_sha):
    slot=state.get('active_slot')
    if slot not in {'blue','green'}:raise RuntimeError('completed_normal_slot_invalid')
    result=operations.command('completed_normal_binding_inspect',['docker','inspect',f'madar-{slot}-backend'])
    rows=json.loads(result.stdout)
    if len(rows)!=1:raise RuntimeError('completed_normal_authority_binding_invalid')
    mounts=[m for m in rows[0].get('Mounts',[]) if m.get('Destination')=='/run/madar/business-write-authority' and m.get('Type')=='bind' and m.get('RW') is False]
    if len(rows)!=1 or len(mounts)!=1:raise RuntimeError('completed_normal_authority_binding_invalid')
    path=Path(mounts[0]['Source'])
    if path.name!='write-authority':raise RuntimeError('completed_normal_authority_path_invalid')
    binding=attest_split(state,path.parent,production_sha,installed_sha)
    authority=json.loads(protected(path/'authority.json',private=False).read_text())
    if authority.get('mode')!='NORMAL' or authority.get('release_sha')!=binding['application_sha'] or authority.get('schema')!=115:
        raise RuntimeError('completed_normal_positive_authority_required')
    return binding

def attest_runtime(operations,state):
    """Use the completed continuation's exact-ID live verifier, read-only.

    Its image IDs and parser/worker inventory differ from an ordinary release;
    never synthesize a registry reference or skip specification/ownership checks.
    """
    from types import SimpleNamespace
    from deployment.lib.active_recovery_boot_actor import ActiveRecoveryBootActor
    binding=discover_split(operations,state,operations.repository_head(),operations.installed_sha())
    root=Path(binding['completion_root']);plan=load_saved_resumption_plan(root)
    source=SimpleNamespace(verify=lambda:historical_source(plan))
    actor=ActiveRecoveryBootActor(plan,root,BASE/('normal-source-'+plan.source_bundle_sha256),source=source)
    actor.assemble();bind_origin_specification_verifiers(actor)
    actor.completed_evidence();actor.kernel.normal()
    if discover_split(operations,state,operations.repository_head(),operations.installed_sha())!=binding:
        raise RuntimeError('completed_normal_runtime_source_changed')
    return binding

def bind_origin_specification_verifiers(actor):
    """Use the bounded unordered-mount comparator only for measured origin IDs.

    Historical raw hashes remain unchanged. The ordinary old continuation keeps
    its strict default; this new source-bound admission/boot path opts in after
    assembling the protected completed origin, not an arbitrary new candidate.
    """
    from deployment.lib.completed_normal_resources import origin_spec_matches
    actor.kernel.spec_matcher=origin_spec_matches
    actor.workers.spec_matcher=origin_spec_matches
