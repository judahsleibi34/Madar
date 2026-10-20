"""Real temporary Git repositories and PostgreSQL17 AST; no deployment authority."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.migration_inventory import discover, canonical
from deployment.lib.migration_risk import analyze, scaffold


class SourceFixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git('init', '-q'); self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('remote', 'add', 'origin', 'https://github.com/judahsleibi34/Madar.git')
        self.write(1); self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', *args], cwd=self.root,
                                       stderr=subprocess.DEVNULL).decode().strip()

    def write(self, number, body=None, name=None):
        if body is None:
            body = scaffold(number-1, number, 'CREATE TABLE public.example (id pg_catalog.int8);') if number>1 else b'-- synthetic historical SQL\n'
        for tree in ('database', 'supabase'):
            path = self.root/'web'/tree/'migrations'/(name or f'{number:03d}_example.sql')
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)

    def commit(self):
        self.git('add', '.'); self.git('commit', '--allow-empty', '-qm', 'synthetic fixture')
        return self.git('rev-parse', 'HEAD')

    def inventory(self, sha=None):
        return discover(self.root, source_sha=sha or self.git('rev-parse', 'HEAD'), history_base_sha=self.base)

    def test_exact_committed_bytes_ordered_and_worktree_mutation_ignored(self):
        self.write(2); self.write(3); head = self.commit()
        inventory = self.inventory(head)
        before = canonical(inventory.document())
        self.write(2, b'-- changed mutable checkout\n')
        self.assertEqual(before, canonical(self.inventory(head).document()))
        self.assertEqual([m.number for m in inventory.forward(1)], [2,3])
        self.assertEqual(inventory.forward(3), ())
        for origin in (0, True, '1', 4):
            with self.assertRaises(RuntimeError): inventory.forward(origin)

    def test_modified_history_even_matching_mirrors_rejected(self):
        self.write(1, b'-- tampered history\n'); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'history_changed'): self.inventory()

    def test_mirror_mismatch_rejected(self):
        self.write(2); (self.root/'web/supabase/migrations/002_example.sql').write_bytes(b'other')
        self.commit()
        with self.assertRaisesRegex(RuntimeError, 'mirror_changed'): self.inventory()

    def test_gap_rejected(self):
        self.write(3); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'gap'): self.inventory()

    def test_duplicate_version_rejected(self):
        self.write(2); self.write(2, name='002_other.sql'); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'duplicate'): self.inventory()

    def test_symlink_rejected(self):
        self.write(2); path=self.root/'web/database/migrations/002_example.sql'
        path.unlink(); path.symlink_to('../../../elsewhere'); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'regular_nonexecutable'): self.inventory()

    def test_filename_and_executable_modes_rejected(self):
        self.write(2, name='0002_example.sql'); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'noncanonical'): self.inventory()

    def test_nonancestor_and_noncommit_rejected(self):
        self.write(2); head=self.commit(); self.base=head
        old=self.git('rev-parse', 'HEAD^')
        with self.assertRaises(RuntimeError): self.inventory(old)
        with self.assertRaisesRegex(RuntimeError, 'commit_object'): self.inventory(self.git('rev-parse', 'HEAD^{tree}'))
        with self.assertRaisesRegex(RuntimeError, 'exact_commit'): self.inventory('HEAD')

    def test_actions_checkout_official_url_alias(self):
        self.git('remote','set-url','origin','https://github.com/judahsleibi34/Madar')
        self.assertEqual(self.inventory().target,1)

    def test_executable_sql_rejected(self):
        self.write(2)
        (self.root/'web/database/migrations/002_example.sql').chmod(0o755)
        self.commit()
        with self.assertRaisesRegex(RuntimeError,'regular_nonexecutable'): self.inventory()

    def test_untrusted_remote_rejected(self):
        self.git('remote', 'set-url', 'origin', 'https://example.invalid/Madar.git')
        with self.assertRaisesRegex(RuntimeError, 'repository_invalid'): self.inventory()

    def test_huge_future_gap_bounded(self):
        self.write(999999999); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'gap'): self.inventory()


class RiskTests(unittest.TestCase):
    def risk(self, body): return analyze(scaffold(150,151,body), origin=150, target=151)

    def test_narrow_additive_subset(self):
        value=self.risk('CREATE TABLE public.future_example (id pg_catalog.int8 PRIMARY KEY, note pg_catalog.text);')
        self.assertEqual(value.classification, 'A')
        self.assertTrue(value.schema_envelope_verified)
        self.assertFalse(value.document()['runtime_compatibility_proven'])
        self.assertFalse(value.document()['authority_issued'])

    def test_operationally_sensitive(self):
        for sql in ('CREATE INDEX x ON public.example(id);',
                    'ALTER TABLE public.example ADD COLUMN note text;',
                    'ALTER TABLE public.example ALTER COLUMN note SET NOT NULL;',
                    'UPDATE public.example SET note=\'x\' WHERE id>1;'):
            with self.subTest(sql=sql): self.assertEqual(self.risk(sql).classification, 'B')

    def test_coordinated(self):
        for sql in ('REVOKE UPDATE ON public.example FROM service_role;',
                    'ALTER TABLE public.example ENABLE ROW LEVEL SECURITY;',
                    'CREATE FUNCTION public.notification_outbox_protocol() RETURNS int LANGUAGE sql AS $$ SELECT 3 $$;',
                    'CREATE TABLE public.payments (id pg_catalog.int8);'):
            with self.subTest(sql=sql): self.assertEqual(self.risk(sql).classification, 'C')

    def test_unsafe_or_unknown_never_routine(self):
        examples=('DROP TABLE public.example;', 'ALTER TABLE public.example DROP COLUMN id;',
                  'TRUNCATE public.example;', 'DELETE FROM public.example;',
                  'UPDATE public.example SET id=0;', 'DO $$ BEGIN EXECUTE \'SELECT 1\'; END $$;',
                  'CREATE INDEX CONCURRENTLY x ON public.example(id);',
                  'CREATE TABLE public.example (id int DEFAULT 42);',
                  'CREATE TABLE public.example (id text REFERENCES public.other);',
                  'CREATE TABLE IF NOT EXISTS public.example (id pg_catalog.int8);',
                  'CREATE UNLOGGED TABLE public.example (id pg_catalog.int8);',
                  'CREATE TABLE public.example (id custom_type);', 'SELECT privileged_function();',
                  'COMMIT; BEGIN; SELECT 1;', 'nonsense;')
        for sql in examples:
            with self.subTest(sql=sql): self.assertEqual(self.risk(sql).classification, 'D')

    def test_envelope_missing_wrong_or_changed_rejects(self):
        sql=scaffold(150,151,'CREATE TABLE public.example (id pg_catalog.int8);')
        for candidate in (b'CREATE TABLE public.example(id int);', sql.replace(b'FOR UPDATE', b''),
                          sql.replace(b'<> 150', b'<> 149'), sql.replace(b' = 151',b' = 152')):
            with self.subTest(candidate=candidate): self.assertEqual(analyze(candidate,origin=150,target=151).classification,'D')

    def test_comments_cannot_downgrade_destructive_sql(self):
        self.assertEqual(self.risk('-- class: A; atlas:nolint\nDROP TABLE public.example;').classification,'D')

    def test_parser_missing_or_wrong_version_rejects(self):
        import pglast
        with patch.object(pglast,'__version__','untrusted'):
            self.assertEqual(self.risk('CREATE TABLE public.example(id pg_catalog.int8);').classification,'D')
        with patch.dict(sys.modules, {'pglast':None}):
            self.assertEqual(self.risk('CREATE TABLE public.example(id pg_catalog.int8);').classification,'D')

    def test_limits_fail_closed(self):
        for value in (None, '', b'x'*(2*1024*1024+1)):
            self.assertEqual(analyze(value,origin=150,target=151).classification,'D')


if __name__=='__main__': unittest.main()
