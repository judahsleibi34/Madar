"""Independently render the same frozen Compose builder used by staging.

The rendered model contains private environment values and never goes to logs
or an operator-writable PASS packet. Only Docker's config command is permitted.
"""
from contextlib import contextmanager
import importlib.machinery
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import subprocess
import base64
import re

from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery_runtime import readonly_configuration
from deployment.lib.completed_normal_profile import profile


def accepted_compose_blobs(sha,objects):
    """Verify accepted commit/tree bytes without fetching into production.

    These are immutable Git objects, not a caller-written source PASS. The
    exact accepted application SHA anchors the commit and both file paths.
    """
    try:
        if not isinstance(objects,list) or len(objects)!=4:raise ValueError()
        measured={}
        for row in objects:
            if set(row)!={'oid','kind','body_base64'} or row['kind'] not in {'commit','tree'}:raise ValueError()
            if not isinstance(row['body_base64'],str) or len(row['body_base64'])>87384:raise ValueError()
            body=base64.b64decode(row['body_base64'],validate=True)
            if len(body)>65536:raise ValueError()
            oid=hashlib.sha1(row['kind'].encode()+b' '+str(len(body)).encode()+b'\0'+body).hexdigest()
            if oid!=row['oid'] or oid in measured:raise ValueError()
            measured[oid]=(row['kind'],body)
        kind,commit=measured[sha]
        if kind!='commit':raise ValueError()
        first=commit.split(b'\n',1)[0]
        if not re.fullmatch(b'tree [0-9a-f]{40}',first):raise ValueError()
        def lookup(tree,name):
            kind,body=measured[tree]
            if kind!='tree':raise ValueError()
            found=None;names=set();offset=0
            while offset<len(body):
                end=body.index(b'\0',offset);mode,entry=body[offset:end].split(b' ',1)
                raw=body[end+1:end+21]
                if len(raw)!=20 or entry in names or not entry or b'/' in entry or entry in (b'.',b'..'):raise ValueError()
                names.add(entry);offset=end+21
                if entry==name.encode():found=(mode,raw.hex())
            if found is None:raise ValueError()
            return found
        root=first[5:].decode();mode,web=lookup(root,'web')
        if mode!=b'40000':raise ValueError()
        mode,main=lookup(web,'docker-compose.yml')
        if mode!=b'100644':raise ValueError()
        mode,precutover=lookup(web,'precutover')
        if mode!=b'40000':raise ValueError()
        mode,client=lookup(precutover,'docker-compose.supabase-client.yml')
        if mode!=b'100644' or set(measured)!={sha,root,web,precutover}:raise ValueError()
        return {'web/docker-compose.yml':main,'web/precutover/docker-compose.supabase-client.yml':client}
    except (ValueError,KeyError,TypeError,UnicodeError):
        raise RuntimeError('completed_model_application_objects_invalid') from None


def candidate_release_root(actor, *, read_only):
    """Render accepted application files without creating a preflight worktree."""
    sha=actor.contract['candidate']['source_sha']
    root=actor.package/'source' if read_only else actor.ops.state_root/'releases'/sha
    objects=getattr(actor,'document',{}).get('application_source_objects')
    bindings=accepted_compose_blobs(sha,objects) if objects is not None else None
    # The frozen controller package may contain different deployment code, but
    # these application Compose inputs must be the accepted application's exact
    # Git blobs. No checkout, grant or Docker mutation is required to prove it.
    for relative in ('web/docker-compose.yml','web/precutover/docker-compose.supabase-client.yml'):
        path=root/relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('completed_model_application_input_missing')
        content=path.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        expected=bindings[relative] if read_only and bindings is not None else actor.ops.root_git(
            'completed_model_application_blob','rev-parse',f'{sha}:{relative}',cwd=actor.ops.repo).stdout
        if bindings is not None and expected!=bindings[relative]:
            raise RuntimeError('completed_model_application_staged_object_changed')
        if blob!=expected:
            raise RuntimeError('completed_model_application_input_changed')
    return root


@contextmanager
def measured_environment(paths,configuration):
    values={}
    load_environment_file(readonly_configuration(Path(paths),private=False),environ=values,require_private=False)
    load_environment_file(readonly_configuration(Path(configuration),private=True),environ=values)
    forbidden={'PATH','HOME','BASH_ENV','ENV','SHELL','CREDENTIALS_DIRECTORY'}
    if any(k.startswith(('LD_','PYTHON','DOCKER_','GIT_')) or k in forbidden for k in values):
        raise RuntimeError('completed_model_loader_environment_invalid')
    previous=dict(os.environ)
    credentials=previous.get('CREDENTIALS_DIRECTORY')
    try:
        os.environ.clear()
        os.environ.update({'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',**values})
        if credentials is not None:os.environ['CREDENTIALS_DIRECTORY']=credentials
        yield
    finally:
        os.environ.clear();os.environ.update(previous)


def render_candidate_model(actor, *, read_only=False):
    def guard():
        if read_only:
            measured,_=actor.measure()
            if os.geteuid()!=0 or measured!=actor.document:
                raise RuntimeError('completed_model_preparation_source_changed')
            from deployment.lib.completed_normal_boot_actor import verify_live_configuration
            verify_live_configuration(actor.document)
        else:actor.guard()
    guard()
    source=actor.package/'source'
    path=source/'web/deployment/bin/madar-release-deploy'
    loader=importlib.machinery.SourceFileLoader('deployment.completed_normal_model_renderer',str(path))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader))
    loader.exec_module(module)
    guard()
    contract=actor.contract;sha=contract['candidate']['source_sha'];slot=contract['candidate']['slot']
    selected=profile(actor.contract)
    compatibility=module.Compatibility.load(source/'web/deployment/releases'/selected.metadata)
    if ((compatibility.schema_min,compatibility.schema_max,compatibility.target_schema)!=(selected.source,selected.target,selected.target)
            or compatibility.excluded_schemas!=selected.excluded):
        raise RuntimeError('completed_model_loader_schema_contract_changed')
    cfg=actor.document['application_artifacts']
    images={key:cfg[key] for key in ('backend','frontend','worker','build_timestamp')}
    operations=module.DockerGitOperations(actor.ops.repo,actor.ops.state_root,Path('/etc/madar/production.env'),compatibility,metadata_filename=selected.metadata)
    operations.release_root=candidate_release_root(actor,read_only=read_only)
    operations.completed_normal_admission=contract
    if read_only:operations.read_only_model_contract=contract
    operations.schema_version=actor.native
    captured=[]
    def render(args,*,cwd=None,env=None,**kwargs):
        if args[:2]!=['docker','compose'] or args[-3:]!=['config','--format','json']:
            raise RuntimeError('completed_model_loader_mutation_denied')
        result=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError('completed_model_loader_config_failed')
        try:captured.append(json.loads(result.stdout))
        except (ValueError,TypeError):raise RuntimeError('completed_model_loader_output_invalid') from None
        return result.stdout
    operations.run=render
    with measured_environment(actor.ops.contract_path,operations.env_file):
        operations._compose(sha,slot,images,'config','--format','json',workers_active=True)
    guard()
    if len(captured)!=1:raise RuntimeError('completed_model_loader_inventory_invalid')
    return captured[0]
