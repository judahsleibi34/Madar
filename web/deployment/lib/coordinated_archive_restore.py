"""Sequential offline byte recovery, including internal backward hardlinks.

No archive entry creates a link on disk. Hardlinks become separate files after
validating the previous regular target. Never execute restored code or apply
backed-up ownership/permissions. Two sequential passes avoid gzip back-seeking.
"""
import hashlib
import os
from pathlib import Path
import shutil
import tarfile
from deployment.lib.coordinated_checkpoint import relative,digest_file


def identity(member):
    return (member.name,member.type,member.size,member.linkname,bool(member.sparse))


def restore_archive(source,destination,*,max_bytes=16*1024**3,max_members=200000):
    source,destination=Path(source),Path(destination)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError('checkpoint_restore_destination_exists')
    expected=[];seen=set();sizes={};total=0;hardlinks=0
    # Validate ALL headers before creating the destination. Stream both passes
    # linearly; extractfile on a random-access gzip reader causes costly seeks.
    with tarfile.open(source,'r|gz') as archive:
        for member in archive:
            if len(expected)>=max_members:raise RuntimeError('checkpoint_archive_member_limit')
            name=relative(member.name).as_posix()
            if name in seen or member.sparse:raise RuntimeError('checkpoint_archive_unsafe_member')
            if member.islnk():
                target=relative(member.linkname).as_posix()
                if target not in sizes:raise RuntimeError('checkpoint_archive_hardlink_target_invalid')
                size=sizes[target];hardlinks+=1
            elif member.isfile():size=member.size
            elif member.isdir():size=0
            else:raise RuntimeError('checkpoint_archive_unsafe_member')
            if size<0:raise RuntimeError('checkpoint_archive_unsafe_member')
            seen.add(name)
            if member.isfile() or member.islnk():sizes[name]=size
            total+=size
            if total>max_bytes:raise RuntimeError('checkpoint_archive_size_limit')
            expected.append(identity(member))
    destination.mkdir(mode=0o700);inventory={};count=0
    with tarfile.open(source,'r|gz') as archive:
        for member in archive:
            if count>=len(expected) or identity(member)!=expected[count]:
                raise RuntimeError('checkpoint_archive_changed_after_preflight')
            count+=1;name=relative(member.name).as_posix();target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if member.isdir():target.mkdir(exist_ok=True,mode=0o700);continue
            expected_digest=hashlib.sha256()
            if member.islnk():
                prior=relative(member.linkname).as_posix();restored=destination/prior
                if restored.is_symlink() or not restored.is_file() or digest_file(restored)!=inventory[prior]:
                    raise RuntimeError('checkpoint_archive_hardlink_target_changed')
                stream=restored.open('rb')
            else:stream=archive.extractfile(member)
            with stream,target.open('xb') as output:
                while chunk:=stream.read(1024*1024):
                    expected_digest.update(chunk);output.write(chunk)
                # This quarantine proves recovered bytes, not crash durability.
                # Per-file fsync makes large controller trees exceed the bound.
                output.flush()
            target.chmod(0o600);inventory[name]=digest_file(target)
            if inventory[name]!=expected_digest.hexdigest() or target.stat().st_size!=sizes[name]:
                raise RuntimeError('checkpoint_archive_restore_mismatch')
    if count!=len(expected):raise RuntimeError('checkpoint_archive_changed_after_preflight')
    return {'files':len(inventory),'bytes':total,'hardlinks_materialized':hardlinks,
            'restored_bytes_verified':True,'code_executed':False,'configuration_activated':False,
            'archive_reading':'two-sequential-passes','crash_durability_proven':False}


def verify_restored_archive(source,destination,*,max_bytes=16*1024**3,max_members=200000):
    """Independently measure an existing quarantine against every archive byte.

    No prior PASS or partial-execution summary is consumed, no file is altered.
    This avoids writing a second large recovered tree after a later gate failed.
    """
    destination=Path(destination)
    if destination.is_symlink() or not destination.is_dir():
        raise RuntimeError('checkpoint_restore_quarantine_untrusted')
    owner=destination.stat().st_uid;seen=set();sizes={};inventory={};total=hardlinks=0
    with tarfile.open(source,'r|gz') as archive:
        for member in archive:
            if len(seen)>=max_members:raise RuntimeError('checkpoint_archive_member_limit')
            name=relative(member.name).as_posix();target=destination/name
            if name in seen or member.sparse:raise RuntimeError('checkpoint_archive_unsafe_member')
            seen.add(name)
            if member.islnk():
                prior=relative(member.linkname).as_posix()
                if prior not in inventory:raise RuntimeError('checkpoint_archive_hardlink_target_invalid')
                size=sizes[prior];expected=inventory[prior];hardlinks+=1
            elif member.isfile():
                size=member.size;check=hashlib.sha256()
                with archive.extractfile(member) as stream:
                    while chunk:=stream.read(1024*1024):check.update(chunk)
                expected=check.hexdigest()
            elif member.isdir():size=0
            else:raise RuntimeError('checkpoint_archive_unsafe_member')
            if size<0:raise RuntimeError('checkpoint_archive_unsafe_member')
            total+=size
            if total>max_bytes:raise RuntimeError('checkpoint_archive_size_limit')
            for parent in (target.parent,*target.parent.parents):
                if parent.is_symlink() or not parent.is_dir():raise RuntimeError('checkpoint_restore_quarantine_untrusted')
                if parent==destination:break
            if member.isdir():
                if target.is_symlink() or not target.is_dir():raise RuntimeError('checkpoint_archive_restore_mismatch')
                continue
            info=target.lstat()
            if (target.is_symlink() or not target.is_file() or info.st_uid!=owner or info.st_mode&0o022
                    or info.st_nlink!=1 or info.st_size!=size or digest_file(target)!=expected):
                raise RuntimeError('checkpoint_archive_restore_mismatch')
            sizes[name]=size;inventory[name]=expected
    actual=set()
    for parent,dirs,files in os.walk(destination,followlinks=False):
        if any((Path(parent)/name).is_symlink() for name in dirs):raise RuntimeError('checkpoint_restore_quarantine_untrusted')
        actual.update((Path(parent)/name).relative_to(destination).as_posix() for name in files)
    if actual!=set(inventory):raise RuntimeError('checkpoint_archive_restore_inventory_inexact')
    return {'files':len(inventory),'bytes':total,'hardlinks_materialized':hardlinks,
        'restored_bytes_verified':True,'code_executed':False,'configuration_activated':False,
        'archive_reading':'independent-sequential-quarantine-verification','crash_durability_proven':False}
