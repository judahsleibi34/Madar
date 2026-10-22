#!/usr/bin/env python3
"""Run one bounded source-ingestion reconciliation batch.

This is an internal service-role operation. It is intentionally not exposed as
an HTTP endpoint and does not schedule itself.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.project_source_ingestion_service import reconcile_stale_ingestions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--lease-seconds", type=int, default=900)
    args = parser.parse_args()
    worker_id = f"source-ingestion-reconciler:{socket.gethostname()}:{os.getpid()}"
    result = reconcile_stale_ingestions(
        worker_id=worker_id,
        limit=max(1, min(args.limit, 100)),
        lease_seconds=max(60, min(args.lease_seconds, 3600)),
    )
    counts: dict[str, int] = {}
    for item in result.get("results", []):
        outcome = str(item.get("outcome") or "unknown")
        counts[outcome] = counts.get(outcome, 0) + 1
    print(json.dumps({
        "available": bool(result.get("available")),
        "claimed": int(result.get("claimed") or 0),
        "outcomes": counts,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
