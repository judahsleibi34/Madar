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

    def test_allows_service_role_backend_crud(self):
        for table in ("users", "builder_projects", "website_settings"):
            grants = [grant(table, "service_role", privilege) for privilege in (
                "SELECT", "INSERT", "UPDATE", "DELETE"
            )]
            with self.subTest(table=table):
                self.assertEqual(verify_rls_grants.find_unsafe_grants(table, grants), [])

    def test_unlisted_privilege_cannot_false_pass(self):
        self.assertEqual(
            verify_rls_grants.find_unsafe_grants(
                "users", [grant("users", "authenticated", "TRUNCATE")]
            ),
            ["authenticated:TRUNCATE"],
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
