"""Exact unselected E-Learning Forms metadata, never execution authority."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "8ca627c64e8f1149551eea795405c63705b828af2eb0b706796fa8052a809131"
BRIDGE_SHA256 = "0a7dc71ed516e29e544b401064aa929090b83bd5582b4d91ca5378666a3424cd"


def validated_entries(root):
    release = Path(root) / 'web/deployment/releases'
    manifest = release / 'migrations-115-141.json'
    bridge = release / 'schema-114-141-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError('retained E-Learning Forms metadata changed')
    entries = json.loads(manifest.read_text())['migrations']
    old = json.loads((release / 'migrations-115-140.json').read_text())['migrations']
    expected = {'number':141, 'from_schema':140, 'to_schema':141, 'compatibility':'forward-compatible', 'path':'web/database/migrations/141_add_elearning_forms.sql'}
    if entries[:-1] != old or any(entries[-1].get(key) != value for key,value in expected.items()):
        raise ValueError('retained E-Learning Forms history invalid')
    database = Path(root) / entries[-1]['path']
    supabase = Path(root) / 'web/supabase/migrations/141_add_elearning_forms.sql'
    if database.read_bytes() != supabase.read_bytes() or hashlib.sha256(database.read_bytes()).hexdigest() != entries[-1]['sha256']:
        raise ValueError('retained E-Learning Forms SQL mirror/checksum invalid')
    return entries[-1:]
