#!/usr/bin/env python3
"""Bounded offline history triage. Findings are private references, never values.

Pattern matches are candidates for review, not proof of active credentials.
No network access, revocation, Git history rewriting or automatic publication.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

PATTERNS = {
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github_token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{40,255})\b'),
    'aws_access_key': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'database_credential_uri': re.compile(rb'postgres(?:ql)?://[^\s/:@]{1,100}:[^\s/@]{8,200}@[^\s"\x27<>]{3,200}'),
    'jwt': re.compile(rb'\beyJ[A-Za-z0-9_-]{10,2000}\.[A-Za-z0-9_-]{10,8000}\.[A-Za-z0-9_-]{20,1000}\b'),
    'private_network_metadata': re.compile(rb'\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b'),
}
TEXT_SUFFIXES = {'.py', '.js', '.ts', '.jsx', '.tsx', '.md', '.json', '.yml', '.yaml', '.sql', '.sh', '.conf', '.toml', '.ini', '.txt', '.env'}


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)


def scan(root, refs, *, byte_limit=512 * 1024 * 1024):
    if not refs or any(not re.fullmatch(r'[A-Za-z0-9_./-]+', ref) or ref.startswith('-') for ref in refs):
        raise ValueError('Explicit safe Git refs required')
    pins = [git(root, 'rev-parse', '--verify', ref + '^{commit}').decode().strip() for ref in refs]
    objects = git(root, 'rev-list', '--objects', *pins).decode(errors='replace').splitlines()
    findings = []; scanned = total = skipped = 0
    # Batch metadata before content reads: oversize objects never enter memory.
    candidates = []
    for entry in objects:
        oid, separator, path = entry.partition(' ')
        if separator and (Path(path).suffix.lower() in TEXT_SUFFIXES or Path(path).name in {'.env', 'Dockerfile'}):
            candidates.append((oid, path))
    metadata = subprocess.run(['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                              cwd=root, input=('\n'.join(oid for oid, _ in candidates) + '\n').encode(),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout.splitlines()
    for (oid, path), row in zip(candidates, metadata):
        fields = row.decode().split()
        if len(fields) != 3 or fields[1] != 'blob':
            continue
        size = int(fields[2])
        if size > 1024 * 1024 or total + size > byte_limit:
            skipped += 1; continue
        data = git(root, 'cat-file', 'blob', oid)
        scanned += 1; total += size
        if b'\0' in data:
            continue
        for number, line in enumerate(data.splitlines(), 1):
            for kind, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    findings.append({'kind': kind, 'blob': oid, 'path': path, 'line': number,
                                     'value_sha256': hashlib.sha256(match.group()).hexdigest()})
    return {'refs': dict(zip(refs, pins)), 'scanned_blobs': scanned, 'scanned_bytes': total,
            'skipped_blobs': skipped, 'coverage_complete': skipped == 0,
            'classification': 'UNREVIEWED CANDIDATES; no active-secret determination',
            'findings': findings}


def write_private(directory, report):
    directory = Path(directory)
    # Only a new direct child of the current user's home; no replacement.
    if directory.parent.resolve() != Path.home().resolve() or directory.exists() or directory.is_symlink():
        raise ValueError('A new private directory directly beneath HOME is required')
    directory.mkdir(mode=0o700)
    descriptor = os.open(directory / 'report.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(report, handle, indent=2); handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('refs', nargs='+')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = scan(root, args.refs)
    write_private(args.output, report)
    print(json.dumps({key: report[key] for key in ('scanned_blobs', 'scanned_bytes', 'skipped_blobs', 'coverage_complete')} |
                     {'candidate_counts': {kind: sum(row['kind'] == kind for row in report['findings']) for kind in PATTERNS}}))


if __name__ == '__main__':
    main()
