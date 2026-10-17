"""Pin the unselected forward-compatible schema147→148 reservation capacity repair."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "1bb6174d75aadc0dc576b2114a9a46e4fcd36da0078132b8a3957c0493809dea"
BRIDGE_SHA256 = "c969b9402d4dd585e87593cb5f0679ae9624482ee92bd6cc82590d53563ceaa3"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-147-148-reservation-capacity.json"
    bridge = release / "schema-147-148-reservation-capacity.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("Reservation capacity candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {"number":148,"from_schema":147,"to_schema":148,"compatibility":"forward-compatible",
                "path":"web/database/migrations/148_guard_reservation_reactivation_capacity.sql"}
    if len(entries) != 1 or {key:entries[0].get(key) for key in expected} != expected:
        raise ValueError("Reservation capacity transition invalid")
    original = root / expected["path"]
    mirror = root / "web/supabase/migrations" / original.name
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("Reservation capacity SQL mirror/checksum invalid")
    value = json.loads(bridge.read_text())
    if (value["schema"] != {"compatible_min":147,"compatible_max":148,"target":148,
            "migration_class":"forward-compatible","rollback_compatible_min":147,"rollback_compatible_max":147}
            or value["migration_policy"] != "none"
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "reservation-reactivation-capacity147-148"):
        raise ValueError("Reservation capacity coordinated compatibility invalid")
    return entries
