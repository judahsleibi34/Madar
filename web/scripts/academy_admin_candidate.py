"""Validate the exact unselected144→145 academy admin review candidate."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = '339028681cc38e0d679eb3a2bd356ff69df31c23289c3e4e6fd7974ddf0cc715'
BRIDGE_SHA256 = 'c460a8ae6e7785757c220886a430c1798f2caa749f61b7343507b248451d00bf'
NAME = '145_add_academy_admin_review_controls.sql'


def validated_entries(root):
    root=Path(root);release=root/'web/deployment/releases'
    manifest=release/'migrations-144-145-academy-admin.json';bridge=release/'schema-144-145-academy-admin-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest()!=BRIDGE_SHA256:
        raise ValueError('Academy admin candidate metadata changed')
    raw=json.loads(manifest.read_text());entries=raw['migrations']
    if len(entries)!=1 or {key:entries[0].get(key) for key in ['number','from_schema','to_schema','compatibility','path']}!={'number':145,'from_schema':144,'to_schema':145,'compatibility':'forward-compatible','path':'web/database/migrations/'+NAME}:
        raise ValueError('Academy admin candidate transition invalid')
    original=root/entries[0]['path'];mirror=root/'web/supabase/migrations'/NAME
    if original.read_bytes()!=mirror.read_bytes() or hashlib.sha256(original.read_bytes()).hexdigest()!=entries[0]['sha256']:
        raise ValueError('Academy admin SQL mirror or checksum invalid')
    value=json.loads(bridge.read_text())
    if value['schema']!={'compatible_min':144,'compatible_max':145,'target':145,'migration_class':'forward-compatible','rollback_compatible_min':144,'rollback_compatible_max':144} or value['migration_manifest']!=manifest.name:
        raise ValueError('Academy admin branch compatibility invalid')
    return entries
