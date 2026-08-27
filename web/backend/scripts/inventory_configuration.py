#!/usr/bin/env python3
"""Generate a redaction-safe inventory of environment keys read by backend source."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.runtime_config import redacted_configuration_inventory


def observed_keys(root: Path) -> set[str]:
    keys: set[str] = set()
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            is_getenv = isinstance(function, ast.Attribute) and function.attr == "getenv"
            is_environ_get = (
                isinstance(function, ast.Attribute) and function.attr == "get"
                and isinstance(function.value, ast.Attribute) and function.value.attr == "environ"
            )
            if (is_getenv or is_environ_get) and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                if isinstance(value, str) and value.isupper():
                    keys.add(value)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    inventory = redacted_configuration_inventory(observed_keys(args.root.resolve()))
    counts = Counter(str(row["classification"]) for row in inventory)
    if args.format == "json":
        print(json.dumps({"counts": dict(sorted(counts.items())), "keys": inventory}, sort_keys=True))
    else:
        print("| Key | Classification | Configured |\n| -- | -- | -- |")
        for row in inventory:
            print(f"| `{row['name']}` | {row['classification']} | {str(row['configured']).lower()} |")
        print(f"\nTotal: {len(inventory)}; unknown: {counts.get('unknown', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
