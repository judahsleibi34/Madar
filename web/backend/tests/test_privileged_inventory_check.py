"""Adversarial completeness checks; these never import application modules.

Route/SQL authorization remains a separate requirement. Real checkout coverage
is checked by running check_privileged_inventory.py against that checkout; these
fixtures test that its omission, duplicate, stale and scope controls still work.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
CHECKER = WEB / 'scripts/check_privileged_inventory.py'


class PrivilegedInventoryCheckTests(unittest.TestCase):
    def scan(self, files, entries):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checker = root / 'web/scripts/check_privileged_inventory.py'
            checker.parent.mkdir(parents=True)
            shutil.copyfile(CHECKER, checker)
            (root / 'web/backend').mkdir()
            for name, body in files.items():
                path = root / 'web/backend' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            manifest = root / 'docs/master-implementation-2026-09-08/privileged-access-inventory.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'entries': entries}))
            return subprocess.run([sys.executable, str(checker)], capture_output=True,
                                  text=True, timeout=10, check=False)

    @staticmethod
    def entry(name, boundary='fixture classification; not proof of authorization'):
        return {'path': 'web/backend/' + name, 'boundary': boundary}

    def test_classified_source_is_parsed_without_importing_or_executing_it(self):
        source = 'from database import service_supabase\nraise RuntimeError("must never execute")\n'
        result = self.scan({'routes/example.py': source}, [self.entry('routes/example.py')])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('1 application files', result.stdout)
        self.assertIn('authorization requires separate route/SQL checks', result.stdout)

    def test_missing_privileged_route_fails(self):
        result = self.scan({'routes/new.py': 'from database import service_supabase\n'}, [])
        self.assertEqual(result.returncode, 1)
        self.assertIn('web/backend/routes/new.py', result.stdout)

    def test_each_supported_privileged_client_name_and_attribute_is_discovered(self):
        for client in ('service_supabase', 'admin_supabase', 'supabase_admin'):
            for expression in ('from database import ' + client + ' as database_client\n',
                               'def operation(client):\n    return client.' + client + '\n'):
                with self.subTest(client=client, expression=expression):
                    result = self.scan({'services/new.py': expression}, [])
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('web/backend/services/new.py', result.stdout)

    def test_workers_are_not_exempt_from_inventory(self):
        result = self.scan({'workers/new.py': 'def poll():\n    from database import service_supabase\n'}, [])
        self.assertEqual(result.returncode, 1)
        self.assertIn('web/backend/workers/new.py', result.stdout)

    def test_stale_classification_fails(self):
        result = self.scan({}, [self.entry('services/removed.py')])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Stale inventory paths: ['web/backend/services/removed.py']", result.stdout)

    def test_duplicate_classifications_fail_even_when_reference_set_matches(self):
        entry = self.entry('services/example.py')
        result = self.scan({'services/example.py': 'service_supabase = object()\n'}, [entry, entry])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate or unclassified', result.stderr)

    def test_missing_or_empty_boundary_is_rejected(self):
        for entry in ({'path': 'web/backend/services/example.py'}, self.entry('services/example.py', '')):
            with self.subTest(entry=entry):
                result = self.scan({'services/example.py': 'service_supabase = object()\n'}, [entry])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('duplicate or unclassified', result.stderr)

    def test_only_existing_test_script_and_bytecode_scopes_are_excluded(self):
        result = self.scan({name: 'service_supabase = object()\n' for name in
                            ('tests/example.py', 'scripts/operator.py', '__pycache__/generated.py')}, [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('0 application files', result.stdout)


if __name__ == '__main__':
    unittest.main()
