"""Safety boundaries; actual business acceptance runs in the owned KVM guest."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB))
spec = importlib.util.spec_from_file_location('running146_business', WEB/'staging/integration/running146_business_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class BusinessFixtureSafetyTests(unittest.TestCase):
    def test_receiver_probe_cannot_redirect_credentials_to_an_external_endpoint(self):
        with patch.object(fixture.urllib.request, 'build_opener') as opener:
            for endpoint in ('https://attacker.invalid', 'http://proxy:8001@attacker.invalid',
                             'http://127.0.0.1:5432'):
                with self.subTest(endpoint=endpoint), self.assertRaisesRegex(RuntimeError, 'private_application_endpoint_required'):
                    fixture.api({}, application_base=endpoint)
            opener.assert_not_called()

    def test_unprivileged_actor_cannot_read_credentials_or_invoke_docker(self):
        with patch.object(fixture.os, 'geteuid', return_value=1000), \
                patch.object(fixture.subprocess, 'check_output') as command, \
                patch.object(Path, 'read_bytes') as read:
            with self.assertRaisesRegex(RuntimeError, 'owned_kvm_required'):
                fixture.owned_inputs()
            read.assert_not_called()
            command.assert_not_called()

    def test_physical_host_cannot_read_fixture_credentials(self):
        with patch.object(fixture.os, 'geteuid', return_value=0), \
                patch.object(fixture.subprocess, 'check_output', return_value=b'none\n') as command, \
                patch.object(Path, 'read_bytes') as read:
            with self.assertRaisesRegex(RuntimeError, 'owned_kvm_required'):
                fixture.owned_inputs()
            read.assert_not_called()
            command.assert_called_once_with(['systemd-detect-virt'])

    def test_enrolled_origin_cannot_be_reseeded_or_extended(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'state.json'
            state.write_text(json.dumps({'known_good_release': {'historical_origin': {'request_id': 'enrolled'}}}))
            db = Mock()
            with patch.object(fixture, 'ROOT', Path(directory)), patch.object(fixture, 'RELEASE_STATE', state):
                with self.assertRaisesRegex(RuntimeError, 'already_enrolled'):
                    fixture.seed(db, [{'tenant_id': 1}])
                with self.assertRaisesRegex(RuntimeError, 'already_enrolled'):
                    fixture.complete_original_data(db, {}, [{'tenant_id': 1}], [{}])
            db.assert_not_called()
            self.assertEqual(db.mock_calls, [])
            self.assertFalse((Path(directory)/'business-seed-intent.json').exists())

    def test_interrupted_intent_cannot_silently_replay_inserts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root/'state.json'
            state.write_text(json.dumps({'known_good_release': {}}))
            intent = root/'business-seed-intent.json'
            intent.write_bytes(b'prior immutable seed intent\n')
            db = Mock()
            with patch.object(fixture, 'ROOT', root), patch.object(fixture, 'RELEASE_STATE', state):
                with self.assertRaises((RuntimeError, FileExistsError)):
                    fixture.seed(db, [{'tenant_id': 1}])
            self.assertEqual(intent.read_bytes(), b'prior immutable seed intent\n')
            self.assertEqual(db.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
