#!/usr/bin/env python3
"""Compare archived baseline/candidate APIs on one synthetic native stack."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request

import manage
from smoke import OPENER, cookie_header

BASELINE_SHA = "876b65e73ea8ceaf398145d8677019184798a95c"


def measure(port, endpoint, headers, *, requests=60):
    def fetch(_index):
        started = time.perf_counter()
        try:
            with OPENER.open(Request(f"http://127.0.0.1:{port}/api{endpoint}", headers=headers), timeout=15) as response:
                response.read()
                status = response.status
        except HTTPError as error:
            with error:
                error.read()
                status = error.code
        except OSError:
            status = 0
        return (time.perf_counter() - started) * 1000, status
    for index in range(3):
        if fetch(index)[1] != 200:
            raise RuntimeError("Benchmark warmup did not return HTTP200")
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch, range(requests)))
    elapsed = time.perf_counter() - started
    ordered = sorted(row[0] for row in rows)
    def percentile(fraction):
        import math
        return round(ordered[max(0, math.ceil(len(rows) * fraction) - 1)], 3)
    return {"requests": requests, "concurrency": 4, "errors": sum(row[1] != 200 for row in rows),
            "p50_ms": percentile(.5), "p95_ms": percentile(.95), "p99_ms": percentile(.99),
            "throughput_rps": round(requests / elapsed, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-source", required=True)
    args = parser.parse_args()
    manage.require_database_marker()
    baseline = Path(args.baseline_source).resolve()
    if not baseline.is_relative_to(Path.home()) or baseline.name != "baseline" or not (baseline / "web/backend/app.py").is_file():
        raise RuntimeError("An owned archived baseline source directory is required")
    manage.attest_resources()
    for service in ("baseline-backend", "baseline-frontend"):
        if manage.docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={manage.PROJECT}",
                         "--filter", f"label=com.docker.compose.service={service}").strip():
            raise RuntimeError("A baseline service is already present; preserve its evidence")
    fixture = json.loads((manage.RUNTIME / "smoke-fixture.json").read_text())
    proxy = (manage.HERE / "frontend.conf").read_text().replace("http://backend:8000/", "http://baseline-backend:8000/")
    manage.private_write("baseline-nginx.conf", proxy, mounted=True)
    label = {"com.madar.staging.owner": manage.OWNER}
    configuration = {"services": {
        "baseline-backend": {
            "image": "madar-backend:b0fdfe049510724c06a04706390cd174ea57a1d1", "pull_policy": "never",
            "user": "65534:65534", "read_only": True, "restart": "no", "networks": ["isolated"],
            "labels": label, "env_file": [str(manage.RUNTIME / "application.env")],
            "environment": {"MADAR_RELEASE_SHA": BASELINE_SHA},
            "volumes": [str(baseline / "web/backend") + ":/app:ro"],
            "tmpfs": ["/tmp:rw,nosuid,nodev,size=256m,mode=1777"], "mem_limit": "1280m", "cpus": 1.5,
            "pids_limit": 256, "security_opt": ["no-new-privileges:true"],
            "healthcheck": {"test": ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"],
                            "interval": "2s", "timeout": "3s", "retries": 30},
            "logging": {"driver": "json-file", "options": {"max-size": "5m", "max-file": "2"}},
        },
        "baseline-frontend": {
            "image": "madar-frontend:b0fdfe049510724c06a04706390cd174ea57a1d1", "pull_policy": "never",
            "entrypoint": ["nginx", "-c", "/staging/nginx.conf", "-g", "daemon off;"],
            "user": "65534:65534", "read_only": True, "restart": "no", "networks": ["isolated", "ingress"],
            "labels": label, "ports": ["127.0.0.1:18082:8080"], "mem_limit": "64m", "cpus": .25, "pids_limit": 128,
            "security_opt": ["no-new-privileges:true"], "tmpfs": ["/tmp:rw,nosuid,nodev,size=32m,mode=1777"],
            "volumes": [str(manage.RUNTIME / "baseline-nginx.conf") + ":/staging/nginx.conf:ro",
                        str(manage.REPOSITORY / "web/frontend/dist") + ":/site:ro",
                        str(manage.RUNTIME / "tls.crt") + ":/staging/tls.crt:ro",
                        str(manage.RUNTIME / "tls.key") + ":/staging/tls.key:ro"],
        },
    }}
    manage.private_write("baseline-compose.json", json.dumps(configuration))
    def compose(*command):
        return manage.compose("--file", str(manage.RUNTIME / "baseline-compose.json"), *command)
    try:
        compose("up", "--no-deps", "-d", "--wait", "--wait-timeout", "90", "baseline-backend", "baseline-frontend")
        report = {"baseline_sha": BASELINE_SHA, "candidate_sha": manage.state()["source_sha"],
                  "conditions": "dedicated4vCPU/5402MiB VM; same native PostgreSQL/Auth/REST/Redis; API1.5CPU/1280MiB; nginx0.25CPU/64MiB; 3warmups,60requests,4clients per endpoint; synthetic data; no other test load",
                  "endpoints": {}}
        for endpoint in ("/health/live", "/auth/user_status", "/admin/users"):
            headers = {} if endpoint == "/health/live" else cookie_header(fixture["cookies"])
            before = measure(18082, endpoint, headers)
            after = measure(18080, endpoint, headers)
            report["endpoints"][endpoint] = {"baseline": before, "candidate": after,
                "p95_change_percent": round((after["p95_ms"] / before["p95_ms"] - 1) * 100, 2)}
        manage.private_write("benchmark-result.json", json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, sort_keys=True))
    finally:
        compose("stop", "--timeout", "15", "baseline-frontend", "baseline-backend")
        compose("rm", "--force", "baseline-frontend", "baseline-backend")


if __name__ == "__main__":
    main()
