#!/usr/bin/env python3
"""Fresh fixed PhaseVII synthetic150 acceptance; INSPECT is non-mutating.

Reuse the150 application/worker/restore probes, with an independent namespace
and pinned-template configuration. No production coordinator or source-stack
stop/resume operation is exposed. Existing attempts cannot be adopted/replayed.
"""
import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import schema150_acceptance as acceptance
import schema150_restore_configuration as configuration

manage, smoke, previous = acceptance.manage, acceptance.smoke, acceptance.previous
PROJECT = 'madar-schema150-phase7-20261018'
OWNER = 'schema150-phase7-20261018'
MARKER = 'madar-schema150-phase7-synthetic'
PORTS = {'18080':'23080', '18443':'23443', '18081':'23081'}
REFERENCE_PORTS = {'23080':'22080', '23443':'22443', '23081':'22081'}


def require_source(source):
    environment = {'PATH':os.defpath, 'HOME':str(Path.home())}
    def git(*arguments):
        value = subprocess.run(['git','-C',str(manage.REPOSITORY),*arguments],
            env=environment, capture_output=True, timeout=15)
        if value.returncode: raise RuntimeError('phase7_acceptance_source_unavailable')
        return value.stdout.decode().strip()
    if git('rev-parse','HEAD') != source or git('status','--porcelain','--untracked-files=normal'):
        raise RuntimeError('phase7_acceptance_clean_exact_source_required')


def require_ports_free():
    required = {int(value) for value in PORTS.values()}
    for name in ('/proc/net/tcp','/proc/net/tcp6'):
        for raw in Path(name).read_text().splitlines()[1:]:
            row = raw.split()
            if row[3] == '0A' and int(row[1].rsplit(':',1)[1],16) in required:
                raise RuntimeError('phase7_acceptance_port_already_owned')


def require_resources_absent():
    if manage.docker('ps','-aq','--filter','label=com.docker.compose.project='+PROJECT).strip():
        raise RuntimeError('phase7_acceptance_existing_project_resources')
    for kind in ('network','volume'):
        if manage.docker(kind,'ls','--filter','name='+PROJECT,'--format','{{.Name}}').strip():
            raise RuntimeError('phase7_acceptance_existing_project_resources')


def validate_plan(plan, runtime, source, images, timestamp):
    """Reapply the retained exact validator using only fixed port translation."""
    normalized = copy.deepcopy(plan)
    services = normalized.get('services', {})
    public = {'auth':{'API_EXTERNAL_URL':'http://127.0.0.1:23081/auth/v1',
        'GOTRUE_SITE_URL':'http://127.0.0.1:23080','GOTRUE_JWT_ISSUER':'http://127.0.0.1:23081/auth/v1',
        'GOTRUE_URI_ALLOW_LIST':'http://127.0.0.1:23080/**'},
        'storage':{'STORAGE_PUBLIC_URL':'http://127.0.0.1:23081'}}
    for name in ('backend','notification-worker','deletion-worker'):
        public[name]={'FRONTEND_URLS':'http://127.0.0.1:23080,https://127.0.0.1:23443'}
    if any(services.get(name,{}).get('environment',{}).get(key) != value
           for name,fields in public.items() for key,value in fields.items()):
        raise RuntimeError('phase7_acceptance_unapproved_public_endpoint')
    for row in services.values():
        for port in row.get('ports', []):
            published = str(port.get('published'))
            if published not in REFERENCE_PORTS:
                raise RuntimeError('phase7_acceptance_unapproved_port')
            port['published'] = REFERENCE_PORTS[published]
        for key, value in (row.get('environment') or {}).items():
            if isinstance(value,str):
                for current, reference in REFERENCE_PORTS.items():
                    value = value.replace('127.0.0.1:'+current, '127.0.0.1:'+reference)
                row['environment'][key] = value
    configuration.validate(normalized, runtime, source, images, PROJECT, OWNER, timestamp)


