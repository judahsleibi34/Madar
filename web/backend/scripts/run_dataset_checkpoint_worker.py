#!/usr/bin/env python3
"""Run one bounded internal checkpoint reconciliation/materialization batch.

This command does not schedule itself. Production use requires a separately
reviewed supervised scheduler or singleton worker deployment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.project_dataset_checkpoint_service import (
    background_checkpoints_available,
    claim_dataset_checkpoints,
    materialize_claimed_checkpoint,
    reconcile_expired_checkpoints,
)


async def run(*, limit: int, lease_seconds: int) -> dict:
    worker_id = f"dataset-checkpoint:{socket.gethostname()}:{os.getpid()}"
    reconciled = reconcile_expired_checkpoints(
        worker_id=f"{worker_id}:reconcile", limit=limit,
        lease_seconds=min(lease_seconds, 600),
    )
    claimed = claim_dataset_checkpoints(
        worker_id=worker_id, limit=limit, lease_seconds=lease_seconds,
    )
    results = []
    for checkpoint in claimed:
        results.append(await materialize_claimed_checkpoint(
            checkpoint, lease_seconds=lease_seconds,
        ))
    return {"available": True, "reconciled": reconciled,
            "claimed": len(claimed), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--lease-seconds", type=int, default=900)
    args = parser.parse_args()
    if not background_checkpoints_available():
        print(json.dumps({"available": False, "claimed": 0, "results": []}, sort_keys=True))
        return 0
    result = asyncio.run(run(
        limit=max(1, min(args.limit, 20)),
        lease_seconds=max(60, min(args.lease_seconds, 3600)),
    ))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
