"""Authenticate fresh CI image archives; never load images or issue authority."""
from contextlib import contextmanager,ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
import zipfile

REPOSITORY='judahsleibi34/Madar'
WORKFLOW='.github/workflows/schema148-artifacts.yml'
INPUTS=('web/backend/Dockerfile','web/backend/requirements.txt','web/backend/constraints.txt',
        'web/frontend/Dockerfile','web/frontend/package.json','web/frontend/package-lock.json')


def archive_runtime_configuration(path,build_host_id):
    """Bind this supported OCI archive to the containerd runtime manifest ID.

    The hosted classic builder's .Id is the config digest; the target native
    engine's .Id is the manifest digest. Never substitute one after acceptance.
    This producer-side inspection extracts no files and retains bounded metadata.
    """
    metadata={};total=0
    class BoundedImage:
        remaining=4*1024**3
        def __init__(self,stream):self.stream=stream
        def read(self,count):
            value=self.stream.read(min(count,self.remaining+1))
            self.remaining-=len(value)
            if self.remaining<0:raise RuntimeError('schema148_image_archive_expansion_limit')
            return value
    with ExitStack() as stack:
        source=path if hasattr(path,'read') else stack.enter_context(open(path,'rb'))
        decoded=stack.enter_context(gzip.GzipFile(fileobj=source,mode='rb'))
        archive=stack.enter_context(tarfile.open(fileobj=BoundedImage(decoded),mode='r|'))
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
    try:configuration=json.loads(metadata[docker[0]['Config']])
    except (ValueError,TypeError):raise RuntimeError('schema148_image_archive_configuration_invalid') from None
    if not isinstance(configuration,dict):raise RuntimeError('schema148_image_archive_configuration_invalid')
    return identity,configuration


def archive_runtime_identity(path,build_host_id):
    return archive_runtime_configuration(path,build_host_id)[0]


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


@contextmanager
def authenticated_bytes(path,expected_digest,*,max_bytes=6*1024**3):
    """Parse exactly the authenticated bytes, even if an operator changes the path.

    The source is operator-owned read-only input, not a protected receipt. A
    private unnamed bounded snapshot binds hashing and ZIP consumption without
    assuming that either its directory entry or its open inode stays immutable.
    Callers importing archive contents must use this same boundary as well.
    """
    if type(max_bytes) is not int or not 0<max_bytes<=6*1024**3:
        raise RuntimeError('schema148_ci_archive_limit_invalid')
    if not re.fullmatch('sha256:[0-9a-f]{64}',str(expected_digest)):
        raise RuntimeError('schema148_ci_archive_digest_invalid')
    path=Path(path)
    try:
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except OSError:
        raise RuntimeError('schema148_ci_archive_invalid') from None
    with os.fdopen(descriptor,'rb') as source:
        measured=os.fstat(source.fileno())
        if not stat.S_ISREG(measured.st_mode) or not 0<measured.st_size<=max_bytes:
            raise RuntimeError('schema148_ci_archive_invalid')
        with tempfile.TemporaryFile(mode='w+b') as frozen:
            value=hashlib.sha256();remaining=measured.st_size
            while remaining:
                chunk=source.read(min(1024*1024,remaining))
                if not chunk:raise RuntimeError('schema148_ci_archive_changed')
                frozen.write(chunk);value.update(chunk);remaining-=len(chunk)
            if source.read(1) or 'sha256:'+value.hexdigest()!=expected_digest:
                raise RuntimeError('schema148_ci_archive_digest_changed')
            frozen.seek(0)
            yield frozen


@contextmanager
def authenticated_archive(path,expected_digest,*,max_bytes=6*1024**3):
    with authenticated_bytes(path,expected_digest,max_bytes=max_bytes) as frozen:
        with zipfile.ZipFile(frozen) as archive:yield archive


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
    with authenticated_archive(path,artifact['digest']) as archive:
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


def provenance_inputs(actor,binding):
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
    return artifact,run,inputs


