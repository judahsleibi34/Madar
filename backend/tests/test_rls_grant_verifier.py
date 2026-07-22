import unittest
from pathlib import Path

from scripts import verify_rls_grants


def grant(table, grantee, privilege):
    return {
        "table_name": table,
        "grantee": grantee,
        "privilege_type": privilege,
    }


class RlsGrantVerifierTests(unittest.TestCase):
    def test_acl_normalization_migration_matches_and_covers_complete_contract(self):
        root = next(parent for parent in Path(__file__).resolve().parents if (parent / "database/migrations").is_dir())
        name = "066_normalize_sensitive_object_privileges.sql"
        database_sql = (root / "database/migrations" / name).read_text(encoding="utf-8")
        supabase_sql = (root / "supabase/migrations" / name).read_text(encoding="utf-8")
        self.assertEqual(database_sql, supabase_sql)
        normalized = " ".join(database_sql.lower().split())
        self.assertIn("revoke all privileges on table public.%i from public, anon, authenticated, service_role", normalized)
        self.assertIn("grant select, insert, update, delete on table public.%i to service_role", normalized)
        self.assertIn("grant usage, select on sequence %i.%i to service_role", normalized)
        self.assertIn("alter default privileges for role postgres in schema public", normalized)
        self.assertIn("revoke all privileges on functions from public, anon, authenticated, service_role", normalized)
        self.assertIn("publish_builder_project_atomic", normalized)
        self.assertIn("calendar_oauth_states", normalized)

    def test_exact_table_acl_detects_unexpected_and_missing_privileges(self):
        rows = [
            grant("builder_form_submissions", "authenticated", "SELECT"),
            grant("builder_form_submissions", "anon", "TRUNCATE"),
            grant("builder_form_submissions", "service_role", "SELECT"),
            grant("builder_form_submissions", "service_role", "INSERT"),
            grant("builder_form_submissions", "service_role", "UPDATE"),
        ]
        self.assertEqual(
            verify_rls_grants.find_grant_mismatches("builder_form_submissions", rows),
            [
                "anon:unexpected:TRUNCATE",
                "service_role:missing:DELETE",
            ],
        )

    def test_exact_acl_rejects_authenticated_references_and_trigger(self):
        rows = [
            grant("builder_projects", "authenticated", "SELECT"),
            grant("builder_projects", "authenticated", "REFERENCES"),
            grant("builder_projects", "authenticated", "TRIGGER"),
        ] + [grant("builder_projects", "service_role", privilege) for privilege in verify_rls_grants.TABLE_CRUD_GRANTS]
        self.assertEqual(
            verify_rls_grants.find_grant_mismatches("builder_projects", rows),
            ["authenticated:unexpected:REFERENCES", "authenticated:unexpected:TRIGGER"],
        )

    def test_exact_acl_rejects_unexpected_service_role_privilege(self):
        rows = [grant("audit_logs", "service_role", privilege) for privilege in (
            "SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"
        )]
        self.assertEqual(
            verify_rls_grants.find_grant_mismatches("audit_logs", rows),
            ["service_role:unexpected:TRUNCATE"],
        )

    def test_sequence_acl_is_exact(self):
        rows = [
            {"sequence_name": "users_id_seq", "owner_name": "postgres", "grantee": "service_role", "privilege_type": "USAGE"},
            {"sequence_name": "users_id_seq", "owner_name": "postgres", "grantee": "service_role", "privilege_type": "SELECT"},
            {"sequence_name": "users_id_seq", "owner_name": "postgres", "grantee": "authenticated", "privilege_type": "UPDATE"},
        ]
        self.assertEqual(
            verify_rls_grants.find_sequence_mismatches(rows),
            ["role=authenticated sequence=public.users_id_seq unexpected=UPDATE expected=none"],
        )

    def test_default_acl_detects_public_execute(self):
        rows = [
            {"object_type": "tables", "grantee": "service_role", "privilege_type": privilege}
            for privilege in verify_rls_grants.TABLE_CRUD_GRANTS
        ] + [
            {"object_type": "sequences", "grantee": "service_role", "privilege_type": privilege}
            for privilege in verify_rls_grants.SEQUENCE_SERVICE_GRANTS
        ] + [
            {"object_type": "functions", "grantee": "service_role", "privilege_type": "EXECUTE"},
            {"object_type": "functions", "grantee": "public", "privilege_type": "EXECUTE"},
        ]
        self.assertEqual(
            verify_rls_grants.find_default_acl_mismatches(rows),
            ["default=functions role=public unexpected=EXECUTE expected=none"],
        )

    def test_environment_contract_rejects_schema_create_and_role_inheritance(self):
        schema = [
            {"role_name": "anon", "has_usage": "true", "has_create": "true"},
            {"role_name": "authenticated", "has_usage": "true", "has_create": "false"},
            {"role_name": "service_role", "has_usage": "true", "has_create": "false"},
        ]
        memberships = [{"member_role": "authenticated", "granted_role": "service_role"}]
        self.assertEqual(
            verify_rls_grants.find_environment_mismatches(schema, memberships),
            [
                "role=anon schema=public unexpected=CREATE expected=USAGE",
                "role=authenticated inherits=service_role invalidates_direct_acl_contract",
            ],
        )

    def test_missing_rls_is_reported(self):
        table = "audit_logs"
        grants = [grant(table, "service_role", privilege) for privilege in verify_rls_grants.TABLE_CRUD_GRANTS]
        report = next(
            item for item in verify_rls_grants.build_reports(
                {table: {"table_name": table, "rls_enabled": "false", "owner_name": "postgres"}},
                [],
                grants,
            ) if item.table == table
        )
        self.assertFalse(report.rls_enabled)

    def test_function_contract_rejects_public_execute_and_unsafe_search_path(self):
        functions = [
            {
                "signature": "public.consume_calendar_oauth_state(text)",
                "function_name": "consume_calendar_oauth_state",
                "settings": "search_path=$user,public",
                "owner_name": "postgres",
                "security_definer": "true",
                "public_execute": "true",
                "anon_execute": "false",
                "authenticated_execute": "false",
                "service_role_execute": "true",
            }
        ]
        mismatches = verify_rls_grants.find_function_mismatches(functions)
        self.assertIn("function=public.consume_calendar_oauth_state(text) unsafe_search_path", mismatches)
        self.assertIn("role=public function=public.consume_calendar_oauth_state(text) unexpected=EXECUTE expected=none", mismatches)

    def test_calendar_tables_are_service_role_only_and_oauth_rpc_is_protected(self):
        calendar_tables = {
            "calendars", "calendar_memberships", "calendar_events",
            "calendar_event_attendees", "calendar_event_reminders",
            "calendar_event_changes", "calendar_tasks", "calendar_task_dependencies",
            "calendar_task_reminders", "calendar_sync_connections",
            "calendar_sync_conflicts", "calendar_invitation_reviews", "calendar_oauth_states",
        }
        self.assertTrue(calendar_tables.issubset(set(verify_rls_grants.SENSITIVE_TABLES)))
        for table in calendar_tables:
            with self.subTest(table=table):
                self.assertEqual(verify_rls_grants.ALLOWED_DIRECT_GRANTS[table]["anon"], set())
                self.assertEqual(verify_rls_grants.ALLOWED_DIRECT_GRANTS[table]["authenticated"], set())
                self.assertEqual(verify_rls_grants.ALLOWED_DIRECT_GRANTS[table]["service_role"], verify_rls_grants.TABLE_CRUD_GRANTS)
        self.assertIn("consume_calendar_oauth_state", verify_rls_grants.SENSITIVE_SECURITY_DEFINER_FUNCTIONS)

    def test_calendar_oauth_migration_matches_and_has_fixed_search_path(self):
        root = next(parent for parent in Path(__file__).resolve().parents if (parent / "database/migrations").is_dir())
        relative = "065_secure_calendar_oauth_state.sql"
        database_sql = (root / "database/migrations" / relative).read_text(encoding="utf-8")
        supabase_sql = (root / "supabase/migrations" / relative).read_text(encoding="utf-8")
        self.assertEqual(database_sql, supabase_sql)
        normalized = " ".join(database_sql.lower().split())
        self.assertIn("security definer set search_path = public", normalized)
        self.assertIn("from public, anon, authenticated", normalized)
        self.assertIn("to service_role", normalized)

    def test_calendar_migrations_061_through_064_match_and_preserve_backend_only_access(self):
        root = next(parent for parent in Path(__file__).resolve().parents if (parent / "database/migrations").is_dir())
        names = (
            "061_create_calendar_platform.sql",
            "062_add_calendar_task_reminders.sql",
            "063_backfill_calendar_task_reminders.sql",
            "064_add_calendar_task_recurrence.sql",
        )
        texts = {}
        for name in names:
            database_sql = (root / "database/migrations" / name).read_text(encoding="utf-8")
            supabase_sql = (root / "supabase/migrations" / name).read_text(encoding="utf-8")
            self.assertEqual(database_sql, supabase_sql, name)
            texts[name] = " ".join(database_sql.lower().split())
        platform = texts[names[0]]
        self.assertIn("enable row level security", platform)
        self.assertIn("revoke all on table public.%i from anon, authenticated", platform)
        self.assertIn("grant select, insert, update, delete on table public.%i to service_role", platform)
        reminders = texts[names[1]]
        self.assertIn("alter table public.calendar_task_reminders enable row level security", reminders)
        self.assertIn("revoke all on table public.calendar_task_reminders from anon, authenticated", reminders)
        self.assertIn("to service_role", reminders)
        self.assertIn("on conflict (task_id, channel) do nothing", texts[names[2]])
        self.assertIn("calendar_tasks_recurrence_rule_check", texts[names[3]])

    def test_privileged_write_migration_revokes_browser_dml_in_both_trees(self):
        test_path = Path(__file__).resolve()
        root = next(
            parent
            for parent in test_path.parents
            if (parent / "database" / "migrations").is_dir()
            and (parent / "supabase" / "migrations").is_dir()
        )
        relative_path = "050_restrict_authenticated_privileged_writes.sql"
        database_sql = (root / "database" / "migrations" / relative_path).read_text(
            encoding="utf-8"
        )
        supabase_sql = (root / "supabase" / "migrations" / relative_path).read_text(
            encoding="utf-8"
        )

        self.assertEqual(database_sql, supabase_sql)
        normalized = " ".join(database_sql.lower().split())
        for table in ("public.users", "public.builder_projects", "public.website_settings"):
            with self.subTest(table=table):
                self.assertIn(
                    f"revoke insert, update, delete on table {table} from authenticated",
                    normalized,
                )
                self.assertIn(
                    f"grant select, insert, update, delete on table {table} to service_role",
                    normalized,
                )

    def test_residual_privilege_migration_resets_authenticated_to_select_only(self):
        test_path = Path(__file__).resolve()
        root = next(
            parent
            for parent in test_path.parents
            if (parent / "database" / "migrations").is_dir()
            and (parent / "supabase" / "migrations").is_dir()
        )
        relative_path = "053_remove_residual_authenticated_privileges.sql"
        database_sql = (root / "database" / "migrations" / relative_path).read_text(
            encoding="utf-8"
        )
        supabase_sql = (root / "supabase" / "migrations" / relative_path).read_text(
            encoding="utf-8"
        )

        self.assertEqual(database_sql, supabase_sql)
        normalized = " ".join(database_sql.lower().split())
        for table in ("public.users", "public.builder_projects", "public.website_settings"):
            with self.subTest(table=table):
                self.assertIn(
                    f"revoke all privileges on table {table} from authenticated",
                    normalized,
                )
                self.assertIn(f"grant select on table {table} to authenticated", normalized)

    def test_rejects_authenticated_users_update(self):
        self.assertEqual(
            verify_rls_grants.find_unsafe_grants(
                "users", [grant("users", "authenticated", "UPDATE")]
            ),
            ["authenticated:UPDATE"],
        )

    def test_rejects_authenticated_builder_project_crud(self):
        grants = [
            grant("builder_projects", "authenticated", privilege)
            for privilege in ("INSERT", "UPDATE", "DELETE")
        ]
        self.assertEqual(
            verify_rls_grants.find_unsafe_grants("builder_projects", grants),
            ["authenticated:DELETE", "authenticated:INSERT", "authenticated:UPDATE"],
        )

    def test_rejects_authenticated_website_settings_update(self):
        self.assertEqual(
            verify_rls_grants.find_unsafe_grants(
                "website_settings",
                [grant("website_settings", "authenticated", "UPDATE")],
            ),
            ["authenticated:UPDATE"],
        )

    def test_allows_scoped_authenticated_select(self):
        for table in ("users", "builder_projects", "website_settings"):
            with self.subTest(table=table):
                self.assertEqual(
                    verify_rls_grants.find_unsafe_grants(
                        table, [grant(table, "authenticated", "SELECT")]
                    ),
                    [],
                )

    def test_rejects_every_residual_builder_project_privilege(self):
        for privilege in ("TRUNCATE", "TRIGGER", "REFERENCES"):
            with self.subTest(privilege=privilege):
                self.assertEqual(
                    verify_rls_grants.find_unsafe_grants(
                        "builder_projects",
                        [grant("builder_projects", "authenticated", privilege)],
                    ),
                    [f"authenticated:{privilege}"],
                )

    def test_allows_service_role_backend_crud(self):
        for table in ("users", "builder_projects", "website_settings"):
            grants = [grant(table, "service_role", privilege) for privilege in (
                "SELECT", "INSERT", "UPDATE", "DELETE"
            )]
            with self.subTest(table=table):
                self.assertEqual(verify_rls_grants.find_unsafe_grants(table, grants), [])

    def test_unknown_future_privilege_cannot_false_pass(self):
        self.assertEqual(
            verify_rls_grants.find_unsafe_grants(
                "users", [grant("users", "authenticated", "FUTURE_PRIVILEGE")]
            ),
            ["authenticated:FUTURE_PRIVILEGE"],
        )

    def test_unsafe_grant_description_names_role_table_unexpected_and_expected(self):
        self.assertEqual(
            verify_rls_grants.describe_unsafe_grants(
                "builder_projects", ["authenticated:TRUNCATE"]
            ),
            [
                "role=authenticated table=public.builder_projects "
                "unexpected=TRUNCATE expected=SELECT"
            ],
        )

    def test_publish_rpc_migrations_keep_only_validated_service_execute(self):
        test_path = Path(__file__).resolve()
        root = next(
            parent
            for parent in test_path.parents
            if (parent / "database" / "migrations" / "045_add_platform_safety.sql").is_file()
        )
        migration_045 = (root / "database/migrations/045_add_platform_safety.sql").read_text(
            encoding="utf-8"
        )
        migration_052 = (
            root / "database/migrations/052_publish_validated_builder_schema.sql"
        ).read_text(encoding="utf-8")
        old_sql = " ".join(migration_045.lower().split())
        new_sql = " ".join(migration_052.lower().split())

        old_signature = (
            "public.publish_builder_project_atomic(uuid, integer, bigint, "
            "timestamptz, integer, boolean)"
        )
        old_signature_052 = (
            "public.publish_builder_project_atomic( uuid, integer, bigint, "
            "timestamptz, integer, boolean )"
        )
        self.assertIn(
            f"revoke all on function {old_signature} from public, anon, authenticated",
            old_sql,
        )
        self.assertIn(
            f"revoke all on function {old_signature_052} from service_role",
            new_sql,
        )
        self.assertIn("security definer", new_sql)
        self.assertIn("set search_path = public", new_sql)
        self.assertIn(
            "revoke all on function public.publish_validated_builder_project_atomic( "
            "uuid, integer, bigint, jsonb, timestamptz, integer, boolean ) from "
            "public, anon, authenticated",
            new_sql,
        )
        self.assertIn(
            "grant execute on function public.publish_validated_builder_project_atomic( "
            "uuid, integer, bigint, jsonb, timestamptz, integer, boolean ) to service_role",
            new_sql,
        )

    def test_sensitive_function_requires_safe_search_path_and_service_only_execute(self):
        reports = verify_rls_grants.build_function_reports(
            [
                {
                    "signature": "public.publish_builder_project_atomic(uuid,integer)",
                    "settings": "search_path=public",
                    "public_execute": "false",
                    "anon_execute": "false",
                    "authenticated_execute": "false",
                },
                {
                    "signature": "public.unsafe_function()",
                    "settings": "",
                    "public_execute": "true",
                    "anon_execute": "true",
                    "authenticated_execute": "false",
                },
            ]
        )

        self.assertTrue(reports[0].safe_search_path)
        self.assertEqual(reports[0].unsafe_execute_roles, [])
        self.assertFalse(reports[1].safe_search_path)
        self.assertEqual(reports[1].unsafe_execute_roles, ["public", "anon"])


if __name__ == "__main__":
    unittest.main()
