#!/usr/bin/env python3
"""Fail-closed audit of the unselected schema136 -> schema156 staging path."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "web/deployment/releases"
EXPECTED = (
    (136, 137, "migrations-137-144-learning.json"),
    (137, 138, "migrations-137-144-learning.json"),
    (138, 139, "migrations-137-144-learning.json"),
    (139, 140, "migrations-137-144-learning.json"),
    (140, 141, "migrations-137-144-learning.json"),
    (141, 143, "migrations-137-144-learning.json"),
    (143, 144, "migrations-137-144-learning.json"),
    (144, 145, "migrations-144-145-commercial.json"),
    (145, 146, "migrations-145-146-price-book.json"),
    (146, 147, "migrations-146-147-project-datasets.json"),
    (147, 148, "migrations-147-148-data-sources.json"),
    (148, 149, "migrations-148-149-source-ingestions.json"),
    (149, 150, "migrations-149-150-source-ingestion-recovery.json"),
    (150, 151, "migrations-150-151-api-source-ingestion.json"),
    (151, 152, "migrations-151-152-incremental-ingestion.json"),
    (152, 153, "migrations-152-153-background-checkpoints.json"),
    (153, 154, "migrations-153-154-shared-immutable-storage.json"),
    (154, 155, "migrations-154-155-credential-vault.json"),
    (155, 156, "migrations-155-156-automatic-source-sync.json"),
)


def _load_validator(filename: str):
    path = ROOT / "web/scripts" / filename
    spec = importlib.util.spec_from_file_location(f"staging_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def validate() -> dict:
    active = json.loads((RELEASES / "release.json").read_text(encoding="utf-8"))
    if active.get("schema", {}).get("target") != 136:
        raise RuntimeError("active_release_target_changed")
    if active.get("migration_manifest") != "migrations-116-136.json":
        raise RuntimeError("active_release_manifest_changed")

    learning = _load_validator("check_learning_migration_path.py")
    learning.validate(ROOT)

    validators = (
        "commercial_continuity_candidate.py",
        "launch_price_book_candidate.py",
        "project_datasets_candidate.py",
        "data_sources_candidate.py",
        "source_ingestions_candidate.py",
        "source_ingestion_recovery_candidate.py",
        "api_source_ingestion_candidate.py",
        "incremental_ingestion_candidate.py",
        "background_checkpoints_candidate.py",
        "shared_immutable_storage_candidate.py",
        "credential_vault_candidate.py",
        "automatic_source_sync_candidate.py",
    )
    for filename in validators:
        _load_validator(filename).validated_entries(ROOT)

    observed: list[tuple[int, int, str]] = []
    seen_manifests: set[str] = set()
    for _source, _target, manifest_name in EXPECTED:
        if manifest_name in seen_manifests:
            continue
        seen_manifests.add(manifest_name)
        manifest = json.loads((RELEASES / manifest_name).read_text(encoding="utf-8"))
        for entry in manifest["migrations"]:
            sql = ROOT / entry["path"]
            mirror = ROOT / str(entry["path"]).replace("/database/", "/supabase/")
            if not sql.is_file() or not mirror.is_file() or sql.read_bytes() != mirror.read_bytes():
                raise RuntimeError(f"migration_mirror_invalid:{entry['number']}")
            if hashlib.sha256(sql.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"migration_checksum_invalid:{entry['number']}")
            observed.append((entry["from_schema"], entry["to_schema"], manifest_name))
    if tuple(observed) != EXPECTED:
        raise RuntimeError(f"staging_transition_path_invalid:{observed!r}")

    if any(source == 142 or target == 142 for source, target, _ in observed):
        raise RuntimeError("excluded_schema142_present")
    return {
        "active_schema": 136,
        "target_schema": 156,
        "excluded_schemas": [142],
        "transitions": [f"{source}->{target}" for source, target, _ in observed],
        "manifests": sorted(seen_manifests),
        "active_release_unchanged": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
