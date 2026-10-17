"""Pin the unselected coordinated schema146→147 notification worker cutover."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "b79ac76d9e64199260172c73813d72f41e13504f2afef53c264ed2c507edf581"
BRIDGE_SHA256 = "ecd561f159cb8e04af01ee4a4e6e30dde1bad653a595f1ab7ac1970b31f65586"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-146-147-notification-fencing.json"
    bridge = release / "schema-146-147-notification-fencing.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("Notification fencing candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {"number":147,"from_schema":146,"to_schema":147,"compatibility":"coordinated",
                "path":"web/database/migrations/147_fence_notification_delivery_claims.sql"}
    if len(entries) != 1 or {key:entries[0].get(key) for key in expected} != expected:
        raise ValueError("Notification fencing transition invalid")
    original = root / expected["path"]
    mirror = root / "web/supabase/migrations" / original.name
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("Notification fencing SQL mirror/checksum invalid")
    value = json.loads(bridge.read_text())
    if (value["schema"] != {"compatible_min":147,"compatible_max":147,"target":147,
            "migration_class":"coordinated","rollback_compatible_min":147,"rollback_compatible_max":147}
            or value["migration_policy"] != "none"
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "notification-claim-fencing146-147"):
        raise ValueError("Notification fencing coordinated compatibility invalid")
    return entries
