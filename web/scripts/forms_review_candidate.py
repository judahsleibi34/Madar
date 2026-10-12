"""Validate the exact unselected143→144 Forms review candidate."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = '11efbeb21be68611d2a06d5e93b6f20f560905e9b64075654889d46581f8eb34'
BRIDGE_SHA256 = '728c766698e0755de90af0b60fee131e69f674c3c7dbb46a153380ea42f56fc7'


def validated_entries(root):
    root=Path(root);release=root/'web/deployment/releases'
    manifest=release/'migrations-143-144-forms.json';bridge=release/'schema-143-144-forms-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest()!=BRIDGE_SHA256:
        raise ValueError('Forms review candidate metadata changed')
    raw=json.loads(manifest.read_text());entries=raw['migrations']
    if len(entries)!=1 or {key:entries[0].get(key) for key in ['number','from_schema','to_schema','compatibility','path']}!={'number':144,'from_schema':143,'to_schema':144,'compatibility':'forward-compatible','path':'web/database/migrations/144_add_generic_learning_form_reviews.sql'}:
        raise ValueError('Forms review candidate transition invalid')
    original=root/entries[0]['path'];mirror=root/'web/supabase/migrations/144_add_generic_learning_form_reviews.sql'
    if original.read_bytes()!=mirror.read_bytes() or hashlib.sha256(original.read_bytes()).hexdigest()!=entries[0]['sha256']:
        raise ValueError('Forms review SQL mirror or checksum invalid')
    value=json.loads(bridge.read_text())
    if value['schema']!={'compatible_min':143,'compatible_max':144,'target':144,'migration_class':'forward-compatible','rollback_compatible_min':143,'rollback_compatible_max':143} or value['migration_manifest']!=manifest.name:
        raise ValueError('Forms review branch compatibility invalid')
    return entries
