#!/usr/bin/env python3
"""Run one bounded, fenced Business Intelligence report worker batch."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.bi_reporting_service import reporting_available, run_worker_batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--lease-seconds", type=int, default=300)
    args = parser.parse_args()
    if not reporting_available():
        print(json.dumps({"available": False, "claimed": 0, "results": []}, sort_keys=True))
        return 0
    worker_id = f"bi-report:{socket.gethostname()}:{os.getpid()}"
    result = run_worker_batch(worker_id=worker_id, limit=max(1, min(args.limit, 20)),
                              lease_seconds=max(30, min(args.lease_seconds, 1800)))
    print(json.dumps({"available": True, **result}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
