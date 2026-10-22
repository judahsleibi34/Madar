import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


REPOSITORY_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
)
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts/check_migration_transitions.py"
SPEC = importlib.util.spec_from_file_location("migration_transition_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


VALID_154 = """begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;
  if v_schema_version is null then
    raise exception 'missing';
  end if;
  if v_schema_version <> 153 then
    raise exception 'wrong predecessor';
  end if;
end;
$$;

create table public.fixture154(id integer);

update public.application_schema_state
set schema_version = 154, applied_at = now()
where contract_key = 'core' and schema_version = 153;

commit;
"""


class MigrationTransitionValidatorTests(unittest.TestCase):
    def validate_fixture(self, database_sql, supabase_sql=None):
        with tempfile.TemporaryDirectory() as temporary:
            web_root = Path(temporary)
            database = web_root / "database/migrations"
            supabase = web_root / "supabase/migrations"
            database.mkdir(parents=True)
            supabase.mkdir(parents=True)
            filename = "154_fixture.sql"
            (database / filename).write_text(database_sql, encoding="utf-8")
            (supabase / filename).write_text(
                database_sql if supabase_sql is None else supabase_sql,
                encoding="utf-8",
            )
            return validator.validate(web_root)

    def assert_invalid(self, sql, expected):
        errors = self.validate_fixture(sql)
        self.assertTrue(errors)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_corrected_transition_and_whitespace_variation_pass(self):
        self.assertEqual(self.validate_fixture(VALID_154), [])
        varied = VALID_154.replace(
            "public.application_schema_state.schema_version%TYPE",
            "public . application_schema_state . schema_version % TYPE",
        ).replace("contract_key = 'core'", "contract_key='core'")
        self.assertEqual(self.validate_fixture(varied), [])

    def test_missing_lock_fails_even_with_unrelated_for_update(self):
        sql = VALID_154.replace("  for update;", ";")
        sql = sql.replace(
            "create table public.fixture154(id integer);",
            "create table public.fixture154(id integer);\n"
            "create function public.unrelated154() returns trigger language plpgsql as $$\n"
            "begin perform 1 from public.fixture154 for update; return new; end;\n$$;",
        )
        self.assert_invalid(sql, "must share one executable DO block")

    def test_wrong_predecessor_fails(self):
        self.assert_invalid(
            VALID_154.replace("v_schema_version <> 153", "v_schema_version <> 152"),
            "153->154 source-schema guard",
        )

    def test_missing_or_wrong_core_contract_fails(self):
        self.assert_invalid(
            VALID_154.replace("contract_key = 'core'", "contract_key = 'other'"),
            "must share one executable DO block",
        )
        self.assert_invalid(
            VALID_154.replace("  where contract_key = 'core'\n  for update;", "  for update;"),
            "must share one executable DO block",
        )

    def test_comments_cannot_spoof_guard_contract(self):
        guarded = VALID_154[VALID_154.index("do $$"):VALID_154.index("create table")]
        sql = VALID_154.replace(guarded, "/*\n" + guarded + "*/\n")
        self.assert_invalid(sql, "typed schema-version declaration")

    def test_duplicate_transition_fails(self):
        duplicate = VALID_154.replace(
            "commit;",
            "update public.application_schema_state set schema_version = 154 "
            "where contract_key = 'core';\ncommit;",
        )
        self.assert_invalid(duplicate, "exactly one schema_version=154 transition")

    def test_schema_guard_must_precede_ddl(self):
        ddl = "create table public.fixture154(id integer);"
        sql = VALID_154.replace(ddl + "\n", "").replace("do $$", ddl + "\n\ndo $$", 1)
        self.assert_invalid(sql, "must precede schema-changing DDL")

    def test_mismatched_migration_mirrors_fail(self):
        errors = self.validate_fixture(VALID_154, VALID_154 + "\n-- mirror drift\n")
        self.assertTrue(any("mirrors differ" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
