#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "web/database/migrations"
SB = ROOT / "web/supabase/migrations"

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


for number in range(84, 1000):
    database = sorted(DB.glob(f"{number:03d}_*.sql"))
    supabase = sorted(SB.glob(f"{number:03d}_*.sql"))

    if not database and not supabase:
        continue

    if len(database) != 1:
        fail(
            f"{number:03d}: expected exactly one database migration, "
            f"found {len(database)}"
        )
        continue

    if len(supabase) != 1:
        fail(
            f"{number:03d}: expected exactly one Supabase migration, "
            f"found {len(supabase)}"
        )
        continue

    db = database[0]
    sb = supabase[0]

    if db.name != sb.name:
        fail(f"{number:03d}: database/Supabase filenames differ")
        continue

    db_bytes = db.read_bytes()
    sb_bytes = sb.read_bytes()

    if db_bytes != sb_bytes:
        fail(f"{number:03d}: database/Supabase mirrors differ")

    text = db_bytes.decode("utf-8").lower()

    if not text.lstrip().startswith("begin;"):
        fail(f"{number:03d}: migration must begin with BEGIN")

    if not text.rstrip().endswith("commit;"):
        fail(f"{number:03d}: migration must end with COMMIT")

    previous = number - 1

    if re.search(r"\bcurrent_schema\b", text):
        fail(
            f"{number:03d}: reserved CURRENT_SCHEMA identifier "
            "must not be used as a PL/pgSQL variable"
        )

    declaration = (
        "v_schema_version "
        "public.application_schema_state.schema_version%type;"
    )

    if declaration not in text:
        fail(
            f"{number:03d}: schema guard must use "
            "application_schema_state.schema_version%TYPE"
        )

    guards = re.findall(
        rf"v_schema_version\s*<>\s*{previous}\b",
        text,
    )

    transitions = re.findall(
        rf"set\s+schema_version\s*=\s*{number}\b",
        text,
    )

    if len(guards) != 1:
        fail(
            f"{number:03d}: expected exactly one "
            f"{previous}->{number} source-schema guard"
        )

    if len(transitions) != 1:
        fail(
            f"{number:03d}: expected exactly one "
            f"schema_version={number} transition"
        )

    if "for update" not in text:
        fail(
            f"{number:03d}: schema-state row must be locked FOR UPDATE"
        )

    if "contract_key = 'core'" not in text:
        fail(
            f"{number:03d}: migration must target core schema contract"
        )


if errors:
    print("Migration transition validation FAILED:")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)

print("Migration transition validation PASS")
