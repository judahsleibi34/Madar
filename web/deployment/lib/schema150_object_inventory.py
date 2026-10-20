"""Read-only, bounded filesystem measurements for the unregistered150 lifecycle.

A prepared preimage captures root identity only: live DB/object bytes are mutable.
Only AFTER an independently verified writer barrier may ``phase='fenced'`` take
an actual two-pass content measurement. Database contents are NEVER read here.
The inventory's historical ``content_sha256`` reference is not a quiescent capture.
A separate protected event must retain the fenced result; ``previous`` checks
in-place identity and subsequent content preservation, not restore authority.

Paths must be actual measured host mountpoints, including Docker volume
Mountpoint paths; a logical volume name is not a host path. No symlinks, hardlinked
files, nested mounts, devices or sockets are admitted. Descriptor walks, repeated
content/stat measurements and path reopens detect substitutions and observed races.
This is not an atomic filesystem snapshot or a replacement for writer quiescence.
It never stops services, changes files, runs commands or issues authority. Bounds
are source constants; oversized/unmeasurable datasets block acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import tarfile
import base64
import time

from deployment.lib.schema150_actor_inventory import REQUIRED_OBJECT_ROOTS, OBJECT_ROOT_ROLES

MAX_ENTRIES = 16384
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_CONTENT_BYTES = 256 * 1024 * 1024
MAX_DEPTH = 32
MAX_SECONDS = 60
CHUNK = 1024 * 1024
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def _require(value, code='schema150_object_measurement_invalid'):
    if not value: raise RuntimeError(code)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _path(value):
    return (isinstance(value, str) and len(value) <= 4096 and value.startswith('/') and value != '/'
            and str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts
            and '\\' not in value and not any(ord(c) < 32 for c in value))


def _signature(value):
    # atime is intentionally absent: this read-only measurement can change it.
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)


def _mount_id(descriptor):
    with open('/proc/self/fdinfo/'+str(descriptor), 'r', encoding='ascii') as stream:
        values = [line.split(':', 1)[1].strip() for line in stream if line.startswith('mnt_id:')]
    _require(len(values) == 1 and re.fullmatch('[0-9]+', values[0]), 'schema150_object_mount_unmeasurable')
    return int(values[0])


def _identity(descriptor):
    value = os.fstat(descriptor)
    _require(stat.S_ISDIR(value.st_mode), 'schema150_object_root_not_directory')
    return {'device': value.st_dev, 'inode': value.st_ino, 'mode': stat.S_IMODE(value.st_mode),
            'uid': value.st_uid, 'gid': value.st_gid, 'mount_id': _mount_id(descriptor)}


def _open_root(path):
    """Walk all ancestors through directory descriptors; no symlink traversal."""
    descriptor = os.open('/', _DIR_FLAGS)
    try:
        for component in PurePosixPath(path).parts[1:]:
            before = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            _require(stat.S_ISDIR(before.st_mode), 'schema150_object_path_untrusted')
            child = os.open(component, _DIR_FLAGS, dir_fd=descriptor)
            try:
                _require(_signature(before) == _signature(os.fstat(child)), 'schema150_object_path_changed')
            except BaseException:
                os.close(child); raise
            os.close(descriptor); descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor); raise


def _tick(budget):
    _require(time.monotonic() <= budget['deadline'], 'schema150_object_measurement_timeout')


def _hash_file(descriptor, size, budget):
    _require(0 <= size <= MAX_FILE_BYTES, 'schema150_object_file_limit')
    digest, count = hashlib.sha256(), 0
    while True:
        _tick(budget)
        chunk = os.read(descriptor, CHUNK)
        if not chunk: break
        count += len(chunk); budget['read_bytes'] += len(chunk)
        _require(count <= size and budget['read_bytes'] <= 2 * MAX_CONTENT_BYTES,
                 'schema150_object_content_limit')
        digest.update(chunk)
    _require(count == size, 'schema150_object_file_changed')
    return digest.hexdigest()


def _scan_once(descriptor, root_identity, budget):
    records, signatures, counts = [], {}, {'entries': 0, 'files': 0, 'bytes': 0}

    def walk(current, prefix, depth):
        _tick(budget); _require(depth <= MAX_DEPTH, 'schema150_object_depth_limit')
        before = os.fstat(current)
        _require(before.st_dev == root_identity['device'] and _mount_id(current) == root_identity['mount_id'],
                 'schema150_object_nested_mount')
        names = sorted(os.listdir(current))
        _require(len(names) <= MAX_ENTRIES, 'schema150_object_entry_limit')
        for name in names:
            _tick(budget)
            counts['entries'] += 1
            _require(counts['entries'] <= MAX_ENTRIES, 'schema150_object_entry_limit')
            relative = prefix+'/'+name if prefix else name
            _require(len(relative) <= 4096, 'schema150_object_path_limit')
            info = os.stat(name, dir_fd=current, follow_symlinks=False)
            _require(info.st_dev == root_identity['device'], 'schema150_object_nested_mount')
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, _DIR_FLAGS, dir_fd=current)
                try:
                    _require(_signature(info) == _signature(os.fstat(child)), 'schema150_object_path_changed')
                    records.append([relative, 'directory', stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid])
                    signatures[relative] = _signature(info)
                    walk(child, relative, depth+1)
                finally: os.close(child)
            else:
                _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                         'schema150_object_special_or_linked_file')
                counts['files'] += 1; counts['bytes'] += info.st_size
                _require(counts['bytes'] <= MAX_CONTENT_BYTES, 'schema150_object_content_limit')
                child = os.open(name, _FILE_FLAGS, dir_fd=current)
                try:
                    actual = os.fstat(child)
                    _require(_signature(actual) == _signature(info) and _mount_id(child) == root_identity['mount_id'],
                             'schema150_object_file_changed')
                    checksum = _hash_file(child, actual.st_size, budget)
                    _require(_signature(actual) == _signature(os.fstat(child)), 'schema150_object_file_changed')
                    records.append([relative, 'file', stat.S_IMODE(actual.st_mode), actual.st_uid, actual.st_gid,
                                    actual.st_size, checksum])
                    signatures[relative] = _signature(actual)
                finally: os.close(child)
            _require(_signature(info) == _signature(os.stat(name, dir_fd=current, follow_symlinks=False)),
                     'schema150_object_path_changed')
        _require(names == sorted(os.listdir(current)) and _signature(before) == _signature(os.fstat(current)),
                 'schema150_object_directory_changed')
        signatures[prefix] = _signature(before)

    walk(descriptor, '', 0)
    return {'sha256': _digest(records), **counts}, signatures


def _previous(value, roots, phase):
    if value is None: return None
    _require(isinstance(value, dict) and set(value) == {'version','phase','roots'} and type(value['version']) is int
             and value['version'] == 1 and value['phase'] in ('identity','fenced') and isinstance(value['roots'],dict)
             and set(value['roots']) == set(roots), 'schema150_object_previous_invalid')
    _require(phase == 'fenced' or value['phase'] == 'identity', 'schema150_object_phase_regression')
    for logical, prior in value['roots'].items():
        _require(isinstance(prior,dict) and set(prior) == {'type','source','identity','content'}
                 and prior['type'] in ('bind','volume') and _path(prior['source'])
                 and isinstance(prior['identity'],dict)
                 and set(prior['identity']) == {'device','inode','mode','uid','gid','mount_id'}
                 and all(type(item) is int and item >= 0 for item in prior['identity'].values()),
                 'schema150_object_previous_invalid')
        content = prior['content']
        if value['phase'] == 'identity' or logical == 'database':
            _require(content is None, 'schema150_object_previous_invalid')
        else:
            _require(isinstance(content,dict) and set(content) == {'sha256','entries','files','bytes'}
                     and isinstance(content['sha256'],str) and re.fullmatch('[0-9a-f]{64}',content['sha256'])
                     and all(type(content[key]) is int and content[key] >= 0 for key in ('entries','files','bytes')),
                     'schema150_object_previous_invalid')
    return json.loads(json.dumps(value))


def measure_roots(roots, *, phase='identity', previous=None):
    """Measure approved host roots; compare optional protected prior measurement.

    ``identity`` never walks object bytes. ``fenced`` requires externally proven
    writer quiescence and takes two matching complete passes. Original root
    identities must remain exact. DB content is null in every phase. A previous
    fenced capture also pins all non-DB content; current inventory reference
    hashes are never silently substituted for a measured quiescence preimage.
    """
    _require(phase in ('identity','fenced') and isinstance(roots,dict)
             and REQUIRED_OBJECT_ROOTS <= set(roots) <= OBJECT_ROOT_ROLES)
    sources = []
    for logical, root in roots.items():
        _require(isinstance(root,dict) and set(root) == {'type','source','content_sha256'}
                 and root['type'] in ('bind','volume') and _path(root['source'])
                 and isinstance(root['content_sha256'],str) and re.fullmatch('[0-9a-f]{64}',root['content_sha256']))
        sources.append(PurePosixPath(root['source']))
    _require(len(set(sources)) == len(sources) and not any(a in b.parents or b in a.parents
             for index,a in enumerate(sources) for b in sources[index+1:]), 'schema150_object_root_overlap')
    old = _previous(previous, roots, phase)
    result = {'version':1,'phase':phase,'roots':{}}
    budget = {'deadline':time.monotonic()+MAX_SECONDS,'read_bytes':0}
    descriptors, first_pass = {}, {}
    try:
        # Hold every measured root descriptor through both forest passes.
        for logical, root in sorted(roots.items()):
            _tick(budget)
            descriptor = _open_root(root['source']); descriptors[logical] = descriptor
            actual = {'type':root['type'],'source':root['source'],'identity':_identity(descriptor),'content':None}
            if old is not None:
                prior = old['roots'][logical]
                _require(isinstance(prior,dict) and set(prior) == set(actual)
                         and all(prior[key] == actual[key] for key in ('type','source','identity'))
                         and (logical != 'database' or prior['content'] is None), 'schema150_object_root_identity_changed')
            result['roots'][logical] = actual
        if phase == 'fenced':
            for logical, descriptor in descriptors.items():
                if logical != 'database':
                    first_pass[logical] = _scan_once(descriptor, result['roots'][logical]['identity'], budget)
            for logical, descriptor in descriptors.items():
                if logical != 'database':
                    reopened = _open_root(roots[logical]['source'])
                    try:
                        _require(_identity(reopened) == result['roots'][logical]['identity'],
                                 'schema150_object_root_identity_changed')
                    finally: os.close(reopened)
                    current = _scan_once(descriptor, result['roots'][logical]['identity'], budget)
                    _require(current == first_pass[logical], 'schema150_object_content_changed')
                    result['roots'][logical]['content'] = current[0]
        for logical, root in sorted(roots.items()):
            actual = result['roots'][logical]
            reopened = _open_root(root['source'])
            try: _require(_identity(reopened) == actual['identity'], 'schema150_object_root_identity_changed')
            finally: os.close(reopened)
            if old is not None and old['phase'] == 'fenced':
                _require(old['roots'][logical]['content'] == actual['content'], 'schema150_object_preservation_changed')
    except OSError:
        raise RuntimeError('schema150_object_path_unmeasurable') from None
    finally:
        for descriptor in descriptors.values(): os.close(descriptor)
    return result


def archive_roots(roots, destination, *, previous):
    """Capture the measured non-database forest, never a live database volume.

    The protected caller must retain the writer barrier. The archive includes
    original metadata and xattrs, but restoring it grants no execution authority.
    Descriptor-relative opens reject links and substitutions during capture; two
    independent forest measurements bracket it. Publication belongs to backup.
    """
    before = measure_roots(roots, phase='fenced', previous=previous)
    budget = {'deadline': time.monotonic()+MAX_SECONDS, 'read_bytes': 0}
    count = total = 0
    with open(destination, 'xb') as output:
        os.fchmod(output.fileno(), 0o600)
        with tarfile.open(fileobj=output, mode='w|gz', format=tarfile.PAX_FORMAT) as archive:
            def walk(descriptor, logical, prefix, depth):
                nonlocal count, total
                _tick(budget); _require(depth <= MAX_DEPTH, 'schema150_object_depth_limit')
                original = os.fstat(descriptor)
                identity = before['roots'][logical]['identity']
                _require(original.st_dev == identity['device'] and _mount_id(descriptor) == identity['mount_id'],
                         'schema150_object_nested_mount')
                names = sorted(os.listdir(descriptor))
                for name in names:
                    _tick(budget); count += 1
                    _require(count <= MAX_ENTRIES*len(roots), 'schema150_object_entry_limit')
                    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    relative = prefix+'/'+name if prefix else name
                    is_directory = stat.S_ISDIR(info.st_mode)
                    _require(is_directory or stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                             'schema150_object_special_or_linked_file')
                    child = os.open(name, _DIR_FLAGS if is_directory else _FILE_FLAGS, dir_fd=descriptor)
                    try:
                        _require(_signature(info) == _signature(os.fstat(child))
                                 and _mount_id(child) == identity['mount_id'], 'schema150_object_file_changed')
                        header = tarfile.TarInfo(logical+'/'+relative)
                        header.mode = stat.S_IMODE(info.st_mode); header.uid = info.st_uid; header.gid = info.st_gid
                        header.mtime = info.st_mtime_ns/10**9
                        header.type = tarfile.DIRTYPE if is_directory else tarfile.REGTYPE
                        header.size = 0 if is_directory else info.st_size
                        attributes = {key:base64.b64encode(os.getxattr(child,key)).decode('ascii')
                                      for key in sorted(os.listxattr(child))}
                        raw = json.dumps(attributes, sort_keys=True, separators=(',', ':'))
                        _require(len(raw.encode()) <= 65536, 'schema150_object_xattr_limit')
                        header.pax_headers['madar.xattrs.base64'] = raw
                        if is_directory:
                            archive.addfile(header); walk(child, logical, relative, depth+1)
                        else:
                            total += info.st_size
                            _require(info.st_size <= MAX_FILE_BYTES and total <= MAX_CONTENT_BYTES*len(roots),
                                     'schema150_object_content_limit')
                            # Duplicate owns only this read position, not a mutable pathname.
                            with os.fdopen(os.dup(child), 'rb') as stream: archive.addfile(header, stream)
                        _require(_signature(info) == _signature(os.fstat(child)), 'schema150_object_file_changed')
                    finally: os.close(child)
                    _require(_signature(info) == _signature(os.stat(name, dir_fd=descriptor, follow_symlinks=False)),
                             'schema150_object_path_changed')
                _require(names == sorted(os.listdir(descriptor)) and _signature(original) == _signature(os.fstat(descriptor)),
                         'schema150_object_directory_changed')
            for logical in sorted(roots):
                if logical == 'database': continue
                descriptor = _open_root(roots[logical]['source'])
                try:
                    _require(_identity(descriptor) == before['roots'][logical]['identity'],
                             'schema150_object_root_identity_changed')
                    info=os.fstat(descriptor);header=tarfile.TarInfo(logical)
                    header.type=tarfile.DIRTYPE;header.mode=stat.S_IMODE(info.st_mode)
                    header.uid=info.st_uid;header.gid=info.st_gid;header.mtime=info.st_mtime_ns/10**9
                    attributes={key:base64.b64encode(os.getxattr(descriptor,key)).decode('ascii')
                                for key in sorted(os.listxattr(descriptor))}
                    raw=json.dumps(attributes,sort_keys=True,separators=(',',':'))
                    _require(len(raw.encode())<=65536,'schema150_object_xattr_limit')
                    header.pax_headers['madar.xattrs.base64']=raw;archive.addfile(header)
                    walk(descriptor, logical, '', 0)
                finally: os.close(descriptor)
        output.flush(); os.fsync(output.fileno())
    after = measure_roots(roots, phase='fenced', previous=before)
    _require(after == before, 'schema150_object_preservation_changed')
    return before
