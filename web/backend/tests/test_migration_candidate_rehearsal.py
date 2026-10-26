"""CI report/dispatch contracts; synthetic plans/transports, no authority."""
import copy
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from scripts import rehearse_migration_candidate as candidate


class CandidateRehearsalTests(unittest.TestCase):
    def report(self, *, risk='A', origin=150, observed=150, compatible=True,
               protected=False, migrations=True):
        value = {'risk_class':risk, 'compatibility_covers_path':compatible,
                 'execution_class':'transactional',
                 'protected_control_plane_changed':protected,
                 'origin_schema':origin, 'target_schema':151,
                 'migrations':[{'number':151}] if migrations else []}
        plan = SimpleNamespace(sha256='a'*64, document=lambda:copy.deepcopy(value))
        tail = {**copy.deepcopy(value), 'risk_class':'A', 'migrations':[],
                'compatibility_covers_path':False}
        substituted = SimpleNamespace(sha256='d'*64, document=lambda:copy.deepcopy(tail))
        inventory = SimpleNamespace(target=151)
        database = Mock()
        database.execute.side_effect = lambda query: SimpleNamespace(fetchone=lambda:
            (observed,) if 'schema_version' in query else ('123456789',))
        connection = Mock()
        connection.__enter__ = Mock(return_value=database)
        connection.__exit__ = Mock(return_value=False)
        output = io.BytesIO()
        with patch.dict(os.environ, {'CI_SOURCE_SHA':'b'*40, 'CI_HISTORY_BASE_SHA':'c'*40,
                'GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN':'synthetic-fixture-only',
                'GENERIC_MIGRATION_SYNTHETIC_BACKUP':'/unused-synthetic-backup'}), \
             patch.object(candidate, 'discover', side_effect=[SimpleNamespace(target=origin), inventory]), \
             patch.object(candidate, 'generate', side_effect=[plan,substituted]) as generate, \
             patch.object(candidate, 'connect', return_value=connection) as connect, \
             patch.object(candidate, 'run', return_value={'observed_schema':151}) as run, \
             patch.object(candidate.sys, 'stdout', SimpleNamespace(buffer=output)):
            self.assertEqual(candidate.main(), 0)
        return json.loads(output.getvalue()), plan, generate, connect, run

    def test_nonroutine_desired_plan_never_becomes_a_fixture_tail(self):
        for risk in ('B','C','D'):
            with self.subTest(risk=risk):
                report, _, generate, connect, run = self.report(risk=risk, origin=146)
                self.assertEqual((report['status'], report['risk_class']), ('BLOCKED',risk))
                generate.assert_called_once()
                self.assertEqual(generate.call_args.kwargs, {'origin':146})
                connect.assert_not_called(); run.assert_not_called()

    def test_advanced_or_older_fixture_blocks_without_regenerating_the_plan(self):
        for observed in (149,151,152):
            with self.subTest(observed=observed):
                report, plan, generate, _, run = self.report(observed=observed)
                self.assertEqual(report['status'], 'BLOCKED')
                self.assertEqual(report['reason'], 'synthetic_fixture_origin_mismatch')
                self.assertEqual(report['observed_origin'], observed)
                self.assertEqual(report['plan_sha256'], plan.sha256)
                generate.assert_called_once(); run.assert_not_called()

    def test_compatible_exact_origin_executes_only_the_original_plan(self):
        report, plan, generate, _, run = self.report()
        self.assertEqual((report['status'], report['observed_origin']), ('PASS',150))
        generate.assert_called_once()
        self.assertIs(run.call_args.args[2], plan)
        self.assertEqual(report['executed_plan_sha256'], report['plan_sha256'])

    def test_missing_compatibility_or_changed_controller_blocks_before_database(self):
        for values in ({'compatible':False}, {'protected':True}):
            with self.subTest(values=values):
                report, _, generate, connect, run = self.report(**values)
                self.assertEqual((report['status'], report['risk_class']), ('BLOCKED','A'))
                generate.assert_called_once(); connect.assert_not_called(); run.assert_not_called()

    def test_application_only_never_opens_database_or_invents_migration(self):
        report, _, generate, connect, run = self.report(migrations=False)
        self.assertEqual(report['status'], 'NOT_APPLICABLE')
        generate.assert_called_once(); connect.assert_not_called(); run.assert_not_called()
