#!/usr/bin/env python3
"""Small loopback-only HTTP concurrency probe for the isolated staging stack."""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def request(url: str, timeout: float) -> tuple[int, float, int]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            content = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        content = error.read()
        status = error.code
    except (urllib.error.URLError, TimeoutError, OSError):
        # Transport failures are measurements, not harness crashes. Status 0
        # is deliberately outside the HTTP status space and is included in
        # the error count and status histogram below.
        content = b""
        status = 0
    return status, (time.perf_counter() - started) * 1000, len(content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--expect", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("only loopback HTTP targets are allowed")
    amount = max(1, min(args.requests, 10000))
    concurrency = max(1, min(args.concurrency, 200))
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        rows = list(executor.map(lambda _: request(args.url, args.timeout), range(amount)))
    elapsed = time.perf_counter() - started
    latencies = [row[1] for row in rows]
    errors = sum(row[0] != args.expect for row in rows)
    result = {
        "url_path": parsed.path, "requests": amount, "concurrency": concurrency,
        "expected_status": args.expect, "errors": errors,
        "error_rate": round(errors / amount, 6),
        "throughput_rps": round(amount / elapsed, 2),
        "p50_ms": round(percentile(latencies, 0.50), 2),
        "p95_ms": round(percentile(latencies, 0.95), 2),
        "p99_ms": round(percentile(latencies, 0.99), 2),
        "response_bytes": sorted({row[2] for row in rows}),
        "transport_errors": sum(row[0] == 0 for row in rows),
        "status_counts": dict(sorted(collections.Counter(row[0] for row in rows).items())),
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
