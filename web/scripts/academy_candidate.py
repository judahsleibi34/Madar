"""Exact unselected academy correction metadata, never execution authority."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "1ed6bc85a4ad4218e4b02bf5450160d3791b23c0ce98c1a2fe93c0d3c59a5085"
BRIDGE_SHA256 = "c06da74ef98352410a6053c059f673912a2f4d16f0b2de919c1d40e40e1016ea"


def validated_entries(root):
    release = Path(root) / 'web/deployment/releases'
    manifest = release / 'migrations-115-139.json'
    bridge = release / 'schema-114-139-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError('retained academy correction metadata changed')
    entries = json.loads(manifest.read_text())['migrations']
    old = json.loads((release / 'migrations-115-138.json').read_text())['migrations']
    expected = {'number':139, 'from_schema':138, 'to_schema':139, 'compatibility':'forward-compatible', 'path':'web/database/migrations/139_generalize_academy_programme_configuration.sql'}
    if entries[:-1] != old or any(entries[-1].get(key) != value for key,value in expected.items()):
        raise ValueError('retained academy correction history invalid')
    database = Path(root) / entries[-1]['path']
    supabase = Path(root) / 'web/supabase/migrations/139_generalize_academy_programme_configuration.sql'
    if database.read_bytes() != supabase.read_bytes() or hashlib.sha256(database.read_bytes()).hexdigest() != entries[-1]['sha256']:
        raise ValueError('retained academy correction SQL mirror/checksum invalid')
    return entries[-1:]
