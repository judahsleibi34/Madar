"""Validate the unadmitted additive167 source chain, never execute SQL."""
import hashlib
import json
from pathlib import Path


SQL_SHA256 = "17c4a2405f3579aa596c9a18160a757ba17c73805ab4dc8ded4c003220b1eedc"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validated_entries(root):
    """Checksum-validate this unselected candidate; grant no execution authority."""
    root = Path(root)
    releases = root / "web/deployment/releases"
    manifest = json.loads((releases / "migrations-166-167-account-recovery.json").read_text())
    bridge = json.loads((releases / "schema-166-167-account-recovery-bridge.json").read_text())
    [entry] = manifest["migrations"]
    require(manifest["manifest_version"] == 1 and manifest["release_sha"] == "STAGING", "candidate167_manifest_invalid")
    require(entry["number"] == entry["to_schema"] == 167 and entry["from_schema"] == 166, "candidate167_transition_invalid")
    require(entry["path"] == "web/database/migrations/167_add_account_recovery_hold.sql", "candidate167_sql_path_invalid")
    original = root / entry["path"]
    require(original.read_bytes() == (root / "web/supabase/migrations/167_add_account_recovery_hold.sql").read_bytes(), "candidate167_mirror_invalid")
    require(hashlib.sha256(original.read_bytes()).hexdigest() == entry["sha256"] == SQL_SHA256, "candidate167_checksum_invalid")
    require(entry["compatibility"] == "coordinated", "candidate167_compatibility_invalid")
    require(bridge["migration_manifest"] == "migrations-166-167-account-recovery.json", "candidate167_bridge_manifest_invalid")
    require(bridge["schema"] == {"compatible_min": 166, "compatible_max": 167, "target": 167,
        "migration_class": "coordinated", "rollback_compatible_min": 167, "rollback_compatible_max": 167}, "candidate167_bridge_schema_invalid")
    require(bridge["migration_policy"] == "blocked-pending-account-erasure-acceptance", "candidate167_admission_must_remain_blocked")
    require(bridge["deployment_profile"] == "account-lifecycle166-167-unadmitted", "candidate167_profile_invalid")
    return [entry]


def validate():
    from check_data_sources_staging_chain import validate as validate166
    root = Path(__file__).resolve().parents[2]
    result = validate166()
    validated_entries(root)
    result.update(target_schema=167, customer_admission=False, execution_admitted=False)
    result["transitions"].append("166->167")
    result["manifests"].append("migrations-166-167-account-recovery.json")
    return result


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
