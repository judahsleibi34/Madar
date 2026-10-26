#!/usr/bin/env python3
"""Run one bounded webhook inbox batch; this command never schedules itself."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.webhook_ingestion_service import run_batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--lease-seconds", type=int, default=300)
    args = parser.parse_args()
    worker_id = f"webhook-ingestion:{socket.gethostname()}:{os.getpid()}"
    result = asyncio.run(run_batch(
        worker_id=worker_id, limit=max(1, min(args.limit, 50)),
        lease_seconds=max(60, min(args.lease_seconds, 1800)),
    ))
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
