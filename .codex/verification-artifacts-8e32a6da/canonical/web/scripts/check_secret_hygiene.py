#!/usr/bin/env python3

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

tracked = subprocess.run(
    ["git", "ls-files"],
    cwd=ROOT,
    text=True,
    check=True,
    stdout=subprocess.PIPE,
).stdout.splitlines()

bad: list[str] = []

allowed_suffixes = (
    ".example",
    ".sample",
    ".template",
)

for name in tracked:
    base = Path(name).name.lower()

    if base == ".env" or base.startswith(".env."):
        if not base.endswith(allowed_suffixes):
            bad.append(name)

if bad:
    print("ERROR: tracked environment-secret files are forbidden:")
    for name in bad:
        print(" -", name)
    raise SystemExit(1)

print("Tracked secret-file hygiene PASS")
