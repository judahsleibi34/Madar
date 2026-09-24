#!/usr/bin/env python3
"""Validate the production-based forward-only schema-107 source contract."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '1e6b739a43759309a45ede2dff28a859209e4a64'

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()

def validate(root: Path = ROOT) -> list[str]:
    errors = []
    release_dir = root / 'web/deployment/releases'
    try:
        pin = json.loads((release_dir / 'production-001-099.json').read_text())
        if pin['production_baseline'] != BASELINE or len(pin['files']) != 198:
            errors.append('immutable production lineage manifest invalid')
        for relative, checksum in pin['files'].items():
            path = root / relative
            if not re.fullmatch(r'web/(database|supabase)/migrations/\d{3}_[a-z0-9_]+\.sql', relative):
                errors.append('invalid production migration path')
                continue
            if not path.is_file() or digest(path) != checksum:
                errors.append('immutable production migration changed: ' + relative)
        release = json.loads((release_dir / 'release.json').read_text())
        schema = release['schema']
        if not (schema['compatible_min'] == 104 <= schema['compatible_max'] == schema['target'] == 107
                and schema['rollback_compatible_min'] == 104 == schema['rollback_compatible_max']
                and schema['migration_class'] == 'expand-only'
                and release['migration_policy'] == 'automatic-after-known-good-backup-first-forward-repair'
                and release['migration_manifest'] == 'migrations-105-107.json'):
            errors.append('release must bridge schema 104 to target 107 with rollback bounded at 104')
        manifest = json.loads((release_dir / 'migrations-105-107.json').read_text(encoding='utf-8-sig'))
        if manifest.get('release_sha') not in {'CURRENT','STAGING'} and not re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('release_sha',''))):
            errors.append('manifest release identity invalid')
        entries = manifest['migrations']
        if [entry['number'] for entry in entries] != [105, 106, 107]:
            errors.append('forward manifest must contain ordered migrations 105, 106, and 107')
        for entry in entries:
            n = entry['number']
            canonical = {
                105: '105_add_order_delivery_fees.sql',
                106: '106_add_ecommerce_category_images.sql',
                107: '107_add_ecommerce_brands.sql',
            }.get(n)
            if n not in (105, 106, 107) or entry['from_schema'] != n - 1 or entry['to_schema'] != n or entry['compatibility'] not in ('expand-only','forward-compatible') or entry['path'] != 'web/database/migrations/' + canonical:
                errors.append('forward manifest transition/path invalid')
                continue
            a = root / entry['path']
            b = root / 'web/supabase/migrations' / canonical
            if a.read_bytes().replace(b'\r\n', b'\n') != b.read_bytes().replace(b'\r\n', b'\n') or digest(a) != entry['sha256']:
                errors.append('forward migration mirror/checksum invalid: ' + canonical)
        for tree in ('database','supabase'):
            versions = sorted(int(p.name.split('_',1)[0]) for p in (root / f'web/{tree}/migrations').glob('*.sql'))
            if versions != list(range(1,108)):
                errors.append('migration namespace must contain exactly 001 through 107: ' + tree)
    except (OSError, KeyError, ValueError, TypeError):
        errors.append('forward release artifacts missing or malformed')
    return errors

if __name__ == '__main__':
    errors = validate()
    for error in errors: print('INVALID ' + error)
    print('Forward release source contract ' + ('INVALID' if errors else 'PASS'))
    raise SystemExit(bool(errors))
