#!/usr/bin/env python3
"""Run one bounded automatic Data Source synchronization batch."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.automatic_source_sync_service import automatic_sync_available, run_batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--tenant-limit", type=int, default=2)
    parser.add_argument("--provider-limit", type=int, default=4)
    args = parser.parse_args()
    if not automatic_sync_available():
        print(json.dumps({"available": False, "claimed": 0, "results": []}, sort_keys=True))
        return 0
    worker_id = f"source-sync:{socket.gethostname()}:{os.getpid()}"
    result = asyncio.run(run_batch(
        worker_id=worker_id, limit=max(1, min(args.limit, 50)),
        lease_seconds=max(60, min(args.lease_seconds, 3600)),
        tenant_limit=max(1, min(args.tenant_limit, 20)),
        provider_limit=max(1, min(args.provider_limit, 50)),
    ))
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