def compose(*args, timeout=180):
    """Consume captured resolved bytes; never reopen mutable Compose/env input."""
    arguments = list(args)
    while '--file' in arguments:
        index = arguments.index('--file')
        if index + 1 == len(arguments) or arguments[index+1] != str(manage.RUNTIME/'acceptance-compose.json'):
            raise RuntimeError('phase7_acceptance_compose_override')
        del arguments[index:index+2]
    forbidden = {'--file','--env-file','--project-name','--project-directory','--profile'}
    if any(value.split('=',1)[0] in forbidden or
           (not value.startswith('--') and value.startswith(('-f','-p'))) for value in arguments):
        raise RuntimeError('phase7_acceptance_compose_override')
    manage.state()
    body = configuration.regular(manage.RUNTIME/'verified-compose.json')
    receipt = json.loads(configuration.regular(manage.RUNTIME/'configuration-receipt.json'))
    if hashlib.sha256(body).hexdigest() != receipt['sha256']:
        raise RuntimeError('phase7_acceptance_verified_configuration_changed')
    validate_plan(json.loads(body), manage.RUNTIME, receipt['source_sha'], receipt['images'], receipt['build_timestamp'])
    return manage.docker('compose','--project-name',PROJECT,'--file','-',*arguments,data=body,timeout=timeout)


def archive_origin():
    """Keep the published149 exact independent148 origin/archive contracts."""
    root = Path.home()/previous.SOURCE_PROJECT
    if (root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid()
            or root.stat().st_mode & 0o777 != 0o700):
        raise RuntimeError('phase7_acceptance_origin_owner_invalid')
    state = json.loads(previous.regular(root/'owner.json'))
    if (state.get('project') != previous.SOURCE_PROJECT
            or state.get('owner') != 'architecture-hardening-20261016'
            or state.get('marker') != 'madar-hardening-synthetic-148-independent'):
        raise RuntimeError('Unrecognized synthetic recovery archive owner')
    checkpoint = json.loads(previous.regular(root/'capture-checkpoint.json'))
    captured = {name:previous.regular(root/name) for name in ('roles.sql','database.dump','objects.tar')}
    if any(hashlib.sha256(data).hexdigest() != checkpoint['archive_sha256'][name] for name,data in captured.items()):
        raise RuntimeError('Synthetic recovery archive digest mismatch')
    previous.archive_members(captured['objects.tar'])
    # Only credential values are retained. No source application/Compose/TLS
    # input is executed or copied into the target; all endpoints are generated.
    fields = {}
    for line in previous.regular(root/'compose.env').decode().splitlines():
        key, separator, value = line.partition('=')
        if not separator or key in fields: raise RuntimeError('phase7_acceptance_origin_credentials_invalid')
        fields[key] = value
    credentials = {key:fields.get(key,'') for key in ('DATABASE_PASSWORD','JWT_SECRET')}
    if any(not re.fullmatch('[0-9a-f]{64}', value) for value in credentials.values()):
        raise RuntimeError('phase7_acceptance_origin_credentials_invalid')
    return captured, checkpoint, credentials


