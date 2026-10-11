"""Root-controlled write authority for the governed local-provider transition.

The backend mounts the containing directory read-only. Missing, untrusted or
changed authority fails closed; a process environment switch cannot grant writes.
Ordinary deployments that do not participate retain their existing policy.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

AUTHORITY_PATH = Path("/run/madar/business-write-authority/authority.json")


def read_authority() -> dict | None:
    configured = os.getenv("MADAR_BUSINESS_WRITE_AUTHORITY", "")
    contract = os.getenv("MADAR_BUSINESS_WRITE_CONTRACT", "")
    if not configured and not contract:
        return None
    if configured != str(AUTHORITY_PATH) or not re.fullmatch(r"[0-9a-f]{64}", contract):
        raise RuntimeError("business_write_authority_configuration_invalid")
    for path in (AUTHORITY_PATH, *AUTHORITY_PATH.parents):
        stat = path.lstat()
        if path.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o022:
            raise RuntimeError("business_write_authority_untrusted")
    value = json.loads(AUTHORITY_PATH.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("business_write_authority_binding_invalid")
    fields = {"version", "schema", "release_sha", "contract_digest", "mode"}
    version = value.get("version")
    if type(version) is not int or version not in {1, 2}:
        raise RuntimeError("business_write_authority_binding_invalid")
    if version == 2:
        fields |= {"compatible_min", "compatible_max"}
        # This is the reviewed local115->136 bridge, not arbitrary permission
        # to widen an older grant. Root must issue a fresh release-bound grant.
        if (type(value.get("compatible_min")) is not int
                or type(value.get("compatible_max")) is not int
                or value["compatible_min"] != 115 or value["compatible_max"] != 136
                or os.getenv("SCHEMA_COMPATIBLE_MIN") != "115"
                or os.getenv("SCHEMA_COMPATIBLE_MAX") != "136"):
            raise RuntimeError("business_write_authority_binding_invalid")
    if (set(value) != fields
            or type(value.get("schema")) is not int
            or not 115 <= value["schema"] <= (136 if version == 2 else 115)
            or value["release_sha"] != os.getenv("MADAR_RELEASE_SHA")
            or not re.fullmatch(r"[0-9a-f]{40}", str(value["release_sha"]))
            or value["contract_digest"] != contract
            or not isinstance(value["mode"], str) or value["mode"] not in {"READ_ONLY", "NORMAL"}):
        raise RuntimeError("business_write_authority_binding_invalid")
    return value


def restricted() -> bool:
    authority = read_authority()
    return authority is not None and authority["mode"] == "READ_ONLY"
