#!/usr/bin/env python3
"""Run one bounded recurring-report and data-refresh dispatch pass."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.bi_reporting_service import dispatch_data_refreshes, dispatch_due_schedules, reporting_available


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--now", help="Controlled ISO-8601 clock for isolated tests")
    args = parser.parse_args()
    if not reporting_available():
        print(json.dumps({"available": False, "scheduled": 0, "refresh": 0}, sort_keys=True))
        return 0
    current = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    schedules = dispatch_due_schedules(now=current, limit=max(1, min(args.limit, 20)))
    refreshes = dispatch_data_refreshes(limit=max(1, min(args.limit, 20)))
    print(json.dumps({"available": True, "schedules": schedules, "refreshes": refreshes}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
