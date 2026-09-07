#!/usr/bin/env python3
"""Online SSH off-host replication; NOT offline, encrypted media or immutable."""
from __future__ import annotations

import base64
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile

import backup_support as backup

DESTINATION = Path('/srv/data2/madar-backups')


def validate_destination(root: Path, expected_uuid: str) -> None:
    if root != DESTINATION:
        raise backup.BackupError('node1_destination_not_authorized')
    backup.real_path(root)
    info = root.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise backup.BackupError('node1_destination_permissions_invalid')
    if not re.fullmatch(r'[0-9a-f-]{36}', expected_uuid):
        raise backup.BackupError('node1_filesystem_uuid_required')
    result = subprocess.run(['findmnt', '-T', str(root), '-n', '-o', 'SOURCE,FSTYPE,TARGET,UUID'],
                            capture_output=True, text=True, timeout=10, check=True)
    if result.stdout.split() != ['/dev/sdc1', 'ext4', '/srv/data2', expected_uuid]:
        raise backup.BackupError('node1_filesystem_identity_mismatch')


def extract(stream, staging: Path) -> None:
    total = 0
    count = 0
    available = shutil.disk_usage(staging).free - 10 * 1024 ** 3
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isdir() or member.isfile()):
                raise backup.BackupError('node1_archive_member_rejected')
            target = staging.joinpath(*path.parts)
            count += 1
            total += member.size
            if count > 1000000 or total > available or member.size < 0:
                raise backup.BackupError('node1_archive_capacity_limit')
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with target.open('xb') as output:
                    source = archive.extractfile(member)
                    shutil.copyfileobj(source, output, length=1024 * 1024)


def receive(backup_id: str, sums: str, expected_uuid: str, keep: int, *, stream=None) -> dict:
    root = DESTINATION
    validate_destination(root, expected_uuid)
    if not backup.BACKUP_ID.fullmatch(backup_id) or not re.fullmatch('[0-9a-f]{64}', sums) or keep < 2:
        raise backup.BackupError('node1_request_invalid')
    fd = os.open(root / '.node1.lock', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        staging = Path(tempfile.mkdtemp(prefix='.' + backup_id + '.incomplete.', dir=root))
        final = root / backup_id
        try:
            extract(stream or sys.stdin.buffer, staging)
            if backup.digest(staging / 'SHA256SUMS') != sums:
                raise backup.BackupError('node1_source_checksum_manifest_mismatch')
            manifest = backup.verify(staging, dump=False)
            if manifest.get('backup_id') != backup_id:
                raise backup.BackupError('node1_backup_identity_mismatch')
            validate_destination(root, expected_uuid)
            if final.exists() or final.is_symlink():
                backup.verify(final, dump=False)
                if backup.digest(final / 'SHA256SUMS') != sums:
                    raise backup.BackupError('node1_existing_backup_differs')
                status = 'already_verified'
            else:
                # A complete copy exists before the single rename publishes it.
                os.rename(staging, final)
                status = 'replicated'
            backup.atomic_text(root / 'LATEST', f'{backup_id[6:]} {final}\n')
            removed = backup.retention(root, final, keep)
            return {'status': status, 'backup_id': backup_id, 'sha256sums_sha256': sums,
                    'destination': str(root), 'retention_removed_backup_ids': removed}
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def remote_command(backup_id: str, sums: str, uuid: str, keep: int) -> str:
    # Transfer reviewed code in the SSH command; no executable/state installation
    # on Node 1 and no remote paths beyond DESTINATION are needed.
    support = Path(backup.__file__).read_bytes()
    receiver = Path(__file__).read_bytes()
    bootstrap = ('import base64,sys,types; '
                 'm=types.ModuleType("backup_support");sys.modules["backup_support"]=m; '
                 f'exec(base64.b64decode({base64.b64encode(support).decode()!r}),m.__dict__); '
                 'n={"__name__":"node1_receiver"}; '
                 f'exec(base64.b64decode({base64.b64encode(receiver).decode()!r}),n); '
                 'n["receiver_main"](*sys.argv[1:])')
    return shlex.join(['python3', '-c', bootstrap, backup_id, sums, uuid, str(keep)])


def receiver_main(backup_id: str, sums: str, uuid: str, keep: str) -> None:
    os.umask(0o077)
    signal.alarm(7200)
    try:
        print(json.dumps(receive(backup_id, sums, uuid, int(keep))))
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': str(error) if isinstance(error, backup.BackupError) else type(error).__name__}))
        raise SystemExit(1)


def replicate() -> dict:
    os.umask(0o077)
    root = Path(os.environ['MADAR_BACKUP_DIR'])
    backup.real_path(root)
    fd = os.open(root / '.backup.lock', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = backup.latest(Path(os.environ['MADAR_BACKUP_FRESHNESS_MARKER']), root)
        sums = backup.digest(source / 'SHA256SUMS')
        host = os.environ.get('MADAR_NODE1_SSH_HOST', 'madar-node1-lan')
        if host not in ('madar-node1-lan', 'madar-node1'):
            raise backup.BackupError('node1_ssh_alias_not_authorized')
        uuid = os.environ['MADAR_NODE1_FILESYSTEM_UUID']
        keep = int(os.environ.get('MADAR_NODE1_KEEP_COUNT', '90'))
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'ConnectTimeout=15', '-o', 'ConnectionAttempts=2',
                   '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
                   host, remote_command(source.name, sums, uuid, keep)]
        with subprocess.Popen(['tar', '--hard-dereference', '-C', str(source), '-cf', '-', '.'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as archive:
            try:
                result = subprocess.run(command, stdin=archive.stdout, capture_output=True, timeout=7300)
                archive.stdout.close()
                archive.wait(timeout=30)
            except BaseException:
                archive.kill()
                archive.wait()
                raise
            if result.returncode or archive.returncode:
                raise backup.BackupError('node1_transfer_failed')
        backup.verify(source)
        response = json.loads(result.stdout)
        if (response.get('backup_id') != source.name or response.get('sha256sums_sha256') != sums
                or response.get('status') not in ('replicated', 'already_verified')):
            raise backup.BackupError('node1_receipt_mismatch')
        return response


if __name__ == '__main__':
    try:
        print(json.dumps(replicate()))
    except Exception as error:
        print('ERROR: ' + (str(error) if isinstance(error, backup.BackupError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
