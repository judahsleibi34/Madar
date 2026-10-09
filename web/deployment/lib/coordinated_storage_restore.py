"""Recover native Storage attributes from the exact restored database metadata.

Only new private quarantine files are changed. No original storage, checkpoint,
receipt or manifest is edited. Alternate versions must contain identical bytes;
unknown objects/attributes or divergent versions fail closed. A separate reader
compares every derived attribute and byte with the current restricted source.
"""
import os
from pathlib import Path
from deployment.lib.coordinated_checkpoint import relative,digest_file

ATTRIBUTES={'user.supabase.cache-control':'cacheControl','user.supabase.content-type':'mimetype'}


def checked_file(path,root):
    if not path.is_relative_to(root):raise RuntimeError('storage_restore_path_invalid')
    for part in (path,*path.parents):
        if part.is_symlink():raise RuntimeError('storage_restore_path_untrusted')
        if part==root:break
    if not path.is_file():raise RuntimeError('storage_restore_file_missing')
    return path


def recover_metadata(objects,restored_root,*,source_root=None):
    restored_root=Path(restored_root)
    if restored_root.is_symlink() or not restored_root.is_dir():raise RuntimeError('storage_restore_root_invalid')
    if source_root is not None:source_root=Path(source_root)
    selected={}
    for row in objects:
        bucket=relative(row['bucket']).as_posix();name=relative(row['name']).as_posix();version=relative(row['version']).as_posix()
        if '/' in bucket or '/' in version:raise RuntimeError('storage_restore_identity_invalid')
        base=restored_root/'stub/stub'/bucket/name
        current=checked_file(base/version,restored_root);current_digest=digest_file(current)
        attributes={key:row['metadata'].get(field) for key,field in ATTRIBUTES.items()}
        if any(not isinstance(value,str) or not value or len(value.encode())>4096 or '\r' in value or '\n' in value for value in attributes.values()):
            raise RuntimeError('storage_restore_metadata_invalid')
        for target in base.iterdir():
            target=checked_file(target,restored_root);key=target.relative_to(restored_root).as_posix()
            if key in selected or digest_file(target)!=current_digest:raise RuntimeError('storage_restore_version_diverged')
            selected[key]={attribute:value.encode() for attribute,value in attributes.items()}
    actual=set()
    for parent,dirs,files in os.walk(restored_root,followlinks=False):
        if any((Path(parent)/name).is_symlink() for name in dirs):raise RuntimeError('storage_restore_path_untrusted')
        actual.update((Path(parent)/name).relative_to(restored_root).as_posix() for name in files)
    if not selected or actual!=set(selected):raise RuntimeError('storage_restore_inventory_inexact')
    # Prove applicability before modifying even the new quarantine. Never infer
    # missing attribute values from a live source or overwrite preserved evidence.
    if source_root is not None:
        source_files={p.relative_to(source_root).as_posix() for p in source_root.rglob('*') if p.is_file()}
        if source_files!=actual:raise RuntimeError('storage_restore_source_inventory_changed')
        for key,attributes in selected.items():
            source=checked_file(source_root/key,source_root)
            if (digest_file(source)!=digest_file(restored_root/key) or set(os.listxattr(source))!=set(attributes)
                    or any(os.getxattr(source,attribute)!=value for attribute,value in attributes.items())):
                raise RuntimeError('storage_restore_source_metadata_changed')
    for key,attributes in selected.items():
        target=checked_file(restored_root/key,restored_root)
        if os.listxattr(target):raise RuntimeError('storage_restore_destination_metadata_exists')
        for attribute,value in attributes.items():os.setxattr(target,attribute,value,flags=os.XATTR_CREATE,follow_symlinks=False)
        if set(os.listxattr(target))!=set(attributes) or any(os.getxattr(target,attribute)!=value for attribute,value in attributes.items()):
            raise RuntimeError('storage_restore_metadata_mismatch')
    return {'objects':len(objects),'files':len(selected),'attributes':sum(len(a) for a in selected.values()),
        'metadata_source':'exact-restored-database','all_versions_have_identical_object_bytes':True,
        'source_bytes_and_attributes_independently_match':source_root is not None,
        'original_storage_modified':False,'values_reported':False}
