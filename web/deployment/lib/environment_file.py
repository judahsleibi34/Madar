"""Strict, secret-safe environment-file loading for host deployment tools."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import MutableMapping


ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|:)\s*(.*)$")


def load_environment_file(
    path: Path,
    *,
    environ: MutableMapping[str, str] | None = None,
    require_private: bool = True,
) -> set[str]:
    """Load dotenv/YAML-style scalar assignments without ever logging values."""

    target = environ if environ is not None else os.environ
    if not path.is_file():
        raise RuntimeError("deployment_environment_file_missing")
    if require_private and path.stat().st_mode & 0o077:
        raise RuntimeError("deployment_environment_file_permissions_too_broad")

    loaded: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            raise RuntimeError(f"deployment_environment_line_invalid:{line_number}")
        name, raw_value = match.groups()
        value = raw_value.strip()
        if value[:1] in {"'", '"'}:
            try:
                decoded = ast.literal_eval(value)
            except (SyntaxError, ValueError) as error:
                raise RuntimeError(
                    f"deployment_environment_quoted_value_invalid:{line_number}"
                ) from error
            if not isinstance(decoded, str):
                raise RuntimeError(f"deployment_environment_value_not_string:{line_number}")
            value = decoded
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        target.setdefault(name, value)
        loaded.add(name)
    return loaded
