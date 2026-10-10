#!/usr/bin/env python3
"""Validate Madar's parallel SQL migration trees without applying migrations."""

from __future__ import annotations

import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TREE_PATHS = {
    "database": REPO_ROOT / "database" / "migrations",
    "supabase": REPO_ROOT / "supabase" / "migrations",
}
FILENAME_PATTERN = re.compile(r"^(?P<number>\d{3})_(?P<description>[a-z0-9][a-z0-9_]*)\.sql$")
NEXT_MIGRATION_NUMBER = 44

HISTORICAL_COMMON_FILES = {
    "001_initial_schema.sql",
    "002_add_user_profile_fields.sql",
    "003_create_website_settings.sql",
    "006_create_get_columns_function.sql",
    "007_add_tenant_id_to_website_settings.sql",
    "008_grant_select_on_tenants.sql",
    "009_make_contact_email_optional.sql",
    "010_drop_email_from_contacts.sql",
    "011_add_phone_to_contacts.sql",
    "012_add_subscription_fields_to_users.sql",
    "013_fix_tenant_relationships.sql",
    "014_fix_tenant_relationships.sql",
    "015_fix_tenant_id_links.sql",
    "016_create_features_table.sql",
    "017_grant_features_permissions.sql",
    "018_fix_features_unique_indexes_updated.sql",
    "019_fix_signup_tenant_foundation.sql",
    "020_precheck_users_identity_duplicates.sql",
    "021_enforce_unique_users_identity.sql",
    "022_create_avatars_storage_bucket.sql",
    "023_add_user_type_to_users.sql",
    "024_create_builder_projects.sql",
    "025_harden_website_settings_rls.sql",
    "026_set_user_1_as_admin.sql",
    "027_create_builder_form_submissions.sql",
    "028_update_builder_form_submission_statuses.sql",
    "029_harden_features_rls.sql",
    "030_create_audit_logs.sql",
    "031_add_business_type_to_tenants.sql",
    "032_repair_onboarding_builder_schema.sql",
    "033_create_user_security_settings.sql",
    "034_harden_website_settings_rls_tenant_only.sql",
    "035_create_admin_account_access.sql",
    "036_restore_original_signup_foundation.sql",
    "037_create_ai_usage_daily.sql",
    "038_create_notifications.sql",
    "039_create_ai_usage_reservation.sql",
    "040_add_user_email_verification_status.sql",
    "041_add_password_reset_request_timestamp.sql",
    "042_create_tenant_site_memberships.sql",
    "043_create_account_lifecycle.sql",
}

HISTORICAL_FILES = {
    "database": HISTORICAL_COMMON_FILES
    | {
        "004_enable_rls_policies.sql",
        "005_create_get_tables_function.sql",
    },
    "supabase": HISTORICAL_COMMON_FILES
    | {
        "004_create_get_tables_function.sql",
        "005_enable_rls_policies.sql",
    },
}

GRANDFATHERED_DUPLICATES = {}

SWAPPED_FILES = (
    (
        "database/004_enable_rls_policies.sql",
        "supabase/005_enable_rls_policies.sql",
    ),
    (
        "database/005_create_get_tables_function.sql",
        "supabase/004_create_get_tables_function.sql",
    ),
)

SWAPPED_NAMES = {
    "database": {
        "004_enable_rls_policies.sql",
        "005_create_get_tables_function.sql",
    },
    "supabase": {
        "004_create_get_tables_function.sql",
        "005_enable_rls_policies.sql",
    },
}

