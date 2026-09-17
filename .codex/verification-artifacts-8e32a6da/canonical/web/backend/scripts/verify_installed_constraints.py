#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
import re
import sys
from pathlib import Path


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_constraints(path: Path) -> dict[str, str]:
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if not separator or not version:
            raise ValueError(f"invalid constraint: {line}")
        result[normalize(name)] = version
    return result


def installed_drift(constraints: dict[str, str]) -> list[str]:
    errors = []
    ignored = {"pip", "setuptools", "wheel"}
    for distribution in importlib.metadata.distributions():
        name = normalize(distribution.metadata["Name"])
        if name in ignored:
            continue
        expected = constraints.get(name)
        if expected is None:
            errors.append(f"installed dependency is not constrained: {name}=={distribution.version}")
        elif expected != distribution.version:
            errors.append(f"installed dependency drift: {name}=={distribution.version}, expected {expected}")
    return sorted(set(errors))


def main() -> int:
    constraints = load_constraints(Path(__file__).resolve().parents[1] / "constraints.txt")
    errors = installed_drift(constraints)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Installed backend dependencies match constraints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
