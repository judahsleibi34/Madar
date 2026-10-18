"""Safety boundaries of the new independent schema149 staging acceptance target."""
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import schema149_acceptance as acceptance


class Schema149AcceptanceSafetyTests(unittest.TestCase):
    def test_primary_host_rejects_before_inspection_or_mutation(self):
        for mode in ('INSPECT', 'REHEARSE'):
            with self.subTest(mode=mode), patch.object(acceptance.manage.socket, 'gethostname', return_value='madar-gpu'), \
                    patch.object(acceptance, 'artifacts') as artifacts, patch.object(acceptance.manage, 'docker') as docker:
                with self.assertRaises(RuntimeError):
                    acceptance.main(mode, Path.home() / 'private', 'a' * 40)
                artifacts.assert_not_called(); docker.assert_not_called()

    def test_unknown_mode_and_mutable_source_reject_before_artifact_use(self):
        for mode, source in (('EXECUTE', 'a' * 40), ('REHEARSE', 'development')):
            with self.subTest(mode=mode), patch.object(acceptance.manage, 'require_staging_host'), \
                    patch.object(acceptance, 'artifacts') as artifacts:
                with self.assertRaises(RuntimeError):
                    acceptance.main(mode, Path.home() / 'private', source)
                artifacts.assert_not_called()

    def test_inspect_never_prepares_or_touches_docker(self):
        with patch.object(acceptance.manage, 'require_staging_host'), \
                patch.object(acceptance, 'artifacts', return_value=({}, {}, {}, {})), \
                patch.object(acceptance, 'prepare') as prepare, patch.object(acceptance.manage, 'docker') as docker:
            acceptance.main('INSPECT', Path.home() / 'private', 'a' * 40)
            prepare.assert_not_called(); docker.assert_not_called()

    def test_object_archive_rejects_traversal_links_and_special_files(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('link', tarfile.SYMTYPE), ('device', tarfile.CHRTYPE)):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as archive:
                entry = tarfile.TarInfo(name); entry.type = kind; archive.addfile(entry)
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                acceptance.archive_members(buffer.getvalue())

    def test_existing_target_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as raw:
            with patch.object(acceptance.manage, 'docker') as docker, self.assertRaisesRegex(RuntimeError, 'Preserve'):
                acceptance.prepare(Path(raw), Path(raw), 'a' * 40, {}, {})
            docker.assert_not_called()

    def test_fixture_and_artifact_scope_reject_symbolic_links(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); real = root / 'real'; real.write_text('private fixture')
            alias = root / 'alias'; alias.symlink_to(real)
            with self.assertRaises(RuntimeError): acceptance.regular(alias)
            with self.assertRaises(RuntimeError): acceptance.artifacts(root, 'a' * 40)

    def test_resume_requires_explicit_rehearse_before_resource_access(self):
        with patch.object(acceptance.manage, 'require_staging_host'), \
                patch.object(acceptance.manage, 'state') as state:
            with self.assertRaises(RuntimeError):
                acceptance.resume_application('INSPECT', Path.home() / 'private', 'a' * 40)
            state.assert_not_called()

    def test_resume_cannot_adopt_a_different_source(self):
        with patch.object(acceptance.manage, 'require_staging_host'), \
                patch.object(acceptance.manage, 'state', return_value={'source_sha': 'b' * 40}), \
                patch.object(acceptance.manage, 'attest_resources'), \
                patch.object(acceptance, 'artifacts') as artifacts, patch.object(acceptance.manage, 'compose') as compose:
            with self.assertRaisesRegex(RuntimeError, 'different source'):
                acceptance.resume_application('REHEARSE', Path.home() / 'private', 'a' * 40)
            artifacts.assert_not_called(); compose.assert_not_called()


if __name__ == '__main__':
    unittest.main()
