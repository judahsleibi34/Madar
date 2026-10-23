#!/usr/bin/env python3
"""Tracked-file hygiene and credential-format checks; never print secret values.

This scans the current tree, including tests and documents. It is not a history
scan or a certification that arbitrary passwords/opaque credentials are absent.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    'private_key':re.compile(rb'(?m)^[ \t]*-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github_token':re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{40,255})\b'),
    'jwt':re.compile(rb'\beyJ[A-Za-z0-9_-]{10,2000}\.[A-Za-z0-9_-]{10,8000}\.[A-Za-z0-9_-]{20,1000}\b'),
    'aws_access_key':re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
}


def scan_file(path):
    findings=set();tail=b'';lines=0
    with path.open('rb') as stream:
        while chunk:=stream.read(65536):
            data=tail+chunk;base=lines-tail.count(b'\n')
            for kind,pattern in PATTERNS.items():
                for match in pattern.finditer(data):
                    findings.add((kind,base+data[:match.start()].count(b'\n')+1))
            lines+=chunk.count(b'\n');tail=data[-16384:]
    return sorted(findings)


def inspect(root,names):
    findings=[]
    for name in names:
        base=Path(name).name.lower();path=root/name
        if (base=='.env' or base.startswith('.env.')) and not base.endswith(('.example','.sample','.template')):
            findings.append({'path':name,'kind':'forbidden_environment_file'})
        # Never follow a source-controlled link into an operator's private files.
        if path.is_symlink():continue
        if not path.is_file():
            findings.append({'path':name,'kind':'tracked_file_unreadable'});continue
        for kind,line in scan_file(path):findings.append({'path':name,'line':line,'kind':kind})
    return findings


def main():
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().rstrip('\0').split('\0')
    findings=inspect(ROOT,[n for n in names if n])
    if findings:
        print(json.dumps({'status':'FAIL','findings':findings},sort_keys=True))
        return 1
    print('Tracked secret-file hygiene and credential-format scan PASS (current tree; history/opaque passwords not certified)')
    return 0


if __name__=='__main__':raise SystemExit(main())
