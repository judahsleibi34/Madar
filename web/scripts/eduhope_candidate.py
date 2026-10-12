"""Validate the exact unselected EduHope candidate; grants no migration authority."""
from pathlib import Path
import hashlib
import json

MANIFEST_SHA256 = "920edf677789df210282ea3c781b9caa85e4a35014e2bd5805598a6f45b54326"
BRIDGE_SHA256 = "301ff5866756c1e16b8065c908b85b247bb76d2f437df74f9dd29c5dbeff85ea"


def validated_entries(root):
    release = Path(root) / 'web/deployment/releases'
    manifest = release / 'migrations-115-138.json'
    bridge = release / 'schema-114-138-bridge.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError('retained EduHope candidate metadata changed')
    entries = json.loads(manifest.read_text())['migrations']
    old = json.loads((release / 'migrations-115-136.json').read_text())['migrations']
    if entries[:-2] != old or [entry['number'] for entry in entries[-2:]] != [137, 138]:
        raise ValueError('retained EduHope history invalid')
    expected = {137: '137_connect_learning_notifications.sql', 138: '138_add_academy_programme_workflows.sql'}
    for entry in entries[-2:]:
        number = entry['number']; filename = expected[number]
        if entry['from_schema'] != number - 1 or entry['to_schema'] != number or entry['compatibility'] != 'forward-compatible' or entry['path'] != 'web/database/migrations/' + filename:
            raise ValueError('retained EduHope transition invalid')
        database = Path(root) / 'web/database/migrations' / filename
        supabase = Path(root) / 'web/supabase/migrations' / filename
        if database.read_bytes() != supabase.read_bytes() or hashlib.sha256(database.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('retained EduHope SQL mirror/checksum invalid')
    return entries[-2:]