def prepare(runtime, directory, source, images, receipt, snapshots):
    if runtime != Path.home()/PROJECT or runtime.exists() or runtime.is_symlink():
        raise RuntimeError('phase7_acceptance_existing_or_ambiguous_target')
    if set(snapshots) != {147,148,149,150} or not all(isinstance(value,bytes) for value in snapshots.values()):
        raise RuntimeError('Captured schema150 chain is required')
    if hashlib.sha256(snapshots[149]).hexdigest() != previous.MIGRATION_SHA:
        raise RuntimeError('Published migration149 bytes do not match exact immutable contract')
    if shutil.disk_usage(Path.home()).free < 8*1024**3:
        raise RuntimeError('phase7_acceptance_disk_headroom')
    memory = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    if memory < 2200*1024: raise RuntimeError('phase7_acceptance_memory_headroom')
    require_ports_free()
    captured, checkpoint, credentials = archive_origin()
    require_resources_absent()
    configuration.generate(runtime,source,images,receipt,credentials,PROJECT,OWNER)
    plan = json.loads(configuration.regular(runtime/'verified-compose.json'))
    for row in plan['services'].values():
        for port in row.get('ports',[]):
            reverse = {value:key for key,value in REFERENCE_PORTS.items()}
            port['published'] = reverse[str(port['published'])]
        for key,value in (row.get('environment') or {}).items():
            if isinstance(value,str):
                for current, reference in REFERENCE_PORTS.items():
                    value = value.replace('127.0.0.1:'+reference, '127.0.0.1:'+current)
                row['environment'][key] = value
    validate_plan(plan,runtime,source,images,receipt['build_timestamp'])
    body = json.dumps(plan,sort_keys=True).encode()
    manage.private_write('verified-compose.json',body.decode())
    manage.private_write('configuration-receipt.json',json.dumps({'source_sha':source,'images':images,
        'sha256':hashlib.sha256(body).hexdigest(),'template_sha256':configuration.TEMPLATES,
        'build_timestamp':receipt['build_timestamp']})+'\n')
    app = configuration.regular(runtime/'application.env').decode()
    for current, reference in REFERENCE_PORTS.items():
        app = app.replace('127.0.0.1:'+reference,'127.0.0.1:'+current)
    manage.private_write('application.env',app)
    for name,data in captured.items(): acceptance.restore.write_binary(runtime/name,data)
    manage.private_write('source-checkpoint.json',json.dumps(checkpoint)+'\n')
    manage.attest_resources()
    return captured, checkpoint


@contextmanager
def namespace(runtime):
    if runtime != Path.home()/PROJECT:
        raise RuntimeError('phase7_acceptance_namespace_invalid')
    changes = ((acceptance,{'PROJECT':PROJECT,'OWNER':OWNER,'MARKER':MARKER,'PORTS':dict(PORTS),
                           'target':target,'prepare':prepare}),
               (manage,{'PROJECT':PROJECT,'OWNER':OWNER,'MARKER':MARKER,'RUNTIME':runtime,'HERE':runtime,'compose':compose}),
               (smoke,{'PROVIDER':'http://127.0.0.1:23081','APPLICATION':'http://127.0.0.1:23080/api'}))
    saved = [(module,{name:getattr(module,name) for name in values}) for module,values in changes]
    try:
        for module,values in changes:
            for name,value in values.items(): setattr(module,name,value)
        yield
    finally:
        for module,values in reversed(saved):
            for name,value in values.items(): setattr(module,name,value)


@contextmanager
def target(runtime):
    # main150 otherwise installs its hardcoded2108x endpoints after149 target.
    if (runtime != Path.home()/PROJECT or manage.PROJECT != PROJECT or acceptance.PROJECT != PROJECT
            or smoke.PROVIDER != 'http://127.0.0.1:23081' or smoke.APPLICATION != 'http://127.0.0.1:23080/api'):
        raise RuntimeError('phase7_acceptance_namespace_invalid')
    yield


def main(mode,directory,source):
    if mode not in ('INSPECT','REHEARSE') or not re.fullmatch('[0-9a-f]{40}',source or ''):
        raise RuntimeError('Explicit mode and exact source commit required')
    runtime = Path.home()/PROJECT
    with namespace(runtime):
        manage.require_staging_host()
        require_source(source)
        report = acceptance.main(mode,directory,source)
        report.update({'phase':'VII','project':PROJECT,'ports':dict(PORTS),'production_authorized':False})
        if mode == 'REHEARSE':
            manage.private_write('phase7-schema150-acceptance.json',json.dumps(report,indent=2)+'\n')
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT')
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--source-sha',required=True)
    args = parser.parse_args()
    print(json.dumps(main(args.mode,args.artifacts,args.source_sha),sort_keys=True))
