#!/usr/bin/env python3
"""Validate the reserved learning route without granting schema authority."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "madar_learning_path", Path(__file__).resolve().parents[1] /
    "deployment/lib/learning_migration_path.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
load_contract, MANIFEST_PATH, SQL_PATH = module.load_contract, module.MANIFEST_PATH, module.SQL_PATH


def validate(root=ROOT):
    contract = load_contract(root)
    if contract["status"] == "reserved":
        paths = [root / MANIFEST_PATH, root / SQL_PATH,
                 root / SQL_PATH.replace("/database/", "/supabase/")]
        if any(path.exists() for path in paths):
            raise ValueError("unfinalized learning migration artifacts present")
    else:
        import json
        module.authorize_manifest(root, root / MANIFEST_PATH, json.loads((root / MANIFEST_PATH).read_text()))
    normal = root / module.NORMAL_CONTRACT_PATH
    if normal.exists():
        import json
        manifest = root / module.NORMAL_MANIFEST_PATH
        module.authorize_normal_manifest(root,manifest,json.loads(manifest.read_text()))
    return contract


if __name__ == "__main__":
    validate()
    print("Learning141→143 exact candidate PASS;142 excluded, active release unchanged")
