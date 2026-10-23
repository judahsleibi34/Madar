"""Maintenance capture inside the existing ordinary backup/restore pipeline.

No CLI, SQL executor, issuer or alternate publication path. The concrete
provider adapter retains its existing authorization, locks and persistent fence.
Temporary role restrictions are never mistaken for recoverable original roles.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from deployment.lib.completed_normal_admission import digest, encoded
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.maintenance_backup_roles import capture_original_roles
from deployment.lib.schema150_provider_adapter import Schema150ProviderAdapter, private_json
from deployment.lib.schema150_object_inventory import archive_roots


def private_copy(source, destination):
    """Copy untrusted dump output into a NEW protected directory via dirfds."""
    from deployment.lib.schema150_object_inventory import _open_root, _signature, _mount_id
    destination.mkdir(mode=0o700)
    root=_open_root(str(source));mount=_mount_id(root);count=total=0
    def walk(descriptor,target,depth):
        nonlocal count,total
        if depth>32:raise RuntimeError('maintenance_backup_copy_depth')
        before=os.fstat(descriptor);names=sorted(os.listdir(descriptor))
        for name in names:
            count+=1
            if count>100000:raise RuntimeError('maintenance_backup_copy_entries')
            info=os.stat(name,dir_fd=descriptor,follow_symlinks=False)
            directory=stat.S_ISDIR(info.st_mode)
            if not directory and not (stat.S_ISREG(info.st_mode) and info.st_nlink==1):
                raise RuntimeError('maintenance_backup_copy_link_or_special')
            child=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|(os.O_DIRECTORY if directory else 0),dir_fd=descriptor)
            try:
                if _signature(info)!=_signature(os.fstat(child)) or _mount_id(child)!=mount:
                    raise RuntimeError('maintenance_backup_copy_changed')
                path=target/name
                if directory:path.mkdir(mode=0o700);walk(child,path,depth+1)
                else:
                    total+=info.st_size
                    if total>4*1024**3:raise RuntimeError('maintenance_backup_copy_capacity')
                    with path.open('xb') as output:
                        os.fchmod(output.fileno(),0o600);remaining=info.st_size
                        while remaining:
                            value=os.read(child,min(1024*1024,remaining))
                            if not value:raise RuntimeError('maintenance_backup_copy_changed')
                            output.write(value);remaining-=len(value)
                        if os.read(child,1):raise RuntimeError('maintenance_backup_copy_changed')
                        output.flush();os.fsync(output.fileno())
                if _signature(info)!=_signature(os.fstat(child)):
                    raise RuntimeError('maintenance_backup_copy_changed')
            finally:os.close(child)
        if names!=sorted(os.listdir(descriptor)) or _signature(before)!=_signature(os.fstat(descriptor)):
            raise RuntimeError('maintenance_backup_copy_changed')
        fd=os.open(target,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    try:walk(root,destination,0)
    finally:os.close(root)


def require_context(context):
    adapter=context.provider_adapter
    if (type(adapter) is not Schema150ProviderAdapter or adapter.contract!=context.contract
            or adapter.root!=context.root or digest(context.contract)!=adapter.binding['context_sha256']):
        raise RuntimeError('maintenance_backup_concrete_context_required')
    context.validate(context.plan, context.root, context.package)
    context.guard()
    return adapter


def readonly_query(adapter, body):
    return adapter._sql("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; "
        "SET LOCAL search_path=pg_catalog; SET LOCAL TIME ZONE 'UTC'; "
        "SET LOCAL statement_timeout='60s';\n"+body+'\nCOMMIT;')


def recovery_context(context):
    return {'origin_source_sha':context.contract['source_roles']['application_sha'],
        'origin_images':context.contract['origin']['images'],'candidate_images':context.contract['candidate']['images'],
        'database_image':context.contract['database']['image'],
        'migration_manifest_sha256':context.contract['migration_manifest_sha256'],
        'controller_tree_sha256':context.contract['candidate']['controller_tree_sha256'],
        'configuration_sha256':context.document['live_configuration_sha256'],'configuration_escrow_required':True}


def capture(context, env, descriptor, identity):
    """Use the measured ordinary dump/file helper with providers stopped.

    No live HTTP probe is attempted after provider fencing. The root caller has
    already authenticated source/images and positive provider identity. Data is
    captured using the existing independently sealed direct-database lease.
    This function produces no backup/replica success or write grant.
    """
    from deployment.lib.active_recovery_backup import checked
    from scripts import backup_support
    adapter=require_context(context)
    original=capture_original_roles(adapter)
    original.verify(adapter.binding, expected_schema=context.schema)
    record=private_json(context.root/'provider-journal'/'0000.json')['payload']['preimage']
    snapshot=json.loads(readonly_query(adapter,backup_support.ROLE_SNAPSHOT_SQL))
    snapshot['roles']=record['roles']['original']['roles']
    snapshot['memberships']=record['roles']['original']['memberships']
    bootstrap=readonly_query(adapter,'SELECT rolname FROM pg_authid WHERE oid=10;').strip()
    before=backup_support.database_fingerprint(lambda sql:readonly_query(adapter,sql))
    capture_env=dict(env, MADAR_PROVIDER_BACKUP_REQUIRED='false', MADAR_RELEASE_SHA=context.plan.source_sha,
        MADAR_BUILD_TIMESTAMP=env.get('MADAR_BUILD_TIMESTAMP','unknown'), MADAR_BACKUP_CREATE_DATABASE='true')
    checked(['/bin/bash','/usr/local/lib/madar/backup_madar.sh'],env=capture_env,user=identity.pw_uid,pass_fds=(descriptor,))
    scope=Path(env['MADAR_BACKUP_DIR'])
    outputs=list(scope.glob('madar-*'))
    if len(outputs)!=1 or outputs[0].is_symlink() or not outputs[0].is_dir():
        raise RuntimeError('maintenance_backup_output_invalid')
    # Never write privileged role material through a runtime-owned ancestor.
    # Interrupted copies stay private and cannot be silently overwritten.
    from deployment.lib.provider_recovery_runtime import protected
    protected(context.root/'admission.json')
    quarantine=context.root/(context.stage+'-maintenance-capture');quarantine.mkdir(mode=0o700)
    backup=quarantine/outputs[0].name
    private_copy(outputs[0],backup)
    backup_support.verify(backup)
    # Reuse the exact fenced checkpoint already owned by the provider journal.
    checkpoint=private_json(context.root/'provider-object-preservation.json')
    if checkpoint['binding']!=adapter.binding:raise RuntimeError('maintenance_backup_object_binding_changed')
    result=seal_capture(backup,binding=adapter.binding,stage=context.stage,original_roles=original.sql_bytes,
        roles_snapshot=snapshot,bootstrap_role=bootstrap,roots=adapter.inventory['object_roots'],
        previous=checkpoint['measurement'],database_fingerprint=before,recovery=recovery_context(context))
    require_context(context)
    if backup_support.database_fingerprint(lambda sql:readonly_query(adapter,sql))!=before:
        raise RuntimeError('maintenance_backup_database_changed')
    exclusive(context.root/(context.stage+'-maintenance-backup-input.json'),encoded({'version':1,
        'context_sha256':context.context,'scope':context.scope,'stage':context.stage,
        'backup_id':backup.name,'manifest_sha256':result}))
    return {'path':str(backup),'manifest_sha256':result}


def seal_capture(backup, *, binding, stage, original_roles, roles_snapshot, bootstrap_role,
                 roots, previous, database_fingerprint, recovery):
    """Encode recovery material in a private unpublished ordinary backup.

    This serialization helper alone proves no authority or source identity.
    capture() authenticates the real actor before and after calling it; the
    protected consumer pins its resulting digest independently before restore.
    """
    from scripts import backup_support
    from deployment.lib.schema150_provider_lifecycle import validate_binding
    validate_binding(binding)
    if stage not in ('pre-migration','post-migration'):raise RuntimeError('maintenance_backup_stage_invalid')
    schema=binding['source_schema' if stage=='pre-migration' else 'target_schema']
    manifest=backup_support.verify(backup)
    if manifest.get('maintenance_backup') is not None or (backup/'maintenance').exists():
        raise RuntimeError('maintenance_backup_extension_already_exists')
    if (int(manifest['database']['schema_version'])!=schema or manifest['release']['git_sha']!=binding['source_sha']
            or manifest.get('recovery',{}).get('provider_objects_required') is not False):
        raise RuntimeError('maintenance_backup_archive_binding_invalid')
    extension=backup/'maintenance';extension.mkdir(mode=0o700)
    exclusive(extension/'roles.sql',original_roles)
    exclusive(extension/'roles-snapshot.json',encoded(roles_snapshot))
    objects=archive_roots(roots,extension/'objects.tar.gz',previous=previous)
    metadata={'version':1,'binding':binding,'stage':stage,'schema':schema,
        'bootstrap_role':bootstrap_role,'roles_sha256':hashlib.sha256(original_roles).hexdigest(),
        'roles_snapshot_sha256':backup_support.digest(extension/'roles-snapshot.json'),
        'objects_sha256':backup_support.digest(extension/'objects.tar.gz'),'objects_measurement':objects,
        'database_fingerprint':database_fingerprint,'recovery':recovery,'authority_issued':False}
    exclusive(extension/'manifest.json',encoded(metadata))
    # This private scoped output has not been published. Replace its manifests
    # before restore/replication and before ordinary LATEST/receipt publication.
    manifest['maintenance_backup']='maintenance/manifest.json'
    manifest['database']['create_database']=True
    backup_support.atomic_text(backup/'manifest.json',json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    sums=backup_support.inventory(backup);sums.pop('SHA256SUMS')
    def checksum_line(name, checksum):
        escaped='\\' in name or '\n' in name
        name=name.replace('\\','\\\\').replace('\n','\\n')
        return ('\\' if escaped else '')+checksum+'  '+name+'\n'
    backup_support.atomic_text(backup/'SHA256SUMS',''.join(checksum_line(name,value) for name,value in sorted(sums.items())))
    backup_support.verify(backup)
    return backup_support.digest(extension/'manifest.json')


def expected_manifest(context, backup):
    """Independently bind the captured material to this still-fenced operation."""
    from scripts import backup_support
    adapter=require_context(context)
    receipt=private_json(context.root/(context.stage+'-maintenance-backup-input.json'))
    expected={'version':1,'context_sha256':context.context,'scope':context.scope,'stage':context.stage,
        'backup_id':backup.name,'manifest_sha256':receipt.get('manifest_sha256')}
    if receipt!=expected or backup!=context.root/(context.stage+'-maintenance-capture')/backup.name:
        raise RuntimeError('maintenance_backup_private_capture_changed')
    value=backup_support.verify_maintenance(backup,expected_sha256=receipt['manifest_sha256'])
    if (value['binding']!=adapter.binding or value['stage']!=context.stage or value['schema']!=context.schema
            or value['recovery']!=recovery_context(context)
            or value['database_fingerprint']!=backup_support.database_fingerprint(lambda sql:readonly_query(adapter,sql))):
        raise RuntimeError('maintenance_backup_live_binding_changed')
    original=capture_original_roles(adapter)
    if hashlib.sha256(original.sql_bytes).hexdigest()!=value['roles_sha256']:
        raise RuntimeError('maintenance_backup_original_roles_changed')
    objects=adapter._object_preservation(adapter.binding,
        private_json(context.root/'provider-journal'/'0000.json')['payload']['preimage'])
    if value['objects_measurement']!=objects:raise RuntimeError('maintenance_backup_object_preimage_changed')
    return backup_support.digest(backup/'maintenance/manifest.json')


def release_ownership(context, backup, identity):
    """Hand verified bytes to ordinary backup ownership behind a private parent.

    The containing admission directory remains root0700 until atomic publication.
    Never recursively chown beneath the runtime-owned public backup directory.
    """
    expected_manifest(context,backup)
    for parent,dirs,files in os.walk(backup,followlinks=False):
        for name in files:
            path=Path(parent)/name;info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                raise RuntimeError('maintenance_backup_publication_changed')
            os.chown(path,identity.pw_uid,identity.pw_gid,follow_symlinks=False)
        for name in dirs:
            path=Path(parent)/name
            if not stat.S_ISDIR(path.lstat().st_mode):raise RuntimeError('maintenance_backup_publication_changed')
            os.chown(path,identity.pw_uid,identity.pw_gid,follow_symlinks=False)
    os.chown(backup,identity.pw_uid,identity.pw_gid,follow_symlinks=False)