TENANT_RELATIONSHIP_DUPLICATES = (
    "013_fix_tenant_relationships.sql",
    "014_fix_tenant_relationships.sql",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_tree(label: str, directory: Path, errors: list[str]) -> dict[str, Path]:
    if not directory.is_dir():
        errors.append(f"{label}: migration directory is missing: {directory}")
        return {}

    files: dict[str, Path] = {}
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            errors.append(f"{label}: unexpected non-file entry: {path.name}")
            continue
        if not FILENAME_PATTERN.fullmatch(path.name):
            errors.append(
                f"{label}: malformed migration filename {path.name!r}; "
                "expected NNN_description.sql"
            )
            continue
        files[path.name] = path

    return files


def check_duplicate_numbers(
    label: str,
    files: dict[str, Path],
    errors: list[str],
) -> None:
    by_number: dict[int, set[str]] = defaultdict(set)
    for name in files:
        match = FILENAME_PATTERN.fullmatch(name)
        assert match is not None
        number = int(match.group("number"))
        by_number[number].add(name)
        if number < NEXT_MIGRATION_NUMBER and name not in HISTORICAL_FILES[label]:
            errors.append(
                f"{label}: new migration {name!r} uses historical prefix "
                f"{number:03d}; new migrations must use "
                f"{NEXT_MIGRATION_NUMBER:03d} or higher"
            )

    for number, names in sorted(by_number.items()):
        if len(names) == 1:
            continue
        expected = GRANDFATHERED_DUPLICATES.get(number)
        if expected is None or names != expected:
            errors.append(
                f"{label}: duplicate migration prefix {number:03d}: "
                f"{', '.join(sorted(names))}"
            )

    for number, expected in GRANDFATHERED_DUPLICATES.items():
        actual = by_number.get(number, set())
        if actual != expected:
            errors.append(
                f"{label}: grandfathered {number:03d} pair changed; expected "
                f"{', '.join(sorted(expected))}, found "
                f"{', '.join(sorted(actual)) or 'nothing'}"
            )

    # All prefixes below 044 are occupied historical history. A new file using
    # one therefore creates a duplicate and is rejected above. This diagnostic
    # documents the required floor for the next unique migration.
    unique_numbers = set(by_number)
    missing_historical = [number for number in range(1, NEXT_MIGRATION_NUMBER) if number not in unique_numbers]
    if missing_historical:
        errors.append(
            f"{label}: historical prefixes unexpectedly missing below "
            f"{NEXT_MIGRATION_NUMBER:03d}: "
            + ", ".join(f"{number:03d}" for number in missing_historical)
        )


def check_tree_parity(
    trees: dict[str, dict[str, Path]],
    errors: list[str],
) -> None:
    database_names = set(trees["database"])
    supabase_names = set(trees["supabase"])

    unexpected_database = (database_names - supabase_names) - SWAPPED_NAMES["database"]
    unexpected_supabase = (supabase_names - database_names) - SWAPPED_NAMES["supabase"]
    if unexpected_database:
        errors.append(
            "database: files missing from supabase mirror: "
            + ", ".join(sorted(unexpected_database))
        )
    if unexpected_supabase:
        errors.append(
            "supabase: files missing from database mirror: "
            + ", ".join(sorted(unexpected_supabase))
        )

    for name in sorted(database_names & supabase_names):
        if digest(trees["database"][name]) != digest(trees["supabase"][name]):
            errors.append(f"mirror content mismatch: {name}")

    for database_ref, supabase_ref in SWAPPED_FILES:
        database_name = database_ref.split("/", 1)[1]
        supabase_name = supabase_ref.split("/", 1)[1]
        database_path = trees["database"].get(database_name)
        supabase_path = trees["supabase"].get(supabase_name)
        if database_path is None or supabase_path is None:
            errors.append(
                f"historical 004/005 swap is incomplete: {database_ref} <-> {supabase_ref}"
            )
        elif digest(database_path) != digest(supabase_path):
            errors.append(
                f"historical 004/005 swap content mismatch: {database_ref} != {supabase_ref}"
            )


def check_tenant_relationship_debt(
    trees: dict[str, dict[str, Path]],
    errors: list[str],
    warnings: list[str],
) -> None:
    first, second = TENANT_RELATIONSHIP_DUPLICATES
    for label, files in trees.items():
        if first not in files or second not in files:
            errors.append(
                f"{label}: historical tenant-relationship pair is incomplete"
            )
            continue
        if digest(files[first]) != digest(files[second]):
            errors.append(
                f"{label}: {first} and {second} no longer match; "
                "historical duplicate-content debt changed"
            )
        else:
            warnings.append(
                f"{label}: {first} and {second} remain identical "
                "historical duplicate-content debt"
            )



def check_production_lineage(errors: list[str]) -> None:
    import json
    pin = REPO_ROOT / "deployment/releases/production-001-099.json"
    try:
        frozen = json.loads(pin.read_text(encoding="utf-8"))
        release = json.loads(
            (REPO_ROOT / "deployment/releases/release.json").read_text(encoding="utf-8")
        )
        release_target = int(release["schema"]["target"])
        # Preserve reviewed main's future namespace without selecting any SQL.
        retained_future = {}
        profile = release.get("deployment_profile")
        if profile in {"local-supabase-schema115", "local-supabase-schema115-136"}:
            expected_schema = {
                "compatible_min": 115, "compatible_max": 115, "target": 115,
                "migration_class": "none", "rollback_compatible_min": 115,
                "rollback_compatible_max": 115,
            }
            if profile == "local-supabase-schema115-136":
                expected_schema.update(compatible_max=136, target=136,
                                       migration_class="forward-compatible")
                valid_policy = (release.get("migration_policy") ==
                                "automatic-after-known-good-backup-first-forward-repair"
                                and release.get("migration_manifest") == "migrations-116-136.json")
            else:
                valid_policy = (release.get("migration_policy") == "none"
                                and "migration_manifest" not in release)
            if release["schema"] != expected_schema or not valid_policy:
                raise ValueError("invalid schema115 release contract")
            manifest_path = REPO_ROOT / "deployment/releases/migrations-115-135.json"
            if digest(manifest_path) != "fe1258bab5f6359a598edc9d34f66e20555f93c5ce5fe911ec13d88b8bd4d7ae":
                raise ValueError("retained canonical-main migration manifest changed")
            manifest = json.loads(manifest_path.read_text())
            entries = manifest["migrations"]
            if [entry["number"] for entry in entries] != list(range(115, 136)):
                raise ValueError("retained future namespace invalid")
            retained_future = {entry["number"]: entry for entry in entries if entry["number"] > 115}
            # Referral candidate history is retained but never selected by schema115.
            referral_manifest_path = REPO_ROOT / "deployment/releases/migrations-115-136.json"
            if digest(referral_manifest_path) != "7ce4527369df9f48be3830074e94838686bd74f9895d4a5480d67b78f5860e7f":
                raise ValueError("retained referral candidate manifest changed")
            referral_entries = json.loads(referral_manifest_path.read_text())["migrations"]
            if (referral_entries[:-1] != entries
                    or referral_entries[-1]["number"] != 136
                    or referral_entries[-1]["from_schema"] != 135
                    or referral_entries[-1]["to_schema"] != 136):
                raise ValueError("retained referral candidate namespace invalid")
            retained_future[136] = referral_entries[-1]
        if frozen["production_baseline"] != "1e6b739a43759309a45ede2dff28a859209e4a64" or len(frozen["files"]) != 198:
            raise ValueError("invalid immutable lineage manifest")
        for relative, checksum in frozen["files"].items():
            path = REPO_ROOT.parent / relative
            if not path.is_file() or digest(path) != checksum:
                errors.append(f"immutable production migration changed: {relative}")
        for tree in TREE_PATHS.values():
            for path in tree.glob("*.sql"):
                number = int(path.name.split("_", 1)[0])
                relative = path.relative_to(REPO_ROOT.parent).as_posix()
                if number <= 99 and relative not in frozen["files"]:
                    errors.append(f"unexpected historical migration: {relative}")
                retained = retained_future.get(number)
                if retained is not None:
                    if (retained["path"] != "web/database/migrations/" + path.name
                            or digest(path) != retained["sha256"]):
                        errors.append(f"checksum-pinned migration changed: {relative}")
                    continue
                if number > release_target:
                    errors.append(
                        f"unexpected migration beyond release target {release_target}: {relative}"
                    )
    except (OSError, KeyError, ValueError, TypeError) as error:
        errors.append(f"production lineage manifest invalid: {type(error).__name__}")

def main() -> int:
    errors: list[str] = []
    check_production_lineage(errors)
    warnings: list[str] = []
    trees = {
        label: collect_tree(label, path, errors)
        for label, path in TREE_PATHS.items()
    }

    for label, files in trees.items():
        check_duplicate_numbers(label, files, errors)

    check_tree_parity(trees, errors)
    check_tenant_relationship_debt(trees, errors, warnings)

    print("Migration validation summary")
    print(f"  database migrations: {len(trees['database'])}")
    print(f"  supabase migrations: {len(trees['supabase'])}")
    print(f"  warnings: {len(warnings)}")
    print(f"  errors: {len(errors)}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print("FAIL: migration validation failed", file=sys.stderr)
        return 1

    print(
        "PASS: migration trees match, known historical exceptions are intact, "
        "and no new duplicate prefixes were found"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
