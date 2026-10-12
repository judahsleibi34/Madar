"""Exact unselected academy owner tools metadata, never execution authority."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "a0d35ff35e9b97bb49124326c98b0cb0405c2b202f741c8bd5c9dc2ef428da00"
BRIDGE_SHA256 = "70eb3bf15dd73f1296018aef0c870e65f5bc31b83dd2b397fa90d7c489f4f8cf"


def validated_entries(root):
    release = Path(root) / 'web/deployment/releases'
    manifest = release / 'migrations-115-140.json'
    bridge = release / 'schema-114-140-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError('retained academy owner tools metadata changed')
    entries = json.loads(manifest.read_text())['migrations']
    old = json.loads((release / 'migrations-115-139.json').read_text())['migrations']
    expected = {'number':140, 'from_schema':139, 'to_schema':140, 'compatibility':'forward-compatible', 'path':'web/database/migrations/140_complete_academy_owner_tools.sql'}
    if entries[:-1] != old or any(entries[-1].get(key) != value for key,value in expected.items()):
        raise ValueError('retained academy owner tools history invalid')
    database = Path(root) / entries[-1]['path']
    supabase = Path(root) / 'web/supabase/migrations/140_complete_academy_owner_tools.sql'
    if database.read_bytes() != supabase.read_bytes() or hashlib.sha256(database.read_bytes()).hexdigest() != entries[-1]['sha256']:
        raise ValueError('retained academy owner tools SQL mirror/checksum invalid')
    return entries[-1:]
