#!/usr/bin/env python3
"""Validate the production-based forward-only schema-102 source contract."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '1e6b739a43759309a45ede2dff28a859209e4a64'

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
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                errors.append('immutable production migration changed: ' + relative)
        release = json.loads((release_dir / 'release.json').read_text())
        schema = release['schema']
        if not (schema['compatible_min'] <= 99 <= schema['compatible_max'] == schema['target'] == 102
                and schema['rollback_compatible_min'] <= 99 == schema['rollback_compatible_max']
                and schema['migration_class'] == 'expand-only'
                and release['migration_policy'] == 'automatic-after-known-good-backup-first-forward-repair'
                and release['migration_manifest'] == 'migrations-100-102.json'):
            errors.append('release must bridge production 099 to target 102 with rollback bounded at 099')
        manifest = json.loads((release_dir / 'migrations-100-102.json').read_text())
        if manifest.get('release_sha') not in {'CURRENT','STAGING'} and not re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('release_sha',''))):
            errors.append('manifest release identity invalid')
        entries = manifest['migrations']
        if [entry['number'] for entry in entries] != [100, 101, 102]:
            errors.append('forward manifest must contain ordered 100, 101 then 102')
        for entry in entries:
            n = entry['number']
            canonical = {
                100: '100_correct_site_visit_counter_rpc.sql',
                101: '101_add_variant_attribute_presentation.sql',
                102: '102_add_ecommerce_discount_conditions.sql',
            }.get(n)
            if n not in (100,101,102) or entry['from_schema'] != n-1 or entry['to_schema'] != n or entry['compatibility'] != 'expand-only' or entry['path'] != 'web/database/migrations/' + canonical:
                errors.append('forward manifest transition/path invalid')
                continue
            a = root / entry['path']
            b = root / 'web/supabase/migrations' / canonical
            if a.read_bytes() != b.read_bytes() or hashlib.sha256(a.read_bytes()).hexdigest() != entry['sha256']:
                errors.append('forward migration mirror/checksum invalid: ' + canonical)
        for tree in ('database','supabase'):
            versions = sorted(int(p.name.split('_',1)[0]) for p in (root / f'web/{tree}/migrations').glob('*.sql'))
            if versions != list(range(1,103)):
                errors.append('migration namespace must contain exactly 001 through 102: ' + tree)
    except (OSError, KeyError, ValueError, TypeError):
        errors.append('forward release artifacts missing or malformed')
    return errors

if __name__ == '__main__':
    errors = validate()
    for error in errors: print('INVALID ' + error)
    print('Forward release source contract ' + ('INVALID' if errors else 'PASS'))
    raise SystemExit(bool(errors))
