import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

from test_backup_tooling import BackupToolingTests, ROOT


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


support = load('backup_support')
node1 = load('replicate_latest_node1')


class BackupOperationsTests(unittest.TestCase):
    def make_backup(self, root, timestamp='20260720T000000Z'):
        fixture = BackupToolingTests()
        env = fixture.backup_environment(root, timestamp)
        env['PATH'] = fixture.fake_postgres_tools(root)
        result = fixture.run_script('backup_madar.sh', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(env['MADAR_BACKUP_DIR']) / ('madar-' + timestamp), env

    def test_relocated_storage_needs_no_fictitious_builder_directory(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = BackupToolingTests()
            env = fixture.backup_environment(root)
            storage = Path(root) / 'persistent'
            storage.mkdir()
            for key, name in [('MADAR_BUILDER_ASSETS_DIR','uploads'), ('MADAR_PRIVATE_UPLOADS_DIR','private_uploads'),
                              ('MADAR_GENERATED_ARTIFACTS_DIR','private_generated_charts'), ('MADAR_AVATARS_DIR','avatar_uploads')]:
                Path(env.pop(key)).rename(storage / name)
            env['MADAR_STORAGE_ROOT'] = str(storage)
            env['PATH'] = fixture.fake_postgres_tools(root)
            result = fixture.run_script('backup_madar.sh', env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            copied = Path(env['MADAR_BACKUP_DIR']) / 'madar-20260720T000000Z/files/builder-assets/fixture.txt'
            self.assertEqual(copied.read_text(), 'builder-assets')
            self.assertFalse((storage / 'builder-assets').exists())

    def test_missing_relocated_source_fails_before_dump_and_preserves_latest(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = BackupToolingTests()
            env = fixture.backup_environment(root)
            env['PATH'] = fixture.fake_postgres_tools(root)
            env['MADAR_BUILDER_ASSETS_DIR'] = str(Path(root) / 'missing')
            backups = Path(env['MADAR_BACKUP_DIR']); backups.mkdir()
            marker = backups / 'LATEST'; marker.write_text('previous verified backup')
            env['MADAR_BACKUP_FRESHNESS_MARKER'] = str(marker)
            result = fixture.run_script('backup_madar.sh', env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('builder-assets', result.stderr)
            self.assertEqual(marker.read_text(), 'previous verified backup')
            self.assertEqual(list(backups.iterdir()), [marker])

    def test_provider_credentials_required_no_partial_publication(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = BackupToolingTests()
            env = fixture.backup_environment(root)
            env['PATH'] = fixture.fake_postgres_tools(root)
            env['MADAR_PROVIDER_BACKUP_REQUIRED'] = 'true'
            result = fixture.run_script('backup_madar.sh', env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('provider backup credentials required', result.stderr)
            self.assertFalse(Path(env['MADAR_BACKUP_DIR']).exists())

    def test_integrity_rejects_extra_files_symlinks_and_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            backup, _ = self.make_backup(root)
            support.verify(backup, dump=False)
            extra = backup / 'unlisted'; extra.write_text('tamper')
            with self.assertRaises(support.BackupError): support.verify(backup, dump=False)
            extra.unlink(); extra.symlink_to('/etc/passwd')
            with self.assertRaises(support.BackupError): support.verify(backup, dump=False)
            extra.unlink()
            with (backup / 'SHA256SUMS').open('a') as sums: sums.write('0'*64 + '  ../escape\n')
            with self.assertRaisesRegex(support.BackupError, 'checksum_path'): support.verify(backup, dump=False)

    def test_latest_rejects_outside_root_and_stale_creation_even_after_touch(self):
        with tempfile.TemporaryDirectory() as root:
            backup, env = self.make_backup(root)
            marker = backup.parent / 'LATEST'
            marker.write_text('20260720T000000Z ' + str(backup) + '\n')
            with self.assertRaisesRegex(support.BackupError, 'stale'): support.latest(marker, backup.parent)
            marker.write_text('20260720T000000Z /elsewhere/madar-20260720T000000Z\n')
            with self.assertRaisesRegex(support.BackupError, 'outside'): support.latest(marker, backup.parent)

    def test_retention_preserves_current_newest_unknown_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            backup, _ = self.make_backup(root)
            import shutil
            for day in ('21', '22', '23'):
                target = backup.parent / ('madar-202607' + day + 'T000000Z')
                shutil.copytree(backup, target)
                manifest = json.loads((target / 'manifest.json').read_text())
                manifest['backup_id'] = target.name
                manifest['created_at'] = target.name[6:]
                (target / 'manifest.json').write_text(json.dumps(manifest))
                files = support.inventory(target); files.pop('SHA256SUMS')
                (target / 'SHA256SUMS').write_text(''.join(f'{v}  {k}\n' for k,v in files.items()))
            unknown = backup.parent / 'operator-evidence'; unknown.mkdir()
            link = backup.parent / 'madar-20260101T000000Z'; link.symlink_to(unknown)
            removed = support.retention(backup.parent, backup, 2)
            self.assertEqual(removed, ['madar-20260721T000000Z'])
            self.assertTrue(backup.exists()); self.assertTrue(unknown.exists()); self.assertTrue(link.is_symlink())
            with self.assertRaises(support.BackupError): support.retention(backup.parent, backup, 1)

    def archive(self, source):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            archive.add(source, arcname='.')
        stream.seek(0)
        return stream

    def test_node1_publish_rerun_integrity_and_partial_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            source, _ = self.make_backup(root)
            destination = Path(root) / 'remote'; destination.mkdir(mode=0o700)
            sums = support.digest(source / 'SHA256SUMS')
            with mock.patch.object(node1, 'DESTINATION', destination), mock.patch.object(node1, 'validate_destination'), mock.patch.object(node1.shutil, 'disk_usage', return_value=mock.Mock(free=100*1024**3)):
                for expected in ('replicated', 'already_verified'):
                    result = node1.receive(source.name, sums, 'test', 90, stream=self.archive(source))
                    self.assertEqual(result['status'], expected)
                latest = (destination / 'LATEST').read_bytes()
                with self.assertRaises(support.BackupError):
                    node1.receive(source.name, '0'*64, 'test', 90, stream=self.archive(source))
                self.assertEqual((destination / 'LATEST').read_bytes(), latest)
                self.assertFalse(list(destination.glob('.*.incomplete.*')))
                support.verify(destination / source.name, dump=False)

    def test_node1_rejects_wrong_filesystem_before_writes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            with mock.patch.object(node1, 'DESTINATION', path), mock.patch.object(node1.subprocess, 'run', return_value=mock.Mock(stdout='/dev/sdb1 ext4 /srv/data1 wrong')):
                with self.assertRaisesRegex(support.BackupError, 'filesystem_identity'):
                    node1.validate_destination(path, 'aafa8641-ab59-4927-9146-c1f9bf9abf3f')
            self.assertEqual(list(path.iterdir()), [])

    def test_node1_archive_rejects_traversal_and_links(self):
        for name, kind in [('../outside', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as root:
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode='w') as archive:
                    member = tarfile.TarInfo(name); member.type = kind; member.linkname = '/etc/passwd'
                    archive.addfile(member)
                stream.seek(0)
                with self.assertRaises(support.BackupError): node1.extract(stream, Path(root))
                self.assertEqual(list(Path(root).iterdir()), [])

    def test_remote_command_is_quoted_python_and_has_no_shell_interpolation(self):
        args = shlex.split(node1.remote_command('madar-20260720T000000Z', 'a'*64, 'uuid', 90))
        self.assertEqual(args[:2], ['python3', '-c'])
        compile(args[2], '<receiver>', 'exec')
        self.assertEqual(args[-4:], ['madar-20260720T000000Z', 'a'*64, 'uuid', '90'])

    def test_provider_change_during_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root); (path / 'provider-inventory.json').write_text('[]')
            with mock.patch.dict(os.environ, {'SUPABASE_URL':'https://provider.invalid','SUPABASE_SERVICE_KEY':'synthetic'}), mock.patch.object(support, 'provider_inventory', return_value=[{'changed': True}]):
                with self.assertRaisesRegex(support.BackupError, 'inventory_changed'):
                    support.provider_snapshot(path, 'madar-20260720T000000Z')
            self.assertFalse((path / 'provider/manifest.json').exists())

    def test_marker_atomic_replacement_exposes_only_private_backup_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            source, env = self.make_backup(root)
            state = Path(root) / 'state'; state.mkdir(mode=0o755)
            marker = source.parent / 'LATEST'
            with mock.patch.dict(os.environ, {'PATH':env['PATH']}):
                support.publish_marker(source, marker, state)
                with (state / 'latest.json').open() as old:
                    old_inode = os.fstat(old.fileno()).st_ino
                    support.publish_marker(source, marker, state)
                    self.assertNotEqual(old_inode, (state / 'latest.json').stat().st_ino)
            metadata = json.loads((state / 'latest.json').read_text())
            self.assertEqual(set(metadata), {'format','backup_id','created_at','verified','manifest_sha256'})
            self.assertEqual((state / 'latest.json').stat().st_mode & 0o777, 0o644)
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
