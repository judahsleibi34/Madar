#!/usr/bin/env python3
"""Require explicit inventory classification for privileged application clients.

This checks inventory completeness, not authorization correctness. Route and SQL
isolation tests remain mandatory; workers and service callers need review too.
"""
import ast
import json
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
root = repo / "web/backend"
client_names = {"service_supabase", "admin_supabase", "supabase_admin"}
found = set()
for path in root.rglob("*.py"):
    if any(part in {"tests", "scripts", "__pycache__"} for part in path.relative_to(root).parts):
        continue
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    references = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name): references.add(node.id)
        elif isinstance(node, ast.Attribute): references.add(node.attr)
        elif isinstance(node, ast.alias): references.add(node.name)
    if references & client_names:
        found.add(str(path.relative_to(repo)))
manifest = json.loads((repo / "docs/master-implementation-2026-09-08/privileged-access-inventory.json").read_text())
entries = manifest["entries"]
expected = {entry["path"] for entry in entries}
if len(expected) != len(entries) or any(not entry.get("boundary") for entry in entries):
    raise SystemExit("Privileged inventory contains duplicate or unclassified entries")
if found != expected:
    print("Unclassified privileged paths:", sorted(found - expected))
    print("Stale inventory paths:", sorted(expected - found))
    raise SystemExit(1)
print(f"Privileged-client inventory complete: {len(found)} application files; authorization requires separate route/SQL checks")
