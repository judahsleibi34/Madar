#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^;\s]+)(?:\s*;.*)?$")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pinned(path: Path) -> tuple[dict[str, str], list[str]]:
    result: dict[str, str] = {}
    errors: list[str] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if not match:
            errors.append(f"{path.name}:{number}: dependency must use an exact == pin")
            continue
        name, version = normalize(match.group(1)), match.group(2)
        if name in result and result[name] != version:
            errors.append(f"{path.name}:{number}: conflicting pin for {name}")
        result[name] = version
    return result, errors


def validate_python(requirements: Path, constraints: Path) -> list[str]:
    direct, errors = pinned(requirements)
    locked, lock_errors = pinned(constraints)
    errors.extend(lock_errors)
    for name, version in direct.items():
        if locked.get(name) != version:
            errors.append(f"constraints.txt: {name} must match direct pin {version}")
    return errors


def validate_node(package_json: Path, package_lock: Path) -> list[str]:
    package = json.loads(package_json.read_text(encoding="utf-8"))
    lock = json.loads(package_lock.read_text(encoding="utf-8"))
    errors = []
    if int(lock.get("lockfileVersion") or 0) < 3:
        errors.append("package-lock.json: lockfileVersion 3 or newer is required")
    root = (lock.get("packages") or {}).get("") or {}
    for key in ("dependencies", "devDependencies"):
        if package.get(key, {}) != root.get(key, {}):
            errors.append(f"package-lock.json: root {key} drifted from package.json")
    return errors


def main() -> int:
    errors = validate_python(ROOT / "backend" / "requirements.txt", ROOT / "backend" / "constraints.txt")
    errors.extend(validate_node(ROOT / "frontend" / "package.json", ROOT / "frontend" / "package-lock.json"))
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    if "RUN npm ci" not in dockerfile:
        errors.append("frontend/Dockerfile: npm ci is required")
    backend_dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    if "-c constraints.txt" not in backend_dockerfile:
        errors.append("backend/Dockerfile: constraints.txt must be enforced")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Dependency locks are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
