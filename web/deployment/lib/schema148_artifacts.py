"""Authenticate fresh CI image archives; never load images or issue authority."""
import hashlib
import json
from pathlib import Path
import re
import stat
import tarfile
import zipfile

REPOSITORY='judahsleibi34/Madar'
WORKFLOW='.github/workflows/schema148-artifacts.yml'
INPUTS=('web/backend/Dockerfile','web/backend/requirements.txt','web/backend/constraints.txt',
        'web/frontend/Dockerfile','web/frontend/package.json','web/frontend/package-lock.json')


def archive_runtime_identity(path,build_host_id):
    """Bind this supported OCI archive to the containerd runtime manifest ID.

    The hosted classic builder's .Id is the config digest; the target native
    engine's .Id is the manifest digest. Never substitute one after acceptance.
    This producer-side inspection extracts no files and retains bounded metadata.
    """
    metadata={};total=0
    with tarfile.open(path,mode='r|gz') as archive:
        for index,member in enumerate(archive):
            if index>1000:raise RuntimeError('schema148_image_archive_inventory_invalid')
            if not member.isfile() or member.size>1024*1024:continue
            total+=member.size
            if total>8*1024*1024 or member.name in metadata:raise RuntimeError('schema148_image_archive_metadata_invalid')
            metadata[member.name]=archive.extractfile(member).read()
    try:
        index=json.loads(metadata['index.json']);docker=json.loads(metadata['manifest.json'])
        manifests=index['manifests']
        if len(manifests)!=1 or len(docker)!=1:raise ValueError()
        identity=manifests[0]['digest']
        if not re.fullmatch('sha256:[0-9a-f]{64}',identity):raise ValueError()
        raw=metadata['blobs/sha256/'+identity.split(':')[1]]
        manifest=json.loads(raw)
        config=manifest['config']['digest']
        if ('sha256:'+hashlib.sha256(raw).hexdigest()!=identity or build_host_id not in {config,identity}
                or docker[0]['Config']!='blobs/sha256/'+config.split(':')[1]
                or 'sha256:'+hashlib.sha256(metadata[docker[0]['Config']]).hexdigest()!=config):raise ValueError()
    except (KeyError,TypeError,ValueError,IndexError):
        raise RuntimeError('schema148_image_archive_identity_invalid') from None
    return identity


def verify_required_ci(records,source_sha):
    """Require the latest exact-application-source runs, separately from build CI."""
    required={'backend-check.yml':'Backend Check','frontend-check.yml':'Frontend Check'}
    if set(records)!=set(required):raise RuntimeError('schema148_application_ci_missing')
    for workflow,name in required.items():
        rows=records[workflow].get('workflow_runs',[])
        if not rows or any(type(row.get('id')) is not int for row in rows):
            raise RuntimeError('schema148_application_ci_missing')
        latest=max(rows,key=lambda row:row['id'])
        if (latest.get('head_sha')!=source_sha or latest.get('name')!=name
                or latest.get('path')!='.github/workflows/'+workflow
                or latest.get('repository',{}).get('full_name')!=REPOSITORY
                or latest.get('head_repository',{}).get('full_name')!=REPOSITORY
                or latest.get('status')!='completed' or latest.get('conclusion')!='success'):
            raise RuntimeError('schema148_application_ci_incomplete')


