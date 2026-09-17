#!/usr/bin/env python3
"""Validate the effective runtime configuration without displaying values."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.runtime_config import validate_runtime_configuration


def main() -> int:
    try:
        configuration = validate_runtime_configuration()
    except RuntimeError as error:
        print(f"Madar runtime configuration: INVALID: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "valid",
        "environment": configuration.environment,
        "release_identity_configured": configuration.release_sha != "development",
        "schema_min": configuration.schema_min,
        "schema_max": configuration.schema_max,
        "email_channel_enabled": configuration.email_channel_enabled,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
