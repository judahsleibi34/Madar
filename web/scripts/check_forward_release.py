#!/usr/bin/env python3
"""Validate pinned migration history and the reviewed active release contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "1e6b739a43759309a45ede2dff28a859209e4a64"

SOURCE_SCHEMA = 114
TARGET_SCHEMA = 135
MANIFEST_NAME = "migrations-115-135.json"
SCHEMA115_BRIDGE_PROFILE = "local-supabase-schema115-136"
SCHEMA115_BRIDGE_MANIFEST = "migrations-116-136.json"
SCHEMA115_BRIDGE_SCHEMA = {
    "compatible_min": 115, "compatible_max": 136, "target": 136,
    "migration_class": "forward-compatible", "rollback_compatible_min": 115,
    "rollback_compatible_max": 115,
}


def schema115_bridge_valid(release: dict) -> bool:
    return (type(release.get("release_metadata_version")) is int and release["release_metadata_version"] == 1
            and release.get("deployment_profile") == SCHEMA115_BRIDGE_PROFILE
            and release.get("schema") == SCHEMA115_BRIDGE_SCHEMA
            and release.get("migration_manifest") == SCHEMA115_BRIDGE_MANIFEST
            and release.get("migration_policy") == "automatic-after-known-good-backup-first-forward-repair")

# Migrations 100-114 have already been applied to production and are no
# longer part of the active 114 -> 135 execution manifest. Keep them
# explicitly checksum-pinned so narrowing the active manifest cannot make
# already-applied production history mutable.
APPLIED_PRODUCTION_MIGRATIONS = {
    100: (
        "100_correct_site_visit_counter_rpc.sql",
        "cd1ba91ca5619c58d7fef247e9523cbf11e9c5812774d44c544cb238645745f9",
    ),
    101: (
        "101_add_variant_attribute_presentation.sql",
        "deb740c8ced84a3e712d93b077aa273220e026c96b13dd064593bdd5a67feaad",
    ),
    102: (
        "102_add_ecommerce_discount_conditions.sql",
        "95a87d3ee5ed4606592a1ef5385c6a22bf02e2bcbfde05edb88af5081457b3f1",
    ),
    103: (
        "103_create_ecommerce_delivery_pricing.sql",
        "37b4f97a6bf70b99aaaf3c097c3f6547e79fdcd2c87779ad4ebbb193ede5ddbc",
    ),
    104: (
        "104_flatten_ecommerce_delivery_pricing.sql",
        "a2121defc5bbf5e590912c145766fcce0b4fb7652faa07bfc7f484c8811df960",
    ),
    105: (
        "105_canonical_tenant_subdomains.sql",
        "f445f36bbba71f6c78f1c4e16f8a59ae63277c7c4f59510bf4e91eab4c967097",
    ),
    106: (
        "106_add_order_delivery_fees.sql",
        "d761e17c78f32ade46561214e2f4e9cf7f6fbb6190994323e1046ad691cfc972",
    ),
    107: (
        "107_add_ecommerce_category_images.sql",
        "96643c4de3919e835e56e1fcaac93019f86391b7bbf48a4779570c9117671ec3",
    ),
    108: (
        "108_add_ecommerce_brands.sql",
        "bafe65b98e0b3b3952aa2d46986e7eae282e08a4fbdaffdd0f583cff6657d4fa",
    ),
    109: (
        "109_fix_ecommerce_order_delivery_totals_constraint.sql",
        "c2d1f1aee929a39a4fc8b86d0b63c86499638fa65eb8dfa3bcc3f0a8579a8803",
    ),
    110: (
        "110_enqueue_ecommerce_order_notifications.sql",
        "62abac35e0ba0a3ddef331391a2de76302e36898816c39ba99c3c67c5c55ca55",
    ),
    111: (
        "111_add_ecommerce_product_categories.sql",
        "c5fdf0f96788bf8850d397395e5e4a833efdb6490438821e9856a2574dbe7e27",
    ),
    112: (
        "112_allow_unreferenced_product_deletion.sql",
        "936361a17a1c21c19f927a66eb6ab52bd019bc986237c74431c11877b63f417a",
    ),
    113: (
        "113_consolidate_managed_asset_visibility.sql",
        "eca869ced3ebd98b43de58636913e873691a904c6675720424621271fd2e36dd",
    ),
    114: (
        "114_consolidate_public_site_runtime.sql",
        "73db3729be8b15f5fc2e18f0584315a16cb47555db7fc691900067b3a1582f6f",
    ),
    115: ("115_reconcile_commercial_access.sql", "e40bfdd49294438e11698934fcc37ba0dcb0a534a51890c26702b13763883f34"),
}

EXPECTED = {
    115: (
        "115_reconcile_commercial_access.sql",
        "forward-compatible",
    ),
    116: ("116_reconcile_ecommerce_product_saves.sql", "forward-compatible"),
    117: ("117_create_elearning_settings.sql", "expand-only"),
    118: ("118_create_elearning_courses.sql", "expand-only"),
    119: ("119_create_elearning_groups_and_instructors.sql", "expand-only"),
    120: ("120_create_elearning_structure.sql", "expand-only"),
    121: ("121_create_elearning_participation.sql", "expand-only"),
    122: ("122_add_elearning_course_deletion.sql", "expand-only"),
    123: ("123_manage_elearning_enrollments.sql", "expand-only"),
    124: ("124_create_elearning_content_blocks.sql", "expand-only"),
    125: ("125_add_elearning_learner_player.sql", "expand-only"),
    126: ("126_integrate_elearning_access_assignments.sql", "expand-only"),
    127: ("127_create_elearning_assessments.sql", "expand-only"),
    128: ("128_add_elearning_assessment_placements.sql", "expand-only"),
    129: ("129_integrate_commerce_learning_entitlements.sql", "expand-only"),
    130: ("130_add_elearning_credentials.sql", "expand-only"),
    131: ("131_add_fixed_learning_academy.sql", "expand-only"),
    132: ("132_add_academy_builder_integration.sql", "expand-only"),
    133: ("133_expand_academy_builder_methodology.sql", "expand-only"),
    134: ("134_guard_elearning_group_names_and_deletion.sql", "expand-only"),
    135: ("135_add_elearning_instructor_deletion.sql", "expand-only"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    release_dir = root / "web/deployment/releases"

    try:
        # Immutable historical production lineage remains frozen through 099.
        pin = json.loads(
            (release_dir / "production-001-099.json").read_text(
                encoding="utf-8"
            )
        )

        if (
            pin["production_baseline"] != BASELINE
            or len(pin["files"]) != 198
        ):
            errors.append("immutable production lineage manifest invalid")

        for relative, checksum in pin["files"].items():
            if not re.fullmatch(
                r"web/(database|supabase)/migrations/"
                r"\d{3}_[a-z0-9_]+\.sql",
                relative,
            ):
                errors.append(
                    "invalid production migration path: " + relative
                )
                continue

            path = root / relative

            if not path.is_file() or digest(path) != checksum:
                errors.append(
                    "immutable production migration changed: " + relative
                )

        # Schema 100-114 is already live in production. These migrations
        # must remain immutable even though the active execution manifest
        # begins at schema 114 and contains migrations 115 through the target schema.
        for number, (filename, checksum) in (
            APPLIED_PRODUCTION_MIGRATIONS.items()
        ):
            database = (
                root
                / "web/database/migrations"
                / filename
            )
            supabase = (
                root
                / "web/supabase/migrations"
                / filename
            )

            if (
                not database.is_file()
                or not supabase.is_file()
                or digest(database) != checksum
                or digest(supabase) != checksum
                or database.read_bytes() != supabase.read_bytes()
            ):
                errors.append(
                    "applied production migration changed: "
                    f"{number:03d}_{filename.split('_', 1)[1]}"
                )

        # Main's catalog transition already owns 116; PR rebasing may not rewrite it.
        for tree in ("database", "supabase"):
            catalog = root / f"web/{tree}/migrations/116_reconcile_ecommerce_product_saves.sql"
            if not catalog.is_file() or digest(catalog) != "6227c1f50f19282f6cd58aa5ada1b2795f5cc63ca674f9447bbdbd44011b2208":
                errors.append(f"canonical main catalog migration changed: {tree}")

        release = json.loads(
            (release_dir / "release.json").read_text(
                encoding="utf-8"
            )
        )

        schema = release["schema"]
        if release.get("deployment_profile") not in {None, "local-supabase-schema115", SCHEMA115_BRIDGE_PROFILE}:
            errors.append("unknown deployment profile")

        if release.get("deployment_profile") == "local-supabase-schema115":
            expected_schema = {
                "compatible_min": 115, "compatible_max": 115, "target": 115,
                "migration_class": "none", "rollback_compatible_min": 115,
                "rollback_compatible_max": 115,
            }
            if (schema != expected_schema or release.get("migration_policy") != "none"
                    or "migration_manifest" in release):
                errors.append("local Supabase candidate must be exact schema115 with no migration selected")
        elif release.get("deployment_profile") == SCHEMA115_BRIDGE_PROFILE:
            if not schema115_bridge_valid(release):
                errors.append("local Supabase bridge must span schema115..136 with rollback bounded at115")
        else:
            if not (
                int(schema["compatible_min"]) == SOURCE_SCHEMA
                <= TARGET_SCHEMA
                == int(schema["compatible_max"])
                == int(schema["target"])
                and int(schema["rollback_compatible_min"]) == SOURCE_SCHEMA
                == int(schema["rollback_compatible_max"])
                and schema["migration_class"] == "forward-compatible"
                and release["migration_policy"]
                == "automatic-after-known-good-backup-first-forward-repair"
                and release["migration_manifest"] == MANIFEST_NAME
            ):
                errors.append(
                    f"release must bridge production schema {SOURCE_SCHEMA} to {TARGET_SCHEMA} "
                    "with rollback bounded at schema 114"
                )
        # Retention is not execution permission. Freeze the canonical-main future
        # inventory so changing SQL and its manifest together cannot widen this
        # exact non-migrating release without a separately reviewed contract.
        if digest(release_dir / MANIFEST_NAME) != "fe1258bab5f6359a598edc9d34f66e20555f93c5ce5fe911ec13d88b8bd4d7ae":
            errors.append("retained canonical-main migration manifest changed")
        manifest = json.loads(
            (release_dir / MANIFEST_NAME).read_text(
                encoding="utf-8"
            )
        )

        identity = str(manifest.get("release_sha") or "")

        if (
            identity not in {"CURRENT", "STAGING"}
            and not re.fullmatch(r"[0-9a-f]{40}", identity)
        ):
            errors.append("manifest release identity invalid")

        entries = manifest["migrations"]

        if [int(entry["number"]) for entry in entries] != sorted(EXPECTED):
            errors.append(
                f"forward manifest must contain migrations {SOURCE_SCHEMA + 1}..{TARGET_SCHEMA}"
            )

        previous = SOURCE_SCHEMA

        for entry in entries:
            number = int(entry["number"])

            if number not in EXPECTED:
                errors.append(
                    f"unexpected forward migration: {number}"
                )
                continue

            filename, compatibility = EXPECTED[number]

            expected_path = (
                "web/database/migrations/" + filename
            )

            if not (
                int(entry["from_schema"]) == previous
                and int(entry["to_schema"]) == number
                and number == previous + 1
                and entry["compatibility"] == compatibility
                and entry["path"] == expected_path
            ):
                errors.append(
                    f"forward migration contract invalid: {number}"
                )
                previous = number
                continue

            database = root / expected_path
            supabase = root / "web/supabase/migrations" / filename

            if (
                not database.is_file()
                or not supabase.is_file()
                or database.read_bytes() != supabase.read_bytes()
                or digest(database) != str(entry["sha256"])
            ):
                errors.append(
                    "forward migration mirror/checksum invalid: "
                    + filename
                )

            previous = number

        # Retain the referral candidate without changing the active schema115
        # release or the immutable 115..135 execution manifest.
        referral_path = release_dir / "migrations-115-136.json"
        if digest(referral_path) != "7ce4527369df9f48be3830074e94838686bd74f9895d4a5480d67b78f5860e7f":
            errors.append("retained referral candidate manifest changed")
        referral_entries = json.loads(referral_path.read_text())["migrations"]
        if referral_entries[:-1] != entries or len(referral_entries) != len(entries) + 1:
            errors.append("retained referral candidate history invalid")
        if not referral_entries:
            raise ValueError("retained referral candidate manifest empty")
        referral = referral_entries[-1]
        filename = "136_add_academy_referral_rewards.sql"
        if (referral["number"] != 136 or referral["from_schema"] != 135
                or referral["to_schema"] != 136
                or referral["compatibility"] != "forward-compatible"
                or referral["path"] != "web/database/migrations/" + filename):
            errors.append("retained referral candidate transition invalid")
        database = root / "web/database/migrations" / filename
        supabase = root / "web/supabase/migrations" / filename
        if (database.read_bytes() != supabase.read_bytes()
                or digest(database) != referral["sha256"]):
            errors.append("retained referral candidate mirror/checksum invalid")

        # New source115 contract reuses the identical historical SQL entries;
        # it must not replay commercial migration115 or rewrite either old manifest.
        source115_path = release_dir / SCHEMA115_BRIDGE_MANIFEST
        source115 = json.loads(source115_path.read_text())
        if (digest(source115_path) != "2ea53a9b24f1d82dd4b3d6390779ad571a30483c3eed3fedb94391d7c3eec4e5"
                or source115 != {"release_sha":"CURRENT", "migrations":referral_entries[1:]}):
            errors.append("schema115 bridge migration history changed")
        bridge = json.loads((release_dir / "schema-115-136-bridge.json").read_text())
        if not schema115_bridge_valid(bridge):
            errors.append("schema115 bridge descriptor invalid")

        for tree in ("database", "supabase"):
            versions = sorted(
                int(path.name.split("_", 1)[0])
                for path in (
                    root / f"web/{tree}/migrations"
                ).glob("*.sql")
            )

            if versions != list(range(1, 137)):
                errors.append(
                    "migration namespace must contain exactly "
                    f"001 through 136: {tree}"
                )

    except (OSError, KeyError, ValueError, TypeError) as error:
        errors.append(
            "forward release artifacts missing or malformed: "
            + type(error).__name__
        )

    return errors


if __name__ == "__main__":
    errors = validate()

    for error in errors:
        print("INVALID " + error)

    print(
        "Forward release source contract "
        + ("INVALID" if errors else "PASS")
    )

    raise SystemExit(bool(errors))
