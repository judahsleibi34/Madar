#!/usr/bin/env python3
import argparse
import json
from services.asset_registry_service import cleanup_expired_builder_assets
from services.upload_config import get_public_uploads_dir

def main() -> int:
    parser = argparse.ArgumentParser(description="Delete registered expired builder assets")
    parser.add_argument("--apply", action="store_true", help="perform deletion (default is dry-run)")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    result = cleanup_expired_builder_assets(storage_root=get_public_uploads_dir(), limit=args.limit, dry_run=not args.apply)
    print(json.dumps({"dry_run": not args.apply, **result}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
