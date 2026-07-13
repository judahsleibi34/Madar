#!/usr/bin/env python3
"""Dry-run-first cleanup for expired, unverified pending accounts."""

import argparse
import json

from services.account_lifecycle_service import cleanup_stale_pending_accounts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect expired pending accounts; deletion requires --apply.",
    )
    parser.add_argument("--apply", action="store_true", help="Delete eligible accounts.")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    result = cleanup_stale_pending_accounts(
        dry_run=not args.apply,
        limit=args.limit,
    )
    print(json.dumps(result, sort_keys=True))
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
