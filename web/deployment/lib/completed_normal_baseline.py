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
    actor.assemble();actor.completed_evidence();actor.kernel.normal()
    if discover_split(operations,state,operations.repository_head(),operations.installed_sha())!=binding:
        raise RuntimeError('completed_normal_runtime_source_changed')
    return binding
