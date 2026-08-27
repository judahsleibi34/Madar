#!/usr/bin/env python3
"""Create a private, disposable staging runtime without production secrets."""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

from create_tokens import encode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_root", type=Path)
    parser.add_argument("--release-sha", required=True)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    if root == Path("/") or root == Path.home() or "/saas/Madar" in str(root):
        raise SystemExit("runtime root must be a dedicated disposable path outside repositories")
    if len(args.release_sha) != 40 or any(char not in "0123456789abcdef" for char in args.release_sha):
        raise SystemExit("release SHA must be a full lowercase Git SHA")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    for relative in (
        "state", "backups", "storage/uploads", "storage/avatar_uploads",
        "storage/private_uploads", "storage/private_generated_charts",
    ):
        path = root / relative
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)
    jwt_secret = secrets.token_urlsafe(48)
    common = {"iss": "madar-staging", "iat": 1_787_642_400, "exp": 1_790_234_400}
    anon = encode({**common, "role": "anon"}, jwt_secret)
    service = encode({**common, "role": "service_role"}, jwt_secret)
    values = {
        "STAGING_JWT_SECRET": jwt_secret,
        "STAGING_ANON_JWT": anon,
        "STAGING_SERVICE_JWT": service,
        "SUPABASE_URL": "http://host.docker.internal:15430",
        "SUPABASE_ANON_KEY": anon,
        "SUPABASE_SERVICE_KEY": service,
        "CSRF_SECRET": secrets.token_urlsafe(48),
        "FRONTEND_URLS": "http://127.0.0.1:13000",
        "VITE_API_URL": "http://127.0.0.1:18001",
        "CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:13000",
        "COOKIE_SECURE": "true",
        "COOKIE_SAMESITE": "lax",
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_FAIL_OPEN": "false",
        "ADMIN_MFA_LOGIN_ENFORCEMENT": "true",
        "EMAIL_CHANNEL_ENABLED": "false",
        "REDIS_URL": "redis://redis:6379/0",
        "MADAR_RELEASE_SHA": args.release_sha,
        "MADAR_BUILD_TIMESTAMP": "staging-runtime",
        "SCHEMA_COMPATIBLE_MIN": "81",
        "SCHEMA_COMPATIBLE_MAX": "83",
        "METRICS_TOKEN": secrets.token_urlsafe(32),
        "STRUCTURED_LOGS": "true",
    }
    env_path = root / "staging.env"
    descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for name, value in values.items():
            handle.write(f"{name}={value}\n")
    print(env_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
