#!/usr/bin/env python3
"""Bounded, tenant-scoped repair of builder draft/published asset references.

Dry-run by default. Run each page with --apply only after reviewing its output.
No files are deleted; the command only reconciles registry bookkeeping.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import service_supabase
from services.asset_registry_service import (
    _retained_project_references,
    extract_builder_asset_references,
    reconcile_project_asset_references,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--apply", action="store_true", help="write references (default: dry-run)")
    args = parser.parse_args()
    if args.tenant_id < 1 or not 1 <= args.limit <= 100 or args.offset < 0:
        parser.error("tenant-id must be positive, limit 1..100, and offset nonnegative")

    projects = (
        service_supabase.table("builder_projects")
        .select("id,status,draft_schema,published_schema")
        .eq("tenant_id", args.tenant_id).order("id")
        .range(args.offset, args.offset + args.limit - 1).execute().data or []
    )
    results = []
    for project in projects:
        desired = _retained_project_references(
            tenant_id=args.tenant_id,
            draft_schema=project.get("draft_schema"),
            published_schema=project.get("published_schema"),
            status=project.get("status") or "draft",
        )
        existing = (
            service_supabase.table("builder_asset_references")
            .select("asset_id,reference_path").eq("project_id", project["id"]).execute().data or []
        )
        result = {
            "project_id": project["id"],
            "status": project.get("status"),
            "desired_keys": len(desired),
            "draft_storage_keys": sorted(extract_builder_asset_references(
                project.get("draft_schema") or {}, tenant_id=args.tenant_id,
            )),
            "published_storage_keys": sorted(extract_builder_asset_references(
                project.get("published_schema") or {}, tenant_id=args.tenant_id,
            )) if project.get("status") == "published" else [],
            "existing_rows": len(existing),
        }
        if args.apply:
            result.update(reconcile_project_asset_references(
                project_id=project["id"], tenant_id=args.tenant_id,
                schema=project.get("draft_schema") or {},
                published_schema=project.get("published_schema"),
                status=project.get("status") or "draft",
                client=service_supabase,
            ))
        results.append(result)
    print(json.dumps({
        "dry_run": not args.apply, "tenant_id": args.tenant_id,
        "offset": args.offset, "limit": args.limit,
        "projects_scanned": len(projects), "projects": results,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