def digest(stream):
    value=hashlib.sha256()
    for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def verify_archive(path,artifact,run,*,source_sha,images,expected_inputs):
    if (not re.fullmatch('[0-9a-f]{40}',source_sha) or run.get('head_sha')!=source_sha
            or run.get('repository',{}).get('full_name')!=REPOSITORY
            or run.get('head_repository',{}).get('full_name')!=REPOSITORY
            or run.get('path')!=WORKFLOW or run.get('name')!='Schema148 Candidate Artifacts'
            or run.get('status')!='completed' or run.get('conclusion')!='success'
            or type(run.get('id')) is not int or type(run.get('run_attempt')) is not int
            or type(artifact.get('id')) is not int or artifact.get('expired') is not False
            or artifact.get('workflow_run',{}).get('id')!=run['id']
            or artifact.get('workflow_run',{}).get('head_sha')!=source_sha
            or artifact.get('name')!=f"schema148-candidate-{source_sha}-{run['id']}-{run['run_attempt']}"
            or not re.fullmatch('sha256:[0-9a-f]{64}',str(artifact.get('digest')))):
        raise RuntimeError('schema148_ci_artifact_identity_invalid')
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=6*1024**3:
        raise RuntimeError('schema148_ci_archive_invalid')
    with path.open('rb') as stream:
        if 'sha256:'+digest(stream)!=artifact['digest']:raise RuntimeError('schema148_ci_archive_digest_changed')
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        if (len(entries)!=3 or {item.filename for item in entries}!={'receipt.json','backend.tar.gz','frontend.tar.gz'}
                or any(item.is_dir() or stat.S_ISLNK(item.external_attr>>16) or item.file_size>3*1024**3 for item in entries)
                or archive.getinfo('receipt.json').file_size>65536):
            raise RuntimeError('schema148_ci_archive_inventory_invalid')
        receipt=json.loads(archive.read('receipt.json'))
        if images is None:images=receipt.get('images')
        if not isinstance(images,dict):raise RuntimeError('schema148_ci_image_identity_invalid')
        if (type(receipt.get('version')) is not int or receipt.get('version')!=1 or receipt.get('repository')!=REPOSITORY
                or receipt.get('source_sha')!=source_sha or receipt.get('build_mode')!='fresh-locked-ci'
                or receipt.get('runtime_identity')!='single-OCI-manifest-containerd'
                or not isinstance(receipt.get('build_host_image_ids'),dict)
                or set(receipt['build_host_image_ids'])!={'backend','frontend'}
                or any(not re.fullmatch('sha256:[0-9a-f]{64}',str(value)) for value in receipt['build_host_image_ids'].values())
                or receipt.get('images')!=images or set(images)!={'backend','frontend'}
                or any(not re.fullmatch('sha256:[0-9a-f]{64}',str(value)) for value in images.values())
                or receipt.get('inputs_sha256')!=expected_inputs or set(expected_inputs)!=set(INPUTS)
                or receipt.get('run_id')!=run['id'] or receipt.get('run_attempt')!=run['run_attempt']
                or receipt.get('production_authorized') is not False or set(receipt.get('archives',{}))!={'backend','frontend'}):
            raise RuntimeError('schema148_ci_receipt_invalid')
        for role in ('backend','frontend'):
            metadata=receipt['archives'][role]
            if metadata.get('file')!=role+'.tar.gz' or metadata.get('bytes')!=archive.getinfo(role+'.tar.gz').file_size:
                raise RuntimeError('schema148_ci_image_archive_invalid')
            with archive.open(role+'.tar.gz') as stream:
                if digest(stream)!=metadata.get('sha256'):raise RuntimeError('schema148_ci_image_archive_changed')
    return receipt


def verify_provenance(actor,binding):
    """API requery prevents a local PASS packet from authenticating itself."""
    from deployment.lib.provider_recovery_runtime import readonly_configuration,file_digest
    if (set(binding)!={'archive','artifact_id','run_id'} or any(type(binding[k]) is not int or binding[k]<=0 for k in ('artifact_id','run_id'))):
        raise RuntimeError('schema148_ci_provenance_binding_invalid')
    def api(endpoint):
        return json.loads(actor.ops.command('schema148_ci_provenance',[
            '/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','api','repos/'+REPOSITORY+'/actions/'+endpoint]).stdout)
    artifact=api('artifacts/'+str(binding['artifact_id']));run=api('runs/'+str(binding['run_id']))
    if artifact.get('id')!=binding['artifact_id'] or run.get('id')!=binding['run_id']:
        raise RuntimeError('schema148_ci_provenance_binding_changed')
    candidate=actor.contract['candidate']['source_sha']
    verify_required_ci({workflow:api('workflows/'+workflow+'/runs?head_sha='+candidate+'&per_page=100')
        for workflow in ('backend-check.yml','frontend-check.yml')},candidate)
    source=actor.package/'source'
    inputs={relative:file_digest(readonly_configuration(source/relative,private=True)) for relative in INPUTS}
    archive=readonly_configuration(Path(binding['archive']),private=True)
    return verify_archive(archive,artifact,run,source_sha=candidate,
                          images=actor.contract['candidate']['images'],expected_inputs=inputs)
