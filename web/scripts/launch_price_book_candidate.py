"""Validate the exact unselected 145→146 revised launch price-book candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "9e70b62615bdcf4708ea574a730074a6ec4b01e7d1b2faad8cf636702ae83a0f"
BRIDGE_SHA256 = "21d4a792b2781a1e112bbfb5fff40b58c6a34c519f5292b9076bbc3ffbdb8751"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-145-146-price-book.json"
    bridge = release / "schema-145-146-price-book-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("Launch price-book candidate metadata changed")
    raw = json.loads(manifest.read_text())
    entries = raw["migrations"]
    expected = {
        "number": 146,
        "from_schema": 145,
        "to_schema": 146,
        "compatibility": "forward-compatible",
        "path": "web/database/migrations/146_revise_launch_price_book.sql",
    }
    if len(entries) != 1 or {
        key: entries[0].get(key) for key in expected
    } != expected:
        raise ValueError("Launch price-book candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/146_revise_launch_price_book.sql"
    if (original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("Launch price-book SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 145,
        "compatible_max": 146,
        "target": 146,
        "migration_class": "forward-compatible",
        "rollback_compatible_min": 145,
        "rollback_compatible_max": 145,
    }
    if (value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "revised-launch-price-book145-146"):
        raise ValueError("Launch price-book branch compatibility invalid")
    return entries
