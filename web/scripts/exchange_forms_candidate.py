"""Exact unselected Exchange Forms metadata, never execution authority."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "b125fc51832e8b090c0f4b1ed79fbfe9a80aed827adb7841e18e21a3daf17a63"
BRIDGE_SHA256 = "afe2ef42a048be3e5fd0c65de980473f7a20ed630edfdb2dbf20131611c2cd51"


def validated_entries(root):
    release = Path(root) / 'web/deployment/releases'
    manifest = release / 'migrations-115-142.json'
    bridge = release / 'schema-114-142-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError('retained Exchange Forms metadata changed')
    entries = json.loads(manifest.read_text())['migrations']
    old = json.loads((release / 'migrations-115-141.json').read_text())['migrations']
    expected = {'number':142, 'from_schema':141, 'to_schema':142, 'compatibility':'forward-compatible', 'path':'web/database/migrations/142_exchange_applications_use_learning_forms.sql'}
    if entries[:-1] != old or any(entries[-1].get(key) != value for key,value in expected.items()):
        raise ValueError('retained Exchange Forms history invalid')
    database = Path(root) / entries[-1]['path']
    supabase = Path(root) / 'web/supabase/migrations/142_exchange_applications_use_learning_forms.sql'
    if database.read_bytes() != supabase.read_bytes() or hashlib.sha256(database.read_bytes()).hexdigest() != entries[-1]['sha256']:
        raise ValueError('retained Exchange Forms SQL mirror/checksum invalid')
    return entries[-1:]
