#!/usr/bin/env python3
"""Read-only tenant commercial-state inventory for operator plan mapping.

This command never writes a subscription.  Its JSON output deliberately shows
current records and observed feature usage without proposing or assigning a
commercial plan.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from database import service_supabase


def rows(table: str, columns: str, tenant_id: int | None = None) -> list[dict]:
    query = service_supabase.table(table).select(columns)
    if tenant_id is not None:
        query = query.eq("tenant_id", tenant_id)
    return [item for item in (query.limit(10000).execute().data or []) if isinstance(item, dict)]


def build_report() -> dict:
    tenants = rows("tenants", "tenant_id,name")
    report = []
    for tenant in sorted(tenants, key=lambda item: int(item["tenant_id"])):
        tenant_id = int(tenant["tenant_id"])
        subscriptions = rows(
            "tenant_subscriptions",
            "id,plan_id,state,catalog_version,source,period_start,period_end,updated_at",
            tenant_id,
        )
        addons = rows(
            "tenant_addons",
            "id,addon_id,state,quantity,catalog_version,updated_at",
            tenant_id,
        )
        legacy = rows(
            "features",
            "id,subscription_type,plan,builder_type,payment_status,updated_at",
            tenant_id,
        )
        usage = {
            "builder_projects": len(rows("builder_projects", "id", tenant_id)),
            "published_sites": len([
                item for item in rows("website_settings", "id,published_project_id", tenant_id)
                if item.get("published_project_id")
            ]),
            "storage_objects": len(rows("tenant_storage_objects", "id", tenant_id)),
        }
        report.append({
            "tenant_id": tenant_id,
            "tenant_name": tenant.get("name"),
            "canonical_subscriptions": subscriptions,
            "canonical_addons": addons,
            "legacy_features": legacy,
            "observed_usage_counts": usage,
            "operator_mapping_required": not any(
                str(item.get("state") or "").lower() in {"active", "trial", "grace"}
                for item in subscriptions
            ),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_dry_run",
        "tenant_count": len(report),
        "tenants": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()
    payload = json.dumps(build_report(), indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "x", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
