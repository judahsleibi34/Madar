#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1]
FIRST_PRE_DDL_GUARD = 117


def _without_comments(sql: str) -> str:
    """Remove SQL comments without letting quoted text create fake comments."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if quote is not None:
            output.append(char)
            if char == quote:
                if following == quote:
                    output.append(following)
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            output.append(char)
            index += 1
            continue
        if char == "-" and following == "-":
            output.extend("  ")
            index += 2
            while index < len(sql) and sql[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if char == "/" and following == "*":
            output.extend("  ")
            index += 2
            while index < len(sql):
                if index + 1 < len(sql) and sql[index:index + 2] == "*/":
                    output.extend("  ")
                    index += 2
                    break
                output.append("\n" if sql[index] == "\n" else " ")
                index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def validate(web_root: Path = WEB_ROOT) -> list[str]:
    database_root = web_root / "database/migrations"
    supabase_root = web_root / "supabase/migrations"
    errors: list[str] = []

    def fail(message: str) -> None:
        errors.append(message)

    for number in range(84, 1000):
        database = sorted(database_root.glob(f"{number:03d}_*.sql"))
        supabase = sorted(supabase_root.glob(f"{number:03d}_*.sql"))
        if not database and not supabase:
            continue
        if len(database) != 1:
            fail(f"{number:03d}: expected exactly one database migration, found {len(database)}")
            continue
        if len(supabase) != 1:
            fail(f"{number:03d}: expected exactly one Supabase migration, found {len(supabase)}")
            continue

        database_path = database[0]
        supabase_path = supabase[0]
        if database_path.name != supabase_path.name:
            fail(f"{number:03d}: database/Supabase filenames differ")
            continue
        database_bytes = database_path.read_bytes()
        supabase_bytes = supabase_path.read_bytes()
        if database_bytes != supabase_bytes:
            fail(f"{number:03d}: database/Supabase mirrors differ")

        text = _without_comments(database_bytes.decode("utf-8")).lower()
        if not text.lstrip().startswith("begin;"):
            fail(f"{number:03d}: migration must begin with BEGIN")
        if not text.rstrip().endswith("commit;"):
            fail(f"{number:03d}: migration must end with COMMIT")

        previous = number - 1
        if number == 143:
            from check_learning_migration_path import validate as validate_learning_path
            try:
                contract = validate_learning_path(web_root.parent)
                if contract["status"] != "finalized":
                    raise ValueError("learning path is reserved")
                previous = 141
            except (OSError, ValueError, TypeError, KeyError) as error:
                fail(f"143: unauthorized learning branch: {error}")
                continue

        if re.search(r"\bcurrent_schema\b", text):
            fail(f"{number:03d}: reserved CURRENT_SCHEMA identifier must not be used as a PL/pgSQL variable")

        declaration_pattern = re.compile(
            r"\bv_schema_version\s+public\s*\.\s*application_schema_state\s*\.\s*"
            r"schema_version\s*%\s*type\s*;"
        )
        guard_pattern = re.compile(rf"\bv_schema_version\s*<>\s*{previous}\b")
        query_pattern = re.compile(
            r"\bselect\s+schema_version\s+into\s+v_schema_version\s+"
            r"from\s+public\s*\.\s*application_schema_state\s+"
            r"where\s+contract_key\s*=\s*'core'\s+for\s+update\s*;",
            re.DOTALL,
        )
        transition_pattern = re.compile(rf"\bset\s+schema_version\s*=\s*{number}\b")

        declarations = declaration_pattern.findall(text)
        guards = guard_pattern.findall(text)
        transitions = transition_pattern.findall(text)
        if len(declarations) != 1:
            fail(f"{number:03d}: expected exactly one typed schema-version declaration")
        if len(guards) != 1:
            fail(f"{number:03d}: expected exactly one {previous}->{number} source-schema guard")
        if len(transitions) != 1:
            fail(f"{number:03d}: expected exactly one schema_version={number} transition")

        guard_blocks = []
        for block in re.finditer(r"\bdo\s+\$\$(.*?)\$\$\s*;", text, re.DOTALL):
            body = block.group(1)
            if (declaration_pattern.search(body)
                    and query_pattern.search(body)
                    and guard_pattern.search(body)):
                guard_blocks.append(block)
        if len(guard_blocks) != 1:
            fail(
                f"{number:03d}: typed declaration, core schema-state query, "
                "FOR UPDATE lock, and predecessor guard must share one executable DO block"
            )
        elif number >= FIRST_PRE_DDL_GUARD:
            first_ddl = re.search(
                r"(?im)^\s*(?:create(?:\s+or\s+replace)?|alter|drop|truncate)\s+"
                r"(?:table|function|trigger|index|extension|type|policy|view|materialized\s+view|sequence|schema)\b",
                text,
            )
            if first_ddl is not None and guard_blocks[0].start() > first_ddl.start():
                fail(f"{number:03d}: schema-state guard and row lock must precede schema-changing DDL")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Migration transition validation FAILED:")
        for error in errors:
            print(" -", error)
        return 1
    print("Migration transition validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
