#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import service_supabase
from services.storage_quota_service import finish_storage
from services.asset_registry_service import cleanup_expired_builder_assets
from services.upload_config import get_public_uploads_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Release expired storage reservations")
    parser.add_argument("--apply", action="store_true", help="release reservations (default is dry-run)")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--include-assets", action="store_true")
    parser.add_argument("--lock-file", default="/tmp/madar-storage-reconcile.lock")
    args = parser.parse_args()
    limit = max(1, min(args.limit, 500))
    lock_path = Path(args.lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "skipped", "reason": "reconciliation_already_running"}, sort_keys=True))
            return 75
        response = service_supabase.table("storage_reservations").select("id,tenant_id,user_id,category,bytes,expires_at").eq(
            "status", "reserved"
        ).lte("expires_at", datetime.now(timezone.utc).isoformat()).limit(limit).execute()
        rows = getattr(response, "data", None) or []
        released = 0
        if args.apply:
            for row in rows:
                finish_storage(reservation_id=row["id"], succeeded=False)
                released += 1
        assets = {"eligible": 0, "deleted": 0, "skipped": 0}
        if args.include_assets:
            assets = cleanup_expired_builder_assets(
                storage_root=get_public_uploads_dir(), limit=limit,
                dry_run=not args.apply,
            )
        print(json.dumps({
            "status": "complete", "dry_run": not args.apply,
            "expired_reservations": len(rows), "released_reservations": released,
            "assets": assets, "batch_limit": limit,
        }, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
