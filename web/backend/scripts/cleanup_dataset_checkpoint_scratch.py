#!/usr/bin/env python3
"""Remove only stale checkpoint workspaces beneath the configured private root."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.checkpoint_streaming import cleanup_stale_workspaces


if __name__ == "__main__":
    print(json.dumps({"removed": cleanup_stale_workspaces()}, sort_keys=True))
