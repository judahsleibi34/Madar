#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone

from database import service_supabase
from services.storage_quota_service import finish_storage


def main() -> int:
    parser = argparse.ArgumentParser(description="Release expired storage reservations")
    parser.add_argument("--apply", action="store_true", help="release reservations (default is dry-run)")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    response = service_supabase.table("storage_reservations").select("id").eq(
        "status", "reserved"
    ).lte("expires_at", datetime.now(timezone.utc).isoformat()).limit(
        max(1, min(args.limit, 500))
    ).execute()
    rows = getattr(response, "data", None) or []
    released = 0
    if args.apply:
        for row in rows:
            finish_storage(reservation_id=row["id"], succeeded=False)
            released += 1
    print(json.dumps({"dry_run": not args.apply, "expired": len(rows), "released": released}, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
