#!/usr/bin/env python3
"""Create deterministic signed JWT fixtures for the local staging gateway."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


def encode(payload: dict, secret: str) -> str:
    def part(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    signing = f"{part({'alg':'HS256','typ':'JWT'})}.{part(payload)}"
    signature = hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest()
    return f"{signing}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


if __name__ == "__main__":
    secret = os.environ["STAGING_JWT_SECRET"]
    now = int(time.time())
    common = {"iss": "madar-staging", "iat": now, "exp": now + 86400}
    print("STAGING_ANON_JWT=" + encode({**common, "role": "anon"}, secret))
    print("STAGING_SERVICE_JWT=" + encode({**common, "role": "service_role"}, secret))
