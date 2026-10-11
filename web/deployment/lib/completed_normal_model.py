"""Independently render the same frozen Compose builder used by staging.

The rendered model contains private environment values and never goes to logs
or an operator-writable PASS packet. Only Docker's config command is permitted.
"""
from contextlib import contextmanager
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess

from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery_runtime import readonly_configuration


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
    compatibility=module.Compatibility.load(source/'web/deployment/releases/release.json')
    if (compatibility.schema_min,compatibility.schema_max,compatibility.target_schema)!=(115,136,136):
        raise RuntimeError('completed_model_loader_schema_contract_changed')
    cfg=actor.document['application_artifacts']
    images={key:cfg[key] for key in ('backend','frontend','worker','build_timestamp')}
    operations=module.DockerGitOperations(actor.ops.repo,actor.ops.state_root,Path('/etc/madar/production.env'),compatibility)
    operations.release_root=actor.ops.state_root/sha
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
