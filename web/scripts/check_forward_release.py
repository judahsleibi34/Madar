#!/usr/bin/env python3
"""Validate the production schema-102 to schema-104 forward release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "1e6b739a43759309a45ede2dff28a859209e4a64"

SOURCE_SCHEMA = 102
TARGET_SCHEMA = 104
MANIFEST_NAME = "migrations-103-104.json"

# Migrations 100-102 have already been applied to production and are no
# longer part of the active 102 -> 104 execution manifest. Keep them
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
}

EXPECTED = {
    103: (
        "103_create_ecommerce_delivery_pricing.sql",
        "expand-only",
    ),
    104: (
        "104_flatten_ecommerce_delivery_pricing.sql",
        "forward-compatible",
    ),
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

        # Schema 100-102 is already live in production. These migrations
        # must remain immutable even though the active execution manifest
        # begins at schema 102 and therefore contains only 103 and 104.
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

        release = json.loads(
            (release_dir / "release.json").read_text(
                encoding="utf-8"
            )
        )

        schema = release["schema"]

        if not (
            int(schema["compatible_min"]) <= SOURCE_SCHEMA
            <= TARGET_SCHEMA
            == int(schema["compatible_max"])
            == int(schema["target"])
            and int(schema["rollback_compatible_min"]) <= SOURCE_SCHEMA
            == int(schema["rollback_compatible_max"])
            and schema["migration_class"] == "expand-only"
            and release["migration_policy"]
            == "automatic-after-known-good-backup-first-forward-repair"
            and release["migration_manifest"] == MANIFEST_NAME
        ):
            errors.append(
                "release must bridge production schema 102 to 104 "
                "with rollback bounded at schema 102"
            )

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

        if [int(entry["number"]) for entry in entries] != [103, 104]:
            errors.append(
                "forward manifest must contain ordered migrations 103 and 104"
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

        for tree in ("database", "supabase"):
            versions = sorted(
                int(path.name.split("_", 1)[0])
                for path in (
                    root / f"web/{tree}/migrations"
                ).glob("*.sql")
            )

            if versions != list(range(1, TARGET_SCHEMA + 1)):
                errors.append(
                    "migration namespace must contain exactly "
                    f"001 through {TARGET_SCHEMA:03d}: {tree}"
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
