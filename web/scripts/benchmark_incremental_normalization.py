#!/usr/bin/env python3
"""Measured bounded synthetic normalization benchmark; no network or database access."""
from __future__ import annotations

import json
import sys
import time
import tracemalloc
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.data_source_api_provider import (  # noqa: E402
    ProviderPage,
    ProviderRecord,
    fetch_bounded_records,
)


class BenchmarkProvider:
    provider_key = "benchmark"
    supported_resources = frozenset({"records"})

    def fetch_page(self, request):
        page = int(request.continuation or 0)
        start = page * 1_000
        records = tuple(
            ProviderRecord(
                f"record-{index:08d}",
                {"amount": index, "name": f"Synthetic {index}", "active": True},
                source_order=1,
            )
            for index in range(start, start + 1_000)
        )
        return ProviderPage(records, str(page + 1) if page < 9 else None)

    def next_cursor(self, _resource_type, _current_cursor):
        return "benchmark:10000"


def main() -> None:
    tracemalloc.start()
    started = time.perf_counter()
    batch = fetch_bounded_records(BenchmarkProvider(), resource_type="records")
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps({
        "records": batch.record_count,
        "pages": batch.page_count,
        "elapsed_seconds": round(elapsed, 6),
        "records_per_second": round(batch.record_count / elapsed, 2),
        "change_chunk_bytes": len(batch.csv_bytes),
        "peak_python_bytes": peak,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
