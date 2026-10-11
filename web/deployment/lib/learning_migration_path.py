"""Exact, fail-closed learning-only branch; active release selection is independent.

Finalizing this reservation requires reviewed SQL/manifest digests and a new
descriptor pin in source. Ordinary manifests continue using consecutive versions.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CONTRACT_PATH = "web/deployment/releases/learning-141-143-path.json"
CONTRACT_SHA256 = "0941d244bd1e6102bed6c5c28a7384afa2a145206ca29ef8ec0ae1eb426e6048"
MANIFEST_PATH = "web/deployment/releases/migrations-141-143-learning.json"
SQL_PATH = "web/database/migrations/143_complete_learning_capabilities.sql"
BRIDGE_PATH = "web/deployment/releases/schema-141-143-learning-bridge.json"


def load_contract(repository_root: Path) -> dict:
    path = repository_root / CONTRACT_PATH
    if hashlib.sha256(path.read_bytes()).hexdigest() != CONTRACT_SHA256:
        raise ValueError("learning migration path checksum mismatch")
    contract = json.loads(path.read_text())
    identity = {
        "contract_version": 1, "route": "learning-only-141-143",
        "source_schema": 141, "target_schema": 143, "excluded_schemas": [142],
        "manifest_path": MANIFEST_PATH, "sql_path": SQL_PATH,
    }
    if any(contract.get(key) != value for key, value in identity.items()):
        raise ValueError("learning migration path identity invalid")
    if contract.get("status") == "reserved":
        if (contract.get("manifest_sha256") is not None
                or contract.get("sql_sha256") is not None
                or contract.get("execution_authority") is not False):
            raise ValueError("learning migration reservation invalid")
    elif contract.get("status") == "finalized":
        if (contract.get("execution_authority") is not True
                or any(not isinstance(contract.get(key), str)
                       or not re.fullmatch(r"[0-9a-f]{64}", contract[key])
                       for key in ("manifest_sha256", "sql_sha256", "bridge_sha256"))):
            raise ValueError("learning migration finalization invalid")
        if contract.get("bridge_path") != BRIDGE_PATH:
            raise ValueError("learning bridge identity invalid")
    else:
        raise ValueError("learning migration path status invalid")
    return contract


def authorize_manifest(repository_root: Path, manifest_path: Path, raw: dict) -> None:
    """Accept only the exact finalized, single-transition candidate, never142."""
    contract = load_contract(repository_root)
    if contract["status"] != "finalized":
        raise ValueError("learning migration path is reserved, not executable")
    if manifest_path.resolve() != (repository_root / MANIFEST_PATH).resolve():
        raise ValueError("learning migration manifest path invalid")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != contract["manifest_sha256"]:
        raise ValueError("learning migration manifest checksum mismatch")
    entries = raw.get("migrations")
    expected = {
        "number": 143, "from_schema": 141, "to_schema": 143,
        "path": SQL_PATH, "sha256": contract["sql_sha256"],
        "compatibility": "forward-compatible",
    }
    if entries != [expected]:
        raise ValueError("learning migration manifest transition invalid")
    database = repository_root / SQL_PATH
    mirror = repository_root / SQL_PATH.replace("/database/", "/supabase/")
    if (not database.is_file() or not mirror.is_file()
            or database.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(database.read_bytes()).hexdigest() != contract["sql_sha256"]):
        raise ValueError("learning migration SQL checksum/mirror mismatch")

    bridge = repository_root / BRIDGE_PATH
    if hashlib.sha256(bridge.read_bytes()).hexdigest() != contract['bridge_sha256']:
        raise ValueError('learning bridge checksum mismatch')
    metadata = json.loads(bridge.read_text())
    if metadata.get('schema') != {'compatible_min':141,'compatible_max':143,'target':143,'migration_class':'forward-compatible','rollback_compatible_min':141,'rollback_compatible_max':141,'excluded_versions':[142]} or metadata.get('migration_manifest') != Path(MANIFEST_PATH).name or metadata.get('migration_policy') != 'automatic-after-known-good-backup-first-forward-repair':
        raise ValueError('learning bridge branch compatibility invalid')
