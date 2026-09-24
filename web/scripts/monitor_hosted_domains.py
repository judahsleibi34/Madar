#!/usr/bin/env python3
"""Read-only public synthetic checks for Madar's canonical hosted domain."""

from __future__ import annotations

import json
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable


DOMAIN = "madarportal.com"
TENANT = "madar-demo"
TIMEOUT_SECONDS = 4
MAX_VERSION_BYTES = 8192
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        return None


def _response_headers(items) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in items:
        key = name.lower()
        headers[key] = f"{headers[key]}; {value}" if key in headers else value
    return headers


def fetch(url: str, *, read_version: bool = False) -> dict:
    """GET a fixed public endpoint without cookies, credentials or redirects."""

    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "User-Agent": "MadarHostedDomainMonitor/1"},
        method="GET",
    )
    # Ignore ambient proxy settings, which could carry credentials or test a
    # different route from the public Cloudflare path.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return {
                "code": response.status,
                "headers": _response_headers(response.headers.items()),
                "body": response.read(MAX_VERSION_BYTES + 1) if read_version else b"",
            }
    except urllib.error.HTTPError as error:
        # The expected 404 and 308 responses are observations, not exceptions.
        with error:
            return {"code": error.code, "headers": _response_headers(error.headers.items()), "body": b""}


def _header(response: dict, name: str) -> str:
    return next(
        (str(value) for key, value in response["headers"].items() if key.lower() == name.lower()),
        "",
    )


def _version(response: dict) -> dict:
    body = response["body"]
    if not isinstance(body, bytes) or len(body) > MAX_VERSION_BYTES:
        raise ValueError("version_body_invalid")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise ValueError("version_json_invalid") from error
    if not isinstance(data, dict) or not RELEASE_SHA.fullmatch(str(data.get("release_sha", ""))):
        raise ValueError("release_sha_invalid")
    slot = data.get("release_slot")
    if slot not in ("blue", "green"):
        raise ValueError("release_slot_invalid")
    return {"release_sha": data["release_sha"], "release_slot": slot}


def run_monitor(
    *,
    requester: Callable[..., dict] = fetch,
    token_factory: Callable[[], str] = lambda: secrets.token_hex(16),
) -> dict:
    started = time.monotonic()
    token = token_factory()
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("synthetic_token_invalid")
    tenant_host = f"{TENANT}.{DOMAIN}"
    unknown_host = f"monitor-{token}.{DOMAIN}"
    missing_tenant = f"missing-{token}"
    probes: dict[str, dict] = {}
    responses: dict[str, dict] = {}

    def probe(name: str, url: str, expected: int, *, version: bool = False) -> None:
        probe_started = time.monotonic()
        result = {"status": "failed", "http_status": None}
        try:
            response = requester(url, read_version=version)
            responses[name] = response
            result["http_status"] = response["code"]
            if response["code"] == expected:
                result["status"] = "passed"
            else:
                result["error"] = "unexpected_http_status"
        except (OSError, TimeoutError, ValueError, urllib.error.URLError):
            result["error"] = "network_error"
        result["duration_ms"] = round((time.monotonic() - probe_started) * 1000)
        probes[name] = result

    probe("homepage", f"https://{tenant_host}/", 200)
    probe("about", f"https://{tenant_host}/about", 200)
    probe("shop", f"https://{tenant_host}/shop", 200)
    probe("tenant_api_version", f"https://{tenant_host}/api/health/version", 200, version=True)
    probe("bootstrap", f"https://{tenant_host}/api/public/sites/{TENANT}/bootstrap", 200)
    probe("wrong_host", f"https://{unknown_host}/api/public/sites/{TENANT}/bootstrap", 404)
    probe("unknown_tenant", f"https://{unknown_host}/api/public/sites/{missing_tenant}/bootstrap", 404)
    probe("legacy_redirect", f"https://{DOMAIN}/site/{TENANT}/?probe={token}", 308)
    probe("explicit_api_version", f"https://api.{DOMAIN}/health/version", 200, version=True)

    legacy = probes["legacy_redirect"]
    if legacy["status"] == "passed":
        location = _header(responses["legacy_redirect"], "Location")
        if location != f"https://{tenant_host}/?probe={token}":
            legacy.update(status="failed", error="legacy_location_mismatch")

    versions = {}
    for name in ("tenant_api_version", "explicit_api_version"):
        if probes[name]["status"] != "passed":
            continue
        try:
            versions[name] = _version(responses[name])
        except ValueError as error:
            probes[name].update(status="failed", error=str(error))

    identity = {"status": "failed"}
    if len(versions) == 2:
        if versions["tenant_api_version"] == versions["explicit_api_version"]:
            identity["status"] = "passed"
        else:
            identity["error"] = "release_identity_mismatch"
    else:
        identity["error"] = "release_identity_unavailable"
    probes["release_identity"] = identity

    hsts = {"status": "failed"}
    forbidden_hsts = any(
        re.search(
            r"(?:^|;)\s*includesubdomains\s*(?:;|$)",
            _header(response, "Strict-Transport-Security"),
            re.IGNORECASE,
        )
        for response in responses.values()
    )
    if forbidden_hsts:
        hsts["error"] = "include_subdomains_forbidden"
    elif "homepage" in responses:
        value = _header(responses["homepage"], "Strict-Transport-Security")
        if re.search(r"(?:^|;)\s*max-age=[1-9][0-9]*\s*(?:;|$)", value, re.IGNORECASE):
            hsts["status"] = "passed"
        else:
            hsts["error"] = "hsts_max_age_missing"
    else:
        hsts["error"] = "hsts_unavailable"
    probes["hsts"] = hsts

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "healthy" if all(item["status"] == "passed" for item in probes.values()) else "unhealthy",
        "canonical_hostname": tenant_host,
        "probes": probes,
        "observed_release_sha": versions.get("tenant_api_version", {}).get("release_sha"),
        "observed_release_slot": versions.get("tenant_api_version", {}).get("release_slot"),
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def main() -> int:
    try:
        result = run_monitor()
    except Exception:
        # No exception text or HTTP body is ever written to the journal.
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "unhealthy",
            "canonical_hostname": f"{TENANT}.{DOMAIN}",
            "probes": {"monitor": {"status": "failed", "error": "monitor_internal_error"}},
            "observed_release_sha": None,
            "observed_release_slot": None,
            "duration_ms": 0,
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())
