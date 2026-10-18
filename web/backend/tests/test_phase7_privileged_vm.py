"""VM refusal boundaries; no packages, QEMU guests, or services are changed."""
import json
import os
import io
from pathlib import Path
import sys
import tempfile
import subprocess
import tarfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import phase7_privileged_vm as vm


class PrivilegedVmSafetyTests(unittest.TestCase):
    def test_wrong_mode_or_mutable_source_refuses_before_host_access(self):
        for mode, source in (('EXECUTE', 'a' * 40), ('PREPARE', 'main'), ('REHEARSE', None)):
            with self.subTest(mode=mode), patch.object(vm, 'host') as host:
                with self.assertRaises(RuntimeError): vm.main(mode, source)
                host.assert_not_called()

    def test_primary_host_and_root_user_refuse_before_tools_or_files(self):
        for hostname, uid in (('madar-gpu', 1000), ('madar-staging', 0)):
            with self.subTest(host=hostname), patch.object(vm.socket, 'gethostname', return_value=hostname), \
                    patch.object(vm.os, 'getuid', return_value=uid), patch.object(vm, 'prepare') as prepare:
                with self.assertRaises(RuntimeError): vm.main('PREPARE', 'a' * 40)
                prepare.assert_not_called()

    def test_inspect_never_prepares_starts_or_downloads(self):
        with patch.object(vm, 'host'), patch.object(vm, 'dependencies', return_value=['qemu-img']), \
                patch.object(vm, 'prepare') as prepare, patch.object(vm, 'rehearse') as rehearse, \
                patch.object(vm, 'run') as run:
            result = vm.main('INSPECT', 'a' * 40)
            self.assertFalse(result['mutations_executed'])
            self.assertEqual(result['missing_dependencies'], ['qemu-img'])
            prepare.assert_not_called(); rehearse.assert_not_called(); run.assert_not_called()

    def test_existing_preparation_is_preserved_without_any_command(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(vm, 'root', return_value=Path(directory)), \
                patch.object(vm, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'already_consumed'): vm.prepare('a' * 40)
            run.assert_not_called()

    def test_missing_dependencies_reject_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'uncreated'
            with patch.object(vm, 'root', return_value=target), patch.object(vm, 'dependencies', return_value=['qemu-img']), \
                    patch.object(vm, 'headroom') as headroom:
                with self.assertRaisesRegex(RuntimeError, 'dependencies_missing'): vm.prepare('a' * 40)
                self.assertFalse(target.exists()); headroom.assert_not_called()

    def test_directory_lock_excludes_another_actor_without_lockfiles(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with vm.lock(target):
                with self.assertRaisesRegex(RuntimeError, 'busy'):
                    with vm.lock(target): self.fail('Concurrent actor admitted')
            with vm.lock(target): pass
            self.assertEqual(list(target.iterdir()), [])

    def test_private_inputs_reject_symlink_shared_mode_and_oversize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); private = root / 'private'; private.write_bytes(b'fixture'); private.chmod(0o600)
            link = root / 'link'; link.symlink_to(private)
            with self.assertRaises(OSError): vm.read(link)
            with self.assertRaises(RuntimeError): vm.read(private, maximum=2)
            private.chmod(0o644)
            with self.assertRaises(RuntimeError): vm.read(private)

    def test_qemu_has_only_bounded_owned_disks_restricted_user_network_and_loopback(self):
        with patch.object(vm, 'root', return_value=Path('/private/owned')):
            arguments = vm.qemu_command()
        self.assertEqual(arguments[:8], ['sudo', '-n', '-u', 'staging-admin', '-g', 'kvm', '--', 'qemu-system-x86_64'])
        self.assertEqual(arguments[arguments.index('-m') + 1], '1024')
        self.assertEqual(arguments[arguments.index('-smp') + 1], '1')
        self.assertIn('restrict=on', arguments[arguments.index('-netdev') + 1])
        self.assertIn('hostfwd=tcp:127.0.0.1:23222-:22', arguments[arguments.index('-netdev') + 1])
        for forbidden in ('-virtfs', '-fsdev', '-virtiofs', '-chardev', '-vnc', '-spice', '-qmp', '-incoming'):
            self.assertNotIn(forbidden, arguments)
        drives = [arguments[index + 1] for index, value in enumerate(arguments) if value == '-drive']
        self.assertEqual(len(drives), 2)
        self.assertTrue(all(value.startswith('file=/private/owned/') for value in drives))
        self.assertFalse(any('backing' in value for value in drives))
        self.assertNotIn('-daemonize', arguments)
        self.assertEqual(arguments[arguments.index('-sandbox') + 1],
                         'on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny')

    def repair_fixture(self, root):
        source = 'a' * 40
        owner = {'owner': vm.NAME, 'source_sha': source}
        files = {'guest.qcow2': b'initial disk', 'seed.iso': b'initial seed', 'source.tar': b'initial source',
                 'serial.log': b'', 'failure-1.log': b'',
                 'daemon-nonboot-strace.1': b'seccomp(SECCOMP_SET_MODE_FILTER, flags, filter) = 0\nclone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID|CLONE_CHILD_SETTID|SIGCHLD, child_tidptr=0x1) = -1 EPERM (Operation not permitted)\nexit_group(1)\n',
                 'boot-attempt.json': json.dumps({'source_sha': source, 'started_at': 1}).encode(),
                 'owner.json': json.dumps(owner).encode()}
        prepared = {**owner, 'production_authority': False,
                    'disk_sha256_before_first_boot': vm.hashlib.sha256(files['guest.qcow2']).hexdigest(),
                    'seed_sha256': vm.hashlib.sha256(files['seed.iso']).hexdigest(),
                    'source_archive_sha256': vm.hashlib.sha256(files['source.tar']).hexdigest()}
        files['prepared.json'] = json.dumps(prepared).encode()
        for name, body in files.items():
            (root / name).write_bytes(body); (root / name).chmod(0o600)
        return source

    def test_repair_requires_explicit_committed_driver_before_host_access(self):
        for mode, driver in (('REPAIR', None), ('REPAIR', 'main'), ('REHEARSE', 'b' * 40)):
            with self.subTest(mode=mode, driver=driver), patch.object(vm, 'host') as host:
                with self.assertRaises(RuntimeError): vm.main(mode, 'a' * 40, driver)
                host.assert_not_called()

    def test_repair_preserves_consumed_attempt_and_separates_driver_from_guest_source(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); source = self.repair_fixture(target)
            original = (target / 'boot-attempt.json').read_bytes()
            with patch.object(vm, 'root', return_value=target), patch.object(vm, 'no_existing_guest'), \
                    patch.object(vm, 'dependencies', return_value=[]), patch.object(vm, 'headroom'), \
                    patch.object(vm, 'run', return_value=json.dumps({'format': 'qcow2', 'virtual-size': 8 * 1024**3}).encode()), \
                    patch.object(vm, 'authenticate_repair_driver', return_value='c' * 64), \
                    patch.object(vm, 'launch_foreground', side_effect=RuntimeError('test stops before actual VM')) as launch:
                with self.assertRaisesRegex(RuntimeError, 'test stops'): vm.rehearse(source, 'b' * 40)
                launch.assert_called_once()
            self.assertEqual((target / 'boot-attempt.json').read_bytes(), original)
            receipt = json.loads((target / 'repair-attempt.json').read_text())
            self.assertEqual(receipt['source_sha'], source)
            self.assertEqual(receipt['repair_driver_sha'], 'b' * 40)
            self.assertEqual(receipt['original_boot_attempt_sha256'], vm.hashlib.sha256(original).hexdigest())

    def test_repair_rejects_any_changed_initial_content_before_driver_or_launch(self):
        for changed in ('guest.qcow2', 'seed.iso', 'source.tar'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                target = Path(directory); source = self.repair_fixture(target)
                (target / changed).write_bytes(b'changed')
                with patch.object(vm, 'root', return_value=target), patch.object(vm, 'no_existing_guest'), \
                        patch.object(vm, 'dependencies', return_value=[]), patch.object(vm, 'headroom'), \
                        patch.object(vm, 'run', return_value=json.dumps({'format': 'qcow2', 'virtual-size': 8 * 1024**3}).encode()), \
                        patch.object(vm, 'authenticate_repair_driver') as driver, patch.object(vm, 'launch_foreground') as launch:
                    with self.assertRaisesRegex(RuntimeError, 'changed'): vm.rehearse(source, 'b' * 40)
                    driver.assert_not_called(); launch.assert_not_called()
                    self.assertFalse((target / 'repair-attempt.json').exists())

    def test_repair_rejects_started_unknown_or_repeated_attempts(self):
        for changed, body in (('serial.log', b'guest kernel started'), ('failure-1.log', b'other error'),
                              ('daemon-nonboot-strace.1', b'unknown failure'), ('repair-attempt.json', b'{}'),
                              ('rehearsal.json', b'{}'), ('boot-attempt.json', b'{"source_sha":"other"}')):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                target = Path(directory); source = self.repair_fixture(target)
                (target / changed).write_bytes(body); (target / changed).chmod(0o600)
                with patch.object(vm, 'root', return_value=target), patch.object(vm, 'no_existing_guest'):
                    with self.assertRaises(RuntimeError): vm.validate_unstarted_repair(source)

    def test_existing_pid_even_broken_symlink_blocks_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); (target / 'qemu.pid').symlink_to(target / 'missing')
            with patch.object(vm, 'root', return_value=target), patch.object(vm.socket, 'socket') as socket:
                with self.assertRaisesRegex(RuntimeError, 'existing_pid'): vm.no_existing_guest()
                socket.assert_not_called()

    def test_matching_live_qemu_process_blocks_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); process = target / '123'; process.mkdir()
            (process / 'cmdline').write_bytes(b'/usr/bin/qemu-system-x86_64\0-name\0' + vm.NAME.encode() + b'\0')
            actual = Path.iterdir
            def entries(path): return iter([process]) if path == Path('/proc') else actual(path)
            with patch.object(vm, 'root', return_value=target), patch.object(Path, 'iterdir', entries), patch.object(vm.socket, 'socket') as socket:
                with self.assertRaisesRegex(RuntimeError, 'existing_process'): vm.no_existing_guest()
                socket.assert_not_called()

    def test_existing_loopback_listener_blocks_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(vm, 'root', return_value=Path(directory)), \
                    patch.object(Path, 'iterdir', return_value=iter(())), patch.object(vm.socket, 'socket') as socket:
                socket.return_value.__enter__.return_value.bind.side_effect = OSError('Address already in use')
                with self.assertRaises(OSError): vm.no_existing_guest()
                socket.return_value.__enter__.return_value.bind.assert_called_once_with(('127.0.0.1', vm.PORT))

    def test_repair_driver_must_match_exact_git_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); bundle = target / vm.BUNDLE; bundle.mkdir(mode=0o700)
            (bundle / 'source.pack').write_bytes(b'fixed pack'); (bundle / 'source.pack').chmod(0o600)
            with patch.object(Path, 'home', return_value=target), patch.object(vm, 'root', return_value=target), \
                    patch.object(vm, 'run', return_value=b'substituted driver'):
                with self.assertRaisesRegex(RuntimeError, 'driver_source_changed'): vm.authenticate_repair_driver('b' * 40)

    def test_foreground_launcher_starts_new_session_without_weakening_qemu_sandbox(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            class Process:
                def poll(self): return 1
            with patch.object(vm, 'root', return_value=target), patch.object(vm.subprocess, 'Popen', return_value=Process()) as popen:
                with self.assertRaisesRegex(RuntimeError, 'foreground_launch_failed'): vm.launch_foreground()
            self.assertTrue(popen.call_args.kwargs['start_new_session'])
            self.assertTrue(popen.call_args.kwargs['close_fds'])
            self.assertNotIn('-daemonize', popen.call_args.args[0])
            self.assertIn('on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny', popen.call_args.args[0])

    def test_launcher_returns_attested_qemu_pid_instead_of_sudo_pid(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); (target / 'qemu.pid').write_text('424242')
            arguments = (b'/usr/bin/qemu-system-x86_64\0-name\0' + vm.NAME.encode()
                         + b'\0-drive\0file=' + str(target / 'guest.qcow2').encode() + b',if=virtio\0')
            actual_read, actual_stat = Path.read_bytes, Path.stat
            def read(path): return arguments if path == Path('/proc/424242/cmdline') else actual_read(path)
            def stat(path, *args, **kwargs):
                return SimpleNamespace(st_uid=os.getuid()) if path == Path('/proc/424242') else actual_stat(path, *args, **kwargs)
            process = SimpleNamespace(pid=111111, poll=lambda: None)
            with patch.object(vm, 'root', return_value=target), patch.object(vm.subprocess, 'Popen', return_value=process), \
                    patch.object(Path, 'read_bytes', read), patch.object(Path, 'stat', stat):
                self.assertEqual(vm.launch_foreground(), 424242)

    def test_ssh_pins_guest_host_key_ignores_host_user_configuration_and_agent(self):
        with patch.object(vm, 'root', return_value=Path('/private/owned')):
            arguments = vm.ssh_arguments()
        self.assertIn('StrictHostKeyChecking=yes', arguments)
        self.assertIn('IdentitiesOnly=yes', arguments)
        self.assertIn('GlobalKnownHostsFile=/dev/null', arguments)
        self.assertIn('ProxyCommand=none', arguments); self.assertIn('ProxyJump=none', arguments)
        self.assertEqual(arguments[arguments.index('-F') + 1], '/dev/null')
        self.assertEqual(arguments[-1], 'madar-vm@127.0.0.1')

    def test_wrong_owner_source_or_consumed_boot_cannot_launch(self):
        for consumed in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                owner = {'owner': vm.NAME, 'source_sha': 'a' * 40}
                prepared = {**owner, 'production_authority': False}
                for name, value in (('owner.json', owner), ('prepared.json', prepared)):
                    (root / name).write_text(json.dumps(value)); (root / name).chmod(0o600)
                if consumed: (root / 'boot-attempt.json').write_text('{}')
                with self.subTest(consumed=consumed), patch.object(vm, 'root', return_value=root), patch.object(vm, 'run') as run:
                    marker = 'already_consumed' if consumed else 'owner_or_source_mismatch'
                    with self.assertRaisesRegex(RuntimeError, marker): vm.rehearse('a' * 40 if consumed else 'b' * 40)
                    run.assert_not_called()

    def test_untrusted_signer_or_changed_official_pin_rejects_before_image_use(self):
        for signer, checksum, marker in (('0' * 40, vm.IMAGE_SHA256, 'signature_identity'),
                                         (vm.SIGNER, '0' * 64, 'image_pin')):
            with tempfile.TemporaryDirectory() as directory:
                home = Path(directory); bundle = home / vm.BUNDLE; bundle.mkdir(mode=0o700)
                target = home / vm.NAME; target.mkdir(mode=0o700)
                for name, value in (('SHA256SUMS', checksum + ' *' + vm.IMAGE + '\n'), ('SHA256SUMS.gpg', 'synthetic signature')):
                    (bundle / name).write_text(value); (bundle / name).chmod(0o600)
                actual_read = vm.read
                def read(path, *args, **kwargs):
                    return b'trusted installed root keyring' if path == vm.KEYRING else actual_read(path, *args, **kwargs)
                with self.subTest(signer=signer), patch.object(Path, 'home', return_value=home), \
                        patch.object(vm, 'root', return_value=target), patch.object(vm, 'read', side_effect=read), \
                        patch.object(vm, 'run', return_value=('[GNUPG:] VALIDSIG ' + signer + '\n').encode()) as run:
                    with self.assertRaisesRegex(RuntimeError, marker): vm.authenticate_bundle()
                    self.assertEqual(run.call_count, 1)
                    self.assertEqual(run.call_args.args[0][0], 'gpgv')

    def test_source_pack_reconstructs_exact_committed_tree_without_history_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); repository = home / 'fixture.git'
            def git(*args, data=None):
                result = subprocess.run(['git', '-C', str(repository), *args], input=data, capture_output=True, check=True)
                return result.stdout.strip()
            subprocess.run(['git', 'init', '--quiet', '--bare', str(repository)], check=True)
            blob = git('hash-object', '-w', '--stdin', data=b'synthetic isolated source\n').decode()
            tree = git('mktree', data=('100644 blob ' + blob + '\tfixture.txt\n').encode()).decode()
            identity = 'Saliba Rishmawi <75858844+Saliba-codes@users.noreply.github.com> 1 +0000'
            commit = git('hash-object', '-t', 'commit', '-w', '--stdin', data=(
                'tree ' + tree + '\nauthor ' + identity + '\ncommitter ' + identity + '\n\nSynthetic fixture\n').encode()).decode()
            pack = git('pack-objects', '--stdout', data=('\n'.join((commit, tree, blob)) + '\n').encode())
            bundle = home / vm.BUNDLE; bundle.mkdir(mode=0o700)
            (bundle / 'source.pack').write_bytes(pack); (bundle / 'source.pack').chmod(0o600)
            target = home / vm.NAME; target.mkdir(mode=0o700)
            with patch.object(Path, 'home', return_value=home), patch.object(vm, 'root', return_value=target), \
                    patch.object(vm, 'REPOSITORY', home / 'archive-without-git'):
                digest = vm.capture_source(commit)
            self.assertEqual(digest, vm.hashlib.sha256((target / 'source.tar').read_bytes()).hexdigest())
            with tarfile.open(fileobj=io.BytesIO((target / 'source.tar').read_bytes())) as archive:
                self.assertEqual(archive.extractfile('source/fixture.txt').read(), b'synthetic isolated source\n')
            self.assertEqual(json.loads((target / 'source-export.json').read_text())['mode'], 'fixed-content-addressed-source-pack')

    def test_qemu_consumes_authenticated_snapshot_after_original_inplace_or_path_substitution(self):
        for replace_path in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                home = Path(directory); bundle = home / vm.BUNDLE; bundle.mkdir(mode=0o700)
                target = home / vm.NAME; target.mkdir(mode=0o700)
                original = b'authenticated official image fixture'
                digest = vm.hashlib.sha256(original).hexdigest()
                image = bundle / vm.IMAGE
                for name, value in (('SHA256SUMS', (digest + ' *' + vm.IMAGE + '\n').encode()),
                                    ('SHA256SUMS.gpg', b'synthetic signature'), (vm.IMAGE, original)):
                    (bundle / name).write_bytes(value); (bundle / name).chmod(0o600)
                actual_read = vm.read
                def read(path, *args, **kwargs):
                    return b'trusted installed root keyring' if path == vm.KEYRING else actual_read(path, *args, **kwargs)
                consumed = []
                def command(args, **kwargs):
                    if args[0] == 'gpgv': return ('[GNUPG:] VALIDSIG ' + vm.SIGNER + '\n').encode()
                    if args[:2] == ['qemu-img', 'info']:
                        if replace_path: image.rename(bundle / 'prior-image')
                        image.write_bytes(b'malicious changed original bytes'); image.chmod(0o600)
                        consumed.append(os.pread(kwargs['pass_fds'][0], len(original), 0))
                        return json.dumps({'format': 'qcow2', 'virtual-size': 1024**3}).encode()
                    if args[:2] == ['qemu-img', 'convert']:
                        consumed.append(os.pread(kwargs['pass_fds'][0], len(original), 0))
                        Path(args[-1]).write_bytes(b'standalone converted fixture')
                        return b''
                    if args[:2] == ['qemu-img', 'resize']: return b''
                    self.fail('Unexpected command')
                with self.subTest(replace_path=replace_path), patch.object(Path, 'home', return_value=home), \
                        patch.object(vm, 'root', return_value=target), patch.object(vm, 'IMAGE_MIN_BYTES', 1), \
                        patch.object(vm, 'IMAGE_SHA256', digest), patch.object(vm, 'read', side_effect=read), \
                        patch.object(vm, 'run', side_effect=command):
                    vm.authenticate_bundle()
                self.assertEqual(consumed, [original, original])
                self.assertNotEqual(image.read_bytes(), original)


if __name__ == '__main__': unittest.main()
