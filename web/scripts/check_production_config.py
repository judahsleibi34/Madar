#!/usr/bin/env python3
"""Secret-safe production and isolated-E2E configuration shape validator."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")


def load_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            raise RuntimeError(f"environment_line_invalid:{path.name}:{number}")
        name, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def absolute_non_root(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and path.is_absolute() and str(path) != "/"


def safe_https_origins(value: str) -> bool:
    origins = [item.strip() for item in value.split(",") if item.strip()]
    if not origins:
        return False
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or "*" in origin
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            return False
    return True


def absolute_http_url(value: str, *, https_only: bool = False) -> bool:
    parsed = urlsplit(value)
    schemes = {"https"} if https_only else {"http", "https"}
    return bool(
        parsed.scheme in schemes
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )


def absolute_https_origin(value: str) -> bool:
    parsed = urlsplit(value)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def classify(values: dict[str, str], e2e: dict[str, str]) -> list[tuple[str, str]]:
    checks: list[tuple[str, str]] = []

    def required(name: str, valid=lambda value: bool(value.strip())) -> None:
        value = values.get(name, "")
        checks.append((name, "MISSING" if not value.strip() else "PASS" if valid(value) else "INVALID"))

    for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"):
        required(name, absolute_http_url if name == "SUPABASE_URL" else lambda value: len(value.strip()) >= 16)
    database_url = values.get("SUPABASE_DB_URL", "").strip()
    pg_names = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE")
    if database_url:
        database_status = "PASS" if urlsplit(database_url).scheme in {"postgres", "postgresql"} else "INVALID"
    elif all(values.get(name, "").strip() for name in pg_names):
        database_status = "PASS" if values["PGPORT"].isdigit() else "INVALID"
    else:
        database_status = "MISSING"
    checks.append(("DATABASE_CONNECTION", database_status))

    for name in ("VITE_API_URL", "PUBLIC_API_URL", "FRONTEND_PRIMARY_URL"):
        required(name, absolute_https_origin)
    required("FRONTEND_URLS", safe_https_origins)
    required("MADAR_STORAGE_ROOT", absolute_non_root)
    required("COOKIE_SECURE", lambda value: value.strip().lower() == "true")
    required("COOKIE_SAMESITE", lambda value: value.strip().lower() in {"strict", "lax", "none"})
    required("CSRF_TRUSTED_ORIGINS", safe_https_origins)
    required("CSRF_SECRET", lambda value: len(value) >= 32)
    required(
        "MADAR_CSP_CONNECT_SRC",
        lambda value: (
            absolute_https_origin(value)
            and value.rstrip("/") == values.get("VITE_API_URL", "").strip().rstrip("/")
        ),
    )
    required("REDIS_URL", lambda value: value.startswith(("redis://", "rediss://")))
    required("ADMIN_MFA_LOGIN_ENFORCEMENT", lambda value: value.strip().lower() == "true")

    telemetry = values.get("PYGWALKER_TELEMETRY_ENABLED", "").strip().lower()
    checks.append(("PYGWALKER_TELEMETRY_ENABLED", "PASS" if telemetry in {"", "false"} else "INVALID"))

    def e2e_required(name: str, valid=lambda value: bool(value.strip())) -> None:
        value = e2e.get(name, "")
        checks.append((name, "MISSING" if not value.strip() else "PASS" if valid(value) else "INVALID"))

    e2e_required("TEST_USER_EMAIL", lambda value: "@" in value and " " not in value)
    e2e_required("TEST_USER_PASSWORD")
    e2e_required("PUBLISHED_FORM_PATH", lambda value: value.startswith("/") and not value.startswith("//"))
    e2e_required("MADAR_E2E_CONFIRM_ISOLATED", lambda value: value == "YES")
    e2e_required("MADAR_E2E_BASE_URL", absolute_http_url)
    e2e_required("MADAR_E2E_DATABASE_ID", lambda value: value.lower().startswith("madar_e2e_") and not any(label in re.split(r"[_-]", value.lower()) for label in ("production", "prod", "main", "shared", "live")))
    e2e_required("MADAR_E2E_RUN_ID", lambda value: bool(RUN_ID.fullmatch(value)))
    e2e_required("MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN", lambda value: value == "YES")
    e2e_required("MADAR_E2E_EXTERNAL_DELIVERY_DISABLED", lambda value: value == "YES")
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-env", type=Path, required=True)
    parser.add_argument("--e2e-env", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        checks = classify(load_values(args.production_env), load_values(args.e2e_env))
    except RuntimeError as error:
        print(f"INVALID CONFIG_FILE {error}")
        return 1
    for name, status in checks:
        print(f"{status} {name}")
    return 0 if all(status == "PASS" for _, status in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
