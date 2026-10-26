#!/usr/bin/env python3
"""Bounded outage test of this project's ephemeral Redis, never a shared service."""

import json
import time

import manage
from smoke import http


def main():
    manage.require_database_marker()
    identifier = manage.compose("ps", "-q", "redis").decode().strip()
    resource = json.loads(manage.docker("inspect", identifier))[0]
    assert resource["Config"]["Labels"]["com.madar.staging.owner"] == manage.OWNER
    assert resource["HostConfig"]["Memory"] == 128 * 1024 * 1024
    assert not any(resource["NetworkSettings"]["Ports"].values())
    maximum = manage.docker("exec", identifier, "redis-cli", "--raw", "config", "get", "maxmemory").decode().splitlines()
    eviction = manage.docker("exec", identifier, "redis-cli", "--raw", "config", "get", "maxmemory-policy").decode().splitlines()
    assert maximum == ["maxmemory", str(48 * 1024 * 1024)]
    assert eviction == ["maxmemory-policy", "noeviction"]
    manage.compose("stop", "--timeout", "10", "redis")
    try:
        http("POST", "/auth/login", application=True,
             body={"email": "synthetic-outage@example.com", "password": "invalid-synthetic-fixture"}, expected=(503,))
        deadline = time.monotonic() + 12
        degraded = False
        while time.monotonic() < deadline:
            result, _ = http("GET", "/health/ready", application=True, expected=(200, 503))
            if not result["ready"] and result["components"]["redis"] not in {"ok", "disabled", "optional_unavailable"}:
                degraded = True
                break
            time.sleep(1)
        assert degraded, "Redis outage was not reflected in readiness"
    finally:
        manage.compose("start", "--wait", "--wait-timeout", "45", "redis")
    deadline = time.monotonic() + 15
    recovered = False
    while time.monotonic() < deadline:
        result, _ = http("GET", "/health/ready", application=True, expected=(200, 503))
        if result["ready"]:
            recovered = True
            break
        time.sleep(1)
    assert recovered, "Staging did not recover readiness after the owned Redis restart"
    print("PASS Redis48MiB/noeviction under128MiB cap, no published ports, login fail-closed503, degraded readiness and recovery after controlled outage")


if __name__ == "__main__":
    main()
