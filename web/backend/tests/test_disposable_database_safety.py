import unittest
from unittest.mock import Mock, patch

from tests.disposable_database_support import connect_disposable_database


class DisposableDatabaseSafetyTests(unittest.TestCase):
    def test_nonlocal_and_hostaddr_redirects_reject_before_connect(self):
        for dsn in (
            "host=production.example dbname=postgres",
            "host=127.0.0.1 hostaddr=192.0.2.1 dbname=postgres",
            "host=localhost,production.example dbname=postgres",
            "dbname=postgres", "service=production host=localhost",
        ):
            with self.subTest(dsn=dsn), patch("tests.disposable_database_support.psycopg.connect") as connect:
                with self.assertRaisesRegex(RuntimeError, "loopback"):
                    connect_disposable_database(dsn, markers={"synthetic-marker"})
                connect.assert_not_called()

    def test_unmarked_local_database_closes_before_fixture_writes(self):
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = (None,)
        with patch("tests.disposable_database_support.psycopg.connect", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "ownership"):
                connect_disposable_database("host=127.0.0.1 dbname=postgres", markers={"synthetic-marker"})
        connection.close.assert_called_once()
        self.assertEqual(connection.execute.call_count, 1)
        self.assertTrue(connection.execute.call_args.args[0].startswith("select "))

    def test_correct_marker_returns_the_verified_connection(self):
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = ("synthetic-marker",)
        with patch("tests.disposable_database_support.psycopg.connect", return_value=connection) as connect:
            actual = connect_disposable_database("host=::1 dbname=synthetic", markers={"synthetic-marker"})
        self.assertIs(actual, connection)
        self.assertEqual(connect.call_args.kwargs["hostaddr"], "::1")
        self.assertEqual(connect.call_args.kwargs["options"], "-c search_path=pg_catalog,public,extensions")
        self.assertIn("pg_catalog.current_database()", connection.execute.call_args.args[0])
        connection.close.assert_not_called()

    def test_connection_failures_do_not_disclose_credentials(self):
        with patch("tests.disposable_database_support.psycopg.connect", side_effect=RuntimeError("private-password")):
            with self.assertRaises(RuntimeError) as caught:
                connect_disposable_database("host=localhost password=private-password", markers={"synthetic-marker"})
        self.assertNotIn("private-password", str(caught.exception))
