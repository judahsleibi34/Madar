"""Deterministic Git-object migration discovery; no database or authority effects.

Source history and mirrors are authenticated against an independently selected
ancestor. Execution must independently authenticate that ancestor/source, inspect
the real database and satisfy protected controller admission. A configured Git
remote alone is not release provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import selectors
import time

REPOSITORY = 'judahsleibi34/Madar'
ORIGINS = {'git@github.com:judahsleibi34/Madar.git', 'https://github.com/judahsleibi34/Madar.git'}
TREES = ('web/database/migrations/', 'web/supabase/migrations/')
NAME = re.compile(r'([0-9]{3,})_([a-z0-9][a-z0-9_]*)\.sql')
SHA = re.compile('[0-9a-f]{40}')
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_ENTRIES = 10000
LEGACY_MIRRORS = {'004_enable_rls_policies.sql': '005_enable_rls_policies.sql',
                  '005_create_get_tables_function.sql': '004_create_get_tables_function.sql'}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class GitSource:
    def __init__(self, root):
        self.deadline = time.monotonic() + 90
        self.root = Path(root).resolve(strict=True)
        self.environment = {'PATH': os.defpath, 'HOME': str(self.root),
                            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                            'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_TERMINAL_PROMPT': '0',
                            'LANG': 'C.UTF-8'}
        if self.command('remote', 'get-url', 'origin').strip().decode() not in ORIGINS:
            raise RuntimeError('migration_source_repository_invalid')
        graft = self.command('rev-parse', '--git-path', 'info/grafts').decode().strip()
        graft = Path(graft) if Path(graft).is_absolute() else self.root / graft
        if graft.exists() or graft.is_symlink():
            raise RuntimeError('migration_source_grafted_history_refused')

    def command(self, *args):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0: raise RuntimeError('migration_source_time_limit')
        output = bytearray()
        with subprocess.Popen(['/usr/bin/git', '--no-replace-objects', '-c', 'safe.directory=' + str(self.root),
                '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', *args],
                cwd=self.root, env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                with selectors.DefaultSelector() as ready:
                    ready.register(process.stdout, selectors.EVENT_READ)
                    end = min(self.deadline, time.monotonic() + 30)
                    while True:
                        left = end - time.monotonic()
                        if left <= 0 or not ready.select(left):
                            raise RuntimeError('migration_source_time_limit')
                        block = os.read(process.stdout.fileno(), 65536)
                        if not block: break
                        output.extend(block)
                        if len(output) > MAX_TOTAL:
                            raise RuntimeError('migration_source_output_limit')
                if process.wait(timeout=max(0.01, end - time.monotonic())):
                    raise RuntimeError('migration_source_git_verification_failed')
            except BaseException:
                process.kill(); process.wait()
                raise
        return bytes(output)

    def commit(self, sha):
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise RuntimeError('migration_source_exact_commit_required')
        if self.command('cat-file', '-t', sha).strip() != b'commit':
            raise RuntimeError('migration_source_commit_object_required')
        return sha

    def blob(self, oid):
        if not SHA.fullmatch(oid) or int(self.command('cat-file', '-s', oid)) > MAX_FILE:
            raise RuntimeError('migration_source_file_limit')
        body = self.command('cat-file', 'blob', oid)
        actual = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
        if actual != oid:
            raise RuntimeError('migration_source_object_changed')
        try: body.decode('utf-8')
        except UnicodeDecodeError: raise RuntimeError('migration_source_utf8_required') from None
        return body

    def files(self, sha, *paths):
        self.commit(sha)
        records = self.command('ls-tree', '-rz', sha, '--', *paths).split(b'\0')
        result = {}; total = 0
        for record in records:
            if not record: continue
            head, rawpath = record.split(b'\t', 1)
            mode, kind, oid = head.decode().split()
            if mode != '100644' or kind != 'blob':
                raise RuntimeError('migration_source_regular_nonexecutable_blob_required')
            path = rawpath.decode('utf-8')
            if path in result or len(result) >= MAX_ENTRIES:
                raise RuntimeError('migration_source_inventory_limit')
            result[path] = self.blob(oid); total += len(result[path])
            if total > MAX_TOTAL: raise RuntimeError('migration_source_inventory_bytes_limit')
        return result


@dataclass(frozen=True)
class MigrationBytes:
    number: int
    path: str
    mirror_path: str
    sql: bytes

    @property
    def sha256(self): return hashlib.sha256(self.sql).hexdigest()

    def record(self):
        return {'number': self.number, 'path': self.path, 'mirror_path': self.mirror_path,
                'sha256': self.sha256, 'bytes': len(self.sql), 'mirror_equal': True}


@dataclass(frozen=True)
class Inventory:
    source_sha: str
    history_base_sha: str
    migrations: tuple[MigrationBytes, ...]
    excluded_versions: tuple[int, ...]

    @property
    def target(self): return max(m.number for m in self.migrations if m.number not in self.excluded_versions)

    def forward(self, origin, target=None):
        target = self.target if target is None else target
        numbers = {m.number: m for m in self.migrations}
        if (type(origin) is not int or type(target) is not int or origin not in numbers
                or target not in numbers or origin in self.excluded_versions or target in self.excluded_versions
                or not origin <= target <= self.target):
            raise RuntimeError('migration_origin_or_target_invalid')
        result = []; previous = origin
        for number in sorted(numbers):
            if origin < number <= target and number not in self.excluded_versions:
                expected = 143 if previous == 141 and self.excluded_versions == (142,) else previous + 1
                if number != expected: raise RuntimeError('migration_forward_path_gap')
                result.append(numbers[number]); previous = number
        if previous != target: raise RuntimeError('migration_forward_path_incomplete')
        return tuple(result)

    def document(self):
        return {'version': 1, 'repository': REPOSITORY, 'source_sha': self.source_sha,
                'history_base_sha': self.history_base_sha, 'target_schema': self.target,
                'excluded_versions': list(self.excluded_versions),
                'migrations': [m.record() for m in self.migrations], 'authority_issued': False}


def _tree(files, prefix):
    result = {}
    for path, body in files.items():
        if not path.startswith(prefix): continue
        leaf = path[len(prefix):]
        match = NAME.fullmatch(leaf)
        if not match or '/' in leaf or len(match[1]) > 9:
            raise RuntimeError('migration_filename_invalid')
        number = int(match[1])
        if number < 1 or match[1] != f'{number:03d}' or number in result:
            raise RuntimeError('migration_duplicate_or_noncanonical_version')
        result[number] = (path, body)
    if not result: raise RuntimeError('migration_tree_empty')
    if any(number != expected for expected, number in enumerate(sorted(result), 1)):
        raise RuntimeError('migration_inventory_gap')
    return result


def discover(root, *, source_sha, history_base_sha):
    git = GitSource(root); git.commit(source_sha); git.commit(history_base_sha)
    git.command('merge-base', '--is-ancestor', history_base_sha, source_sha)
    baseline = git.files(history_base_sha, *TREES)
    current = git.files(source_sha, *TREES)
    if any(current.get(path) != body for path, body in baseline.items()):
        raise RuntimeError('migration_published_history_changed')
    db, mirror = _tree(current, TREES[0]), _tree(current, TREES[1])
    _tree(baseline, TREES[0]); _tree(baseline, TREES[1])
    if set(db) != set(mirror): raise RuntimeError('migration_mirror_inventory_mismatch')
    result = []
    for number, (path, body) in sorted(db.items()):
        name = path[len(TREES[0]):]
        counterpart = TREES[1] + LEGACY_MIRRORS.get(name, name)
        if counterpart not in current or body != current[counterpart]:
            raise RuntimeError('migration_sql_mirror_changed')
        # Alternate mirror names are historical exceptions, never permission to
        # introduce another branch or overwrite an already published prefix.
        if name in LEGACY_MIRRORS and (path not in baseline or counterpart not in baseline):
            raise RuntimeError('migration_untrusted_historical_exception')
        result.append(MigrationBytes(number, path, counterpart, body))
    excluded = ()
    legacy_path = TREES[0] + '143_complete_learning_capabilities.sql'
    if legacy_path in current:
        from deployment.lib.learning_migration_path import CONTRACT_PATH, CONTRACT_SHA256
        contract_files = git.files(source_sha, CONTRACT_PATH)
        body = contract_files.get(CONTRACT_PATH, b'')
        if hashlib.sha256(body).hexdigest() != CONTRACT_SHA256:
            raise RuntimeError('migration_historical_branch_contract_changed')
        contract = json.loads(body)
        if (contract.get('status') != 'finalized' or contract.get('source_schema') != 141
                or contract.get('target_schema') != 143 or contract.get('excluded_schemas') != [142]
                or contract.get('sql_sha256') != hashlib.sha256(current[legacy_path]).hexdigest()):
            raise RuntimeError('migration_historical_branch_invalid')
        excluded = (142,)
    return Inventory(source_sha, history_base_sha, tuple(result), excluded)
