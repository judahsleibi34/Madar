"""Candidate167 non-identifying restore suppression; never executes a restore.

The live floor must be outside restored data roots and protected independently
by the installed backup/restore control plane. No account identifiers are kept.
"""
import json
import os
from pathlib import Path
import stat
import tempfile


class RestoreBoundaryError(RuntimeError):
    pass


def floor_binding():
    from services.upload_config import get_data_upload_dir,get_private_charts_dir,get_public_uploads_dir
    configured=os.getenv('ACCOUNT_ERASURE_RESTORE_FLOOR_FILE','').strip()
    if not configured:raise RestoreBoundaryError('restore_floor_configuration_required')
    path=Path(configured)
    if not path.is_absolute() or path.is_symlink():raise RestoreBoundaryError('restore_floor_path_unsafe')
    for root in (get_data_upload_dir(),get_private_charts_dir(),get_public_uploads_dir()):
        if path.resolve().is_relative_to(root.resolve()):raise RestoreBoundaryError('restore_floor_must_be_independent')
    if path.parent.resolve()!=path.parent:raise RestoreBoundaryError('restore_floor_path_unsafe')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    info=path.parent.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode&0o077 or info.st_uid!=os.geteuid():raise RestoreBoundaryError('restore_floor_permissions_unsafe')
    return {'path':str(path),'device':info.st_dev,'parent_inode':info.st_ino}


def read_floor():
    path=Path(floor_binding()['path'])
    try:descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:return 0
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o077 or info.st_uid!=os.geteuid() or info.st_size>128:
            raise RestoreBoundaryError('restore_floor_identity_unsafe')
        value=json.loads(os.read(descriptor,128))
        if not isinstance(value,dict) or set(value)!={'version','epoch'} or value.get('version')!=1 or type(value.get('epoch')) is not int or value['epoch']<0:
            raise RestoreBoundaryError('restore_floor_invalid')
        return value['epoch']
    except (ValueError,TypeError):raise RestoreBoundaryError('restore_floor_invalid') from None
    finally:os.close(descriptor)


def publish_floor(epoch):
    """Caller holds protocol3's shared registration EX through finalization."""
    if type(epoch) is not int or epoch<=0:raise RestoreBoundaryError('restore_floor_invalid')
    path=Path(floor_binding()['path'])
    if read_floor()>epoch:raise RestoreBoundaryError('restore_floor_would_regress')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.restore-floor-',delete=False) as output:
            temporary=Path(output.name);output.write(json.dumps({'version':1,'epoch':epoch}).encode());output.flush();os.fsync(output.fileno())
        os.chmod(temporary,0o600);os.replace(temporary,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def capture_boundary(client):
    value=client.rpc('account_restore_boundary167',{}).execute().data
    if not isinstance(value,dict) or type(value.get('committed_epoch')) is not int or value['committed_epoch']<0 or type(value.get('erasure_in_progress')) is not bool:
        raise RestoreBoundaryError('restore_boundary_unavailable')
    if value['erasure_in_progress']:raise RestoreBoundaryError('restore_erasure_in_progress')
    floor=read_floor()
    if value['committed_epoch']!=floor:raise RestoreBoundaryError('restore_boundary_incomplete')
    return {'version':1,'epoch':floor}


def seal_snapshot(before,after,archive_sha256):
    if not isinstance(before,dict) or before!=after or before.get('version')!=1 or type(before.get('epoch')) is not int or before['epoch']<0:raise RestoreBoundaryError('snapshot_crossed_erasure')
    if not isinstance(archive_sha256,str) or len(archive_sha256)!=64 or any(c not in '0123456789abcdef' for c in archive_sha256):
        raise RestoreBoundaryError('snapshot_integrity_required')
    return {**before,'archive_sha256':archive_sha256}


def verify_restore(manifest,archive_sha256,client):
    """Admission evidence only, never permission to execute a restore.

    Caller must authenticate/seal the manifest with the existing protected
    archive contract; this check alone is not a signature or restore authority.
    """
    if manifest.get('archive_sha256')!=archive_sha256:raise RestoreBoundaryError('snapshot_integrity_mismatch')
    current=capture_boundary(client)
    seal_snapshot(current,current,archive_sha256)
    if manifest.get('version')!=1 or type(manifest.get('epoch')) is not int or manifest['epoch']!=current['epoch']:
        raise RestoreBoundaryError('restore_would_resurrect_erased_data')
    return {'suppression_verified':True,'restore_execution_authorized':False}
