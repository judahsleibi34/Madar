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
    minimum, maximum = 115, 115
    if type(version) is not int or version not in {1, 2, 3, 4}:
        raise RuntimeError("business_write_authority_binding_invalid")
    if version == 4:
        fields |= {'compatible_min','compatible_max','operation','operation_id','attempt_id',
                   'controller_sha','database_system_identifier','plan_sha256','target_schema'}
        import uuid
        try:attempt_valid=str(uuid.UUID(value.get('attempt_id','')))==value['attempt_id']
        except (ValueError,TypeError,KeyError,AttributeError):attempt_valid=False
        if (value.get('operation')!='policy-governed-automatic-release' or not attempt_valid
                or not re.fullmatch('migration-plan-[a-f0-9]{64}',str(value.get('operation_id')))
                or not re.fullmatch('[a-f0-9]{40}',str(value.get('controller_sha')))
                or value['controller_sha']!=os.getenv('MADAR_RELEASE_CONTROLLER_SHA')
                or not re.fullmatch('[1-9][0-9]{0,31}',str(value.get('database_system_identifier')))
                or value['database_system_identifier']!=os.getenv('MADAR_RELEASE_DATABASE_SYSTEM_IDENTIFIER')
                or not re.fullmatch('[a-f0-9]{64}',str(value.get('plan_sha256')))
                or any(type(value.get(k)) is not int for k in ('compatible_min','compatible_max','target_schema'))
                or not 0<value['compatible_min']<=value['target_schema']<=value['compatible_max']<10**9
                or os.getenv('SCHEMA_COMPATIBLE_MIN')!=str(value['compatible_min'])
                or os.getenv('SCHEMA_COMPATIBLE_MAX')!=str(value['compatible_max'])
                or os.getenv('SCHEMA_EXCLUDED_VERSIONS','')!=''
                or value.get('mode')=='NORMAL' and value.get('schema')!=value['target_schema']):
            raise RuntimeError('business_write_authority_binding_invalid')
        # These bounds belong to the independently verified actual image. No
        # historical160 contract is widened. Root may refresh exact-operation
        # metadata for a still-compatible serving process through its RO mount.
        minimum,maximum=value['compatible_min'],value['compatible_max']
    if version == 3:
        # A distinct exact operation; historical v2 ranges are never widened.
        fields |= {'compatible_min','compatible_max','operation','origin_schema',
                   'controller_sha','migration_manifest_sha256'}
        if (value.get('operation')!='completed-normal-schema146-160-coordinated-release'
                or type(value.get('origin_schema')) is not int or value['origin_schema']!=146
                or type(value.get('compatible_min')) is not int or value['compatible_min']!=146
                or type(value.get('compatible_max')) is not int or value['compatible_max']!=160
                or os.getenv('SCHEMA_COMPATIBLE_MIN')!='146' or os.getenv('SCHEMA_COMPATIBLE_MAX')!='160'
                or os.getenv('SCHEMA_EXCLUDED_VERSIONS','')!=''
                or not re.fullmatch('[0-9a-f]{40}',str(value.get('controller_sha')))
                or value['controller_sha']!=os.getenv('MADAR_RELEASE_CONTROLLER_SHA')
                or value.get('migration_manifest_sha256')!='7633a15a9f531874409577fb9696e472631d3bbde63ae2603be0a4d23ef7c08f'
                or value['migration_manifest_sha256']!=os.getenv('MADAR_RELEASE_MIGRATION_MANIFEST_SHA256')
                or value.get('mode')=='NORMAL' and value.get('schema')!=160):
            raise RuntimeError('business_write_authority_binding_invalid')
        minimum,maximum=146,160
    if version == 2:
        fields |= {"compatible_min", "compatible_max"}
        # Only reviewed bridge ranges are admitted. A new range needs a fresh
        # root-issued source/context-bound grant; no legacy grant is widened.
        if (type(value.get("compatible_min")) is not int
                or type(value.get("compatible_max")) is not int
                or (value["compatible_min"],value["compatible_max"]) not in {(115,136),(136,144),(144,146),(146,148)}
                or os.getenv("SCHEMA_COMPATIBLE_MIN") != str(value["compatible_min"])
                or os.getenv("SCHEMA_COMPATIBLE_MAX") != str(value["compatible_max"])):
            raise RuntimeError("business_write_authority_binding_invalid")
        minimum, maximum = value["compatible_min"],value["compatible_max"]
        if (minimum,maximum) == (136,144) and (
                os.getenv("SCHEMA_EXCLUDED_VERSIONS") != "142" or value.get("schema") == 142):
            raise RuntimeError("business_write_authority_binding_invalid")
        if (minimum,maximum) == (144,146) and (
                os.getenv("SCHEMA_EXCLUDED_VERSIONS", "") != ""
                or value.get("mode") == "NORMAL" and value.get("schema") != 146):
            raise RuntimeError("business_write_authority_binding_invalid")
        if (minimum,maximum) == (146,148) and (
                os.getenv("SCHEMA_EXCLUDED_VERSIONS", "") != ""
                or value.get("mode") == "NORMAL" and value.get("schema") != 148):
            raise RuntimeError("business_write_authority_binding_invalid")
    if (set(value) != fields
            or type(value.get("schema")) is not int
            or not minimum <= value["schema"] <= maximum
            or value["release_sha"] != os.getenv("MADAR_RELEASE_SHA")
            or not re.fullmatch(r"[0-9a-f]{40}", str(value["release_sha"]))
            or value["contract_digest"] != contract
            or not isinstance(value["mode"], str) or value["mode"] not in {"READ_ONLY", "NORMAL"}):
        raise RuntimeError("business_write_authority_binding_invalid")
    return value


def restricted() -> bool:
    authority = read_authority()
    return authority is not None and authority["mode"] == "READ_ONLY"