def capture_candidate_archive(path,destination,artifact,run,*,source_sha,images,expected_inputs):
    """Retain the authenticated snapshot and inspect its actual OCI configs.

    This bounded file codec has no operational authority. The existing root
    coordinator selects a NEW protected destination after fresh admission.
    An interrupted directory is retained and cannot be adopted or overwritten.
    """
    destination=Path(destination);destination.mkdir(mode=0o700)
    target=destination/'archive.zip'
    with authenticated_bytes(path,artifact['digest']) as frozen:
        with target.open('xb') as output:
            os.fchmod(output.fileno(),0o600)
            for chunk in iter(lambda:frozen.read(1024*1024),b''):output.write(chunk)
            output.flush();os.fsync(output.fileno())
    receipt=verify_archive(target,artifact,run,source_sha=source_sha,images=images,expected_inputs=expected_inputs)
    timestamp=receipt.get('build_timestamp')
    if not isinstance(timestamp,str) or not 1<=len(timestamp)<=80:
        raise RuntimeError('schema148_ci_build_timestamp_invalid')
    with authenticated_archive(target,artifact['digest']) as archive:
        for role in ('backend','frontend'):
            with tempfile.TemporaryFile(mode='w+b') as inner:
                with archive.open(role+'.tar.gz') as source:
                    for chunk in iter(lambda:source.read(1024*1024),b''):inner.write(chunk)
                inner.seek(0)
                identity,configuration=archive_runtime_configuration(inner,receipt['build_host_image_ids'][role])
                config=configuration.get('config',{})
                if not isinstance(config,dict):raise RuntimeError('schema148_ci_captured_image_incompatible')
                labels=config.get('Labels',{})
                if (identity!=images[role] or not isinstance(labels,dict)
                        or labels.get('org.opencontainers.image.revision')!=source_sha
                        or labels.get('com.madar.release.sha')!=source_sha
                        or labels.get('com.madar.release.built_at')!=timestamp
                        or labels.get('com.madar.build.mode')!='fresh-locked-ci'
                        or labels.get('com.madar.staging.build_mode')
                        or role=='frontend' and labels.get('com.madar.frontend.api_origin')!='/api'):
                    raise RuntimeError('schema148_ci_captured_image_incompatible')
    descriptor=os.open(destination,os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    return receipt


def candidate_seal_binding(actor,binding,artifact,run,receipt):
    from deployment.lib.completed_normal_admission import digest as contract_digest
    return {'version':1,'context_sha256':contract_digest(actor.contract),
        'plan_sha256':actor.contract['plan_sha256'],'source_sha':actor.contract['candidate']['source_sha'],
        'controller_sha':actor.contract['candidate']['controller_sha'],
        'database':actor.contract['database'],'images':actor.contract['candidate']['images'],
        'migration_manifest_sha256':actor.contract['migration_manifest_sha256'],
        'provenance':binding,'artifact_id':artifact['id'],'archive_sha256':artifact['digest'],
        'run_id':run['id'],'run_attempt':run['run_attempt'],
        'receipt_sha256':hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'authority_issued':False}


def seal_candidate_provenance(actor,binding):
    """Existing coordinator capture, before prepare and while both locks hold.

    No image import, container creation, proxy activation or credential issuer.
    The source guard, existing fresh authority and fixed admission parent remain
    mandatory. This does not register schema150 or a generic release executor.
    """
    from deployment.lib.completed_normal_admission import ADMISSIONS,digest as contract_digest,require_fresh_authorization,encoded
    from deployment.lib.provider_recovery_runtime import protected,readonly_configuration
    from deployment.lib.emergency_routing_repair import exclusive
    if os.geteuid()!=0 or actor.root!=ADMISSIONS/contract_digest(actor.contract):
        raise RuntimeError('schema148_ci_protected_capture_required')
    actor.guard();require_fresh_authorization(actor.contract)
    protected(actor.root/'admission.json')
    artifact,run,inputs=provenance_inputs(actor,binding)
    archive=readonly_configuration(Path(binding['archive']),private=True)
    receipt=capture_candidate_archive(archive,actor.root/'candidate-artifacts',artifact,run,
        source_sha=actor.contract['candidate']['source_sha'],images=actor.contract['candidate']['images'],expected_inputs=inputs)
    if receipt['build_timestamp']!=actor.document['application_artifacts']['build_timestamp']:
        raise RuntimeError('schema148_ci_candidate_timestamp_changed')
    actor.guard();require_fresh_authorization(actor.contract)
    exclusive(actor.root/'candidate-artifact-seal.json',encoded(candidate_seal_binding(actor,binding,artifact,run,receipt)))
    return receipt


def verify_provenance(actor,binding):
    from deployment.lib.provider_recovery_runtime import readonly_configuration,protected
    artifact,run,inputs=provenance_inputs(actor,binding)
    seal=actor.root/'candidate-artifact-seal.json'
    captured=actor.root/'candidate-artifacts'
    if seal.exists() or seal.is_symlink() or captured.exists() or captured.is_symlink():
        # Never fall back to mutable operator input after capture was attempted.
        record=json.loads(protected(seal,private=True).read_bytes())
        archive=protected(captured/'archive.zip',private=True)
        receipt=verify_archive(archive,artifact,run,source_sha=actor.contract['candidate']['source_sha'],
            images=actor.contract['candidate']['images'],expected_inputs=inputs)
        if record!=candidate_seal_binding(actor,binding,artifact,run,receipt):
            raise RuntimeError('schema148_ci_candidate_seal_changed')
        return receipt
    archive=readonly_configuration(Path(binding['archive']),private=True)
    return verify_archive(archive,artifact,run,source_sha=actor.contract['candidate']['source_sha'],
        images=actor.contract['candidate']['images'],expected_inputs=inputs)
