#!/usr/bin/env python3
"""Fixed owned KVM guest for privileged tests; no production authority or mounts.

INSPECT is read-only. PREPARE authenticates a parent-provisioned official image
bundle and creates standalone guest files. REHEARSE explicitly boots that guest,
copies an exact committed source archive, and proves guest root/systemd access.
This does not install or accept Madar's privileged production controller.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import tarfile
import tempfile
import time

NAME = 'madar-phase7-privileged-20261018'
BUNDLE = 'madar-phase7-official-cloudimage-20261018'
GUEST = 'madar-phase7-guest'
GUEST_USER = 'madar-vm'
PORT = 23222
MEMORY_MIB, CPUS, DISK_GIB = 1024, 1, 8
IMAGE = 'noble-server-cloudimg-amd64.img'
IMAGE_SHA256 = '04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94'
IMAGE_MIN_BYTES, IMAGE_MAX_BYTES = 100 * 1024**2, 1024**3
KEYRING = Path('/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg')
SIGNER = 'D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81'
OFFICIAL = 'https://cloud-images.ubuntu.com/noble/current/'
REPOSITORY = Path(__file__).resolve().parents[3]
TOOLS = ('qemu-system-x86_64', 'qemu-img', 'cloud-localds', 'gpgv', 'ssh-keygen', 'ssh', 'scp', 'git')


def root(): return Path.home() / NAME


def host():
    if socket.gethostname() != 'madar-staging' or os.getuid() == 0:
        raise RuntimeError('phase7_vm_requires_dedicated_staging_unprivileged_owner')
    if root().is_symlink() or root().parent.resolve() != Path.home().resolve():
        raise RuntimeError('phase7_vm_ambiguous_root')


def private_directory(path):
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o700:
        raise RuntimeError('phase7_vm_directory_ownership_invalid')


@contextmanager
def lock(path):
    private_directory(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('phase7_vm_busy') from None
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError('phase7_vm_directory_replaced')
        yield
    finally: os.close(fd)


def read(path, maximum=2 * 1024**2, *, root_owned=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        value = os.fstat(stream.fileno())
        if (not stat.S_ISREG(value.st_mode) or value.st_uid != (0 if root_owned else os.getuid())
                or value.st_mode & (0o022 if root_owned else 0o077) or value.st_size > maximum):
            raise RuntimeError('phase7_vm_file_ownership_or_size_invalid')
        body = stream.read(maximum + 1)
    if len(body) > maximum: raise RuntimeError('phase7_vm_file_too_large')
    return body


def write(name, value):
    body = value.encode() if isinstance(value, str) else value
    fd = os.open(root() / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())


def run(arguments, *, data=None, timeout=120, pass_fds=()):
    result = subprocess.run(arguments, input=data, capture_output=True, timeout=timeout, pass_fds=pass_fds,
        env={'PATH': os.defpath, 'HOME': str(Path.home())})
    if result.returncode:
        # SSH/cloud-init errors may include private material. Preserve only in
        # this owned directory; never print command output or credentials.
        if root().is_dir():
            name = 'failure-' + str(time.time_ns()) + '.log'
            write(name, result.stdout[-65536:] + result.stderr[-65536:])
        raise RuntimeError('phase7_vm_command_failed_private_diagnostic_retained')
    return result.stdout


def dependencies(): return [name for name in TOOLS if shutil.which(name) is None]


def digest_file(path, maximum=2 * 1024**3):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        value = os.fstat(fd)
        if (not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid()
                or value.st_mode & 0o077 or value.st_size > maximum):
            raise RuntimeError('phase7_vm_private_image_invalid')
        digest = hashlib.sha256()
        while block := os.read(fd, 1024**2): digest.update(block)
        return digest.hexdigest()
    finally: os.close(fd)


def headroom():
    if shutil.disk_usage(Path.home()).free < 12 * 1024**3:
        raise RuntimeError('phase7_vm_disk_headroom_insufficient')
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    if available < 2300 * 1024: raise RuntimeError('phase7_vm_memory_headroom_insufficient')


@contextmanager
def authenticated_image_snapshot(path):
    """Consume an authenticated unnamed copy, never the writable bundle inode."""
    original = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        value = os.fstat(original)
        if (not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid() or value.st_mode & 0o077
                or not IMAGE_MIN_BYTES < value.st_size <= IMAGE_MAX_BYTES):
            raise RuntimeError('phase7_vm_official_image_file_invalid')
        with tempfile.TemporaryFile(dir=root()) as snapshot:
            digest, size = hashlib.sha256(), 0
            while block := os.read(original, 1024**2):
                size += len(block)
                if size > IMAGE_MAX_BYTES: raise RuntimeError('phase7_vm_official_image_file_invalid')
                snapshot.write(block); digest.update(block)
            if digest.hexdigest() != IMAGE_SHA256:
                raise RuntimeError('phase7_vm_official_image_digest_invalid')
            snapshot.flush(); os.fsync(snapshot.fileno()); snapshot.seek(0)
            yield snapshot.fileno()
    finally: os.close(original)


def authenticate_bundle():
    bundle = Path.home() / BUNDLE; private_directory(bundle)
    checksums, signature = read(bundle / 'SHA256SUMS'), read(bundle / 'SHA256SUMS.gpg')
    read(KEYRING, root_owned=True)
    # Capture signed bytes into private files; gpgv consumes those copies and
    # does not reopen an operator-selected checksum pathname after validation.
    write('SHA256SUMS', checksums); write('SHA256SUMS.gpg', signature)
    status = run(['gpgv', '--status-fd', '1', '--keyring', str(KEYRING), str(root() / 'SHA256SUMS.gpg'), str(root() / 'SHA256SUMS')])
    valid = [line.split() for line in status.decode().splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
    if not any(SIGNER in line[2:] for line in valid): raise RuntimeError('phase7_vm_official_signature_identity_invalid')
    matches = re.findall(r'^([0-9a-f]{64}) [ *]' + re.escape(IMAGE) + r'$', checksums.decode(), re.M)
    if matches != [IMAGE_SHA256]: raise RuntimeError('phase7_vm_official_image_pin_changed')
    with authenticated_image_snapshot(bundle / IMAGE) as fd:
        info = json.loads(run(['qemu-img', 'info', '--output=json', '/proc/self/fd/' + str(fd)], pass_fds=(fd,)))
        if info.get('format') != 'qcow2' or info.get('backing-filename') or info.get('encrypted') or info.get('virtual-size', 0) > DISK_GIB * 1024**3:
            raise RuntimeError('phase7_vm_official_image_layout_invalid')
        # A standalone conversion, never a backing file pointing at shared data.
        run(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'qcow2', '/proc/self/fd/' + str(fd), str(root() / 'guest.qcow2')], pass_fds=(fd,), timeout=240)
    (root() / 'guest.qcow2').chmod(0o600)
    run(['qemu-img', 'resize', str(root() / 'guest.qcow2'), str(DISK_GIB) + 'G'])


def capture_source(source_sha):
    repository = REPOSITORY
    mode = 'local-known-repository'
    if (repository / '.git').exists():
        origin = run(['git', '-C', str(repository), 'remote', 'get-url', 'origin']).decode().strip()
        if origin not in ('git@github.com:judahsleibi34/Madar.git', 'https://github.com/judahsleibi34/Madar.git', 'https://github.com/judahsleibi34/Madar'):
            raise RuntimeError('phase7_vm_source_repository_invalid')
    else:
        # The staging VM need not possess GitHub credentials or published
        # history. A fixed private pack supplies only the requested commit and
        # its complete tree/blobs. Git's content-addressed commit authenticates
        # the tree; a caller-written JSON SHA label cannot substitute source.
        pack = read(Path.home() / BUNDLE / 'source.pack', 256 * 1024**2)
        repository = root() / 'source.git'
        run(['git', 'init', '--quiet', '--bare', str(repository)])
        run(['git', '-C', str(repository), 'index-pack', '--stdin'], data=pack, timeout=120)
        mode = 'fixed-content-addressed-source-pack'
    if run(['git', '-C', str(repository), 'cat-file', '-t', source_sha]).strip() != b'commit':
        raise RuntimeError('phase7_vm_committed_source_required')
    archive = run(['git', '-C', str(repository), 'archive', '--format=tar', '--prefix=source/', source_sha], timeout=120)
    if len(archive) > 256 * 1024**2: raise RuntimeError('phase7_vm_source_archive_too_large')
    import io
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != 'source' or not (member.isfile() or member.isdir()):
                raise RuntimeError('phase7_vm_source_archive_unsafe')
    write('source.tar', archive)
    write('source-export.json', json.dumps({'source_sha': source_sha, 'mode': mode,
        'archive_sha256': hashlib.sha256(archive).hexdigest(), 'production_authority': False}) + '\n')
    return hashlib.sha256(archive).hexdigest()


def prepare(source_sha):
    if root().exists() or root().is_symlink(): raise RuntimeError('phase7_vm_prepare_attempt_already_consumed')
    if dependencies(): raise RuntimeError('phase7_vm_dependencies_missing')
    headroom(); private_directory(Path.home() / BUNDLE)
    root().mkdir(mode=0o700)
    with lock(root()):
        write('owner.json', json.dumps({'owner': NAME, 'source_sha': source_sha, 'image_sha256': IMAGE_SHA256,
                                       'guest': GUEST, 'port': PORT, 'production_authority': False}) + '\n')
        authenticate_bundle()
        source_digest = capture_source(source_sha)
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', NAME, '-f', str(root() / 'identity')])
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', GUEST, '-f', str(root() / 'guest-host-key')])
        for name in ('identity', 'identity.pub', 'guest-host-key', 'guest-host-key.pub'): (root() / name).chmod(0o600)
        authorized = read(root() / 'identity.pub').decode().strip()
        host_public = read(root() / 'guest-host-key.pub').decode().strip()
        write('known_hosts', f'[127.0.0.1]:{PORT} ' + host_public + '\n')
        marker = {'owner': NAME, 'source_sha': source_sha, 'source_archive_sha256': source_digest, 'production_authority': False}
        cloud = {'hostname': GUEST, 'manage_etc_hosts': True, 'package_update': False, 'package_upgrade': False,
            'ssh_pwauth': False, 'disable_root': True, 'ssh_keys': {'ed25519_private': read(root() / 'guest-host-key').decode(), 'ed25519_public': host_public},
            'users': [{'name': GUEST_USER, 'shell': '/bin/bash', 'lock_passwd': True, 'sudo': ['ALL=(ALL) NOPASSWD:ALL'], 'ssh_authorized_keys': [authorized]}],
            'write_files': [{'path': '/etc/madar-phase7-disposable.json', 'owner': 'root:root', 'permissions': '0600', 'content': json.dumps(marker) + '\n'}]}
        write('user-data', '#cloud-config\n' + json.dumps(cloud) + '\n')
        write('meta-data', json.dumps({'instance-id': NAME, 'local-hostname': GUEST}) + '\n')
        write('network-config', json.dumps({'version': 2, 'ethernets': {'guestnet': {'match': {'macaddress': '52:54:00:07:18:01'}, 'set-name': 'ens3', 'dhcp4': True, 'dhcp6': False}}}) + '\n')
        run(['cloud-localds', '--network-config=' + str(root() / 'network-config'), str(root() / 'seed.iso'), str(root() / 'user-data'), str(root() / 'meta-data')])
        (root() / 'seed.iso').chmod(0o600)
        write('prepared.json', json.dumps({**marker, 'disk_gib': DISK_GIB, 'memory_mib': MEMORY_MIB, 'vcpus': CPUS,
            'disk_sha256_before_first_boot': digest_file(root() / 'guest.qcow2'),
            'seed_sha256': hashlib.sha256(read(root() / 'seed.iso', 16 * 1024**2)).hexdigest()}) + '\n')
        return {'mode': 'PREPARE', 'prepared': True, 'source_sha': source_sha, 'image_sha256': IMAGE_SHA256,
                'vm_started': False, 'production_modified': False}


def qemu_command():
    return ['sudo', '-n', '-u', 'staging-admin', '-g', 'kvm', '--', 'qemu-system-x86_64',
        '-name', NAME, '-machine', 'q35,accel=kvm', '-cpu', 'host', '-smp', str(CPUS), '-m', str(MEMORY_MIB),
        '-nodefaults', '-no-user-config', '-display', 'none', '-monitor', 'none',
        '-serial', 'file:' + str(root() / 'serial.log'), '-pidfile', str(root() / 'qemu.pid'),
        '-sandbox', 'on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny',
        '-drive', 'file=' + str(root() / 'guest.qcow2') + ',if=virtio,format=qcow2,cache=none',
        '-drive', 'file=' + str(root() / 'seed.iso') + ',if=virtio,format=raw,readonly=on',
        '-netdev', f'user,id=phase7,net=192.0.2.0/24,restrict=on,hostfwd=tcp:127.0.0.1:{PORT}-:22',
        '-device', 'virtio-net-pci,netdev=phase7,mac=52:54:00:07:18:01']


def ssh_arguments():
    return ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'GlobalKnownHostsFile=/dev/null',
        '-o', 'UserKnownHostsFile=' + str(root() / 'known_hosts'), '-o', 'ConnectTimeout=3',
        '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none', '-i', str(root() / 'identity'),
        '-p', str(PORT), GUEST_USER + '@127.0.0.1']


def no_existing_guest():
    if os.path.lexists(root() / 'qemu.pid'):
        raise RuntimeError('phase7_vm_existing_pid_requires_independent_inspection')
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal(): continue
        try: arguments = (process / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError, PermissionError): continue
        if arguments and b'qemu-system' in arguments[0] and (
                NAME.encode() in arguments or any(str(root() / 'guest.qcow2').encode() in arg for arg in arguments)):
            raise RuntimeError('phase7_vm_existing_process_requires_independent_inspection')
    with socket.socket() as probe: probe.bind(('127.0.0.1', PORT))


def validate_unstarted_repair(source_sha):
    """One repair only for the observed seccomp/daemonize zero-effect failure."""
    if os.path.lexists(root() / 'repair-attempt.json') or os.path.lexists(root() / 'rehearsal.json'):
        raise RuntimeError('phase7_vm_repair_attempt_already_consumed')
    attempt = json.loads(read(root() / 'boot-attempt.json'))
    if attempt.get('source_sha') != source_sha:
        raise RuntimeError('phase7_vm_original_attempt_invalid')
    if read(root() / 'serial.log') != b'': raise RuntimeError('phase7_vm_repair_guest_may_have_started')
    failures = list(root().glob('failure-*.log'))
    if len(failures) != 1 or read(failures[0]) != b'':
        raise RuntimeError('phase7_vm_repair_requires_known_launch_failure')
    traces = [read(path).decode(errors='replace') for path in root().glob('daemon-nonboot-strace.*')]
    if not any(re.search(r'clone\(child_stack=NULL, flags=CLONE_CHILD_CLEARTID\|CLONE_CHILD_SETTID\|SIGCHLD[^\n]* = -1 EPERM', trace)
               and 'exit_group(1)' in trace and 'SECCOMP_SET_MODE_FILTER' in trace for trace in traces):
        raise RuntimeError('phase7_vm_repair_requires_known_seccomp_daemonize_failure')
    no_existing_guest()
    return hashlib.sha256(read(root() / 'boot-attempt.json')).hexdigest()


def authenticate_repair_driver(driver_sha):
    if not re.fullmatch('[0-9a-f]{40}', driver_sha or ''):
        raise RuntimeError('phase7_vm_committed_repair_driver_required')
    repository = root() / 'repair-driver.git'
    pack = read(Path.home() / BUNDLE / 'source.pack', 256 * 1024**2)
    run(['git', 'init', '--quiet', '--bare', str(repository)])
    run(['git', '-C', str(repository), 'index-pack', '--stdin'], data=pack)
    if run(['git', '-C', str(repository), 'cat-file', '-t', driver_sha]).strip() != b'commit':
        raise RuntimeError('phase7_vm_committed_repair_driver_required')
    relative = 'web/staging/integration/phase7_privileged_vm.py'
    committed = run(['git', '-C', str(repository), 'show', driver_sha + ':' + relative])
    if committed != Path(__file__).read_bytes():
        raise RuntimeError('phase7_vm_repair_driver_source_changed')
    return hashlib.sha256(committed).hexdigest()


def launch_foreground():
    # QEMU10 applies spawn=deny before its own -daemonize fork. Start a new
    # host session before QEMU installs seccomp; retain every sandbox rule.
    fd = os.open(root() / 'qemu-launch.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        process = subprocess.Popen(qemu_command(), stdin=subprocess.DEVNULL, stdout=output, stderr=output,
            start_new_session=True, close_fds=True, env={'PATH': os.defpath, 'HOME': str(Path.home())})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('phase7_vm_foreground_launch_failed_private_diagnostic_retained')
        if (root() / 'qemu.pid').exists():
            (root() / 'qemu.pid').chmod(0o600)
            pid = int(read(root() / 'qemu.pid').decode().strip())
            arguments = Path('/proc', str(pid), 'cmdline').read_bytes().split(b'\0')
            if (b'qemu-system' not in arguments[0] or NAME.encode() not in arguments
                    or not any(str(root() / 'guest.qcow2').encode() in arg for arg in arguments)
                    or Path('/proc', str(pid)).stat().st_uid != os.getuid()):
                raise RuntimeError('phase7_vm_started_pid_identity_invalid')
            return pid
        time.sleep(.1)
    raise RuntimeError('phase7_vm_started_pid_not_observed_requires_independent_inspection')


def rehearse(source_sha, repair_driver_sha=None):
    private_directory(root())
    with lock(root()):
        owner = json.loads(read(root() / 'owner.json')); prepared = json.loads(read(root() / 'prepared.json'))
        if owner.get('owner') != NAME or owner.get('source_sha') != source_sha or prepared.get('owner') != NAME or prepared.get('source_sha') != source_sha or prepared.get('production_authority') is not False:
            raise RuntimeError('phase7_vm_owner_or_source_mismatch')
        if repair_driver_sha is None and (os.path.lexists(root() / 'boot-attempt.json') or os.path.lexists(root() / 'qemu.pid')):
            raise RuntimeError('phase7_vm_boot_attempt_already_consumed')
        repair_preimage = validate_unstarted_repair(source_sha) if repair_driver_sha is not None else None
        if dependencies(): raise RuntimeError('phase7_vm_dependencies_missing')
        headroom()
        no_existing_guest()
        image = json.loads(run(['qemu-img', 'info', '--output=json', str(root() / 'guest.qcow2')]))
        if image.get('format') != 'qcow2' or image.get('backing-filename') or image.get('virtual-size') != DISK_GIB * 1024**3:
            raise RuntimeError('phase7_vm_prepared_disk_identity_invalid')
        if hashlib.sha256(read(root() / 'seed.iso', 16 * 1024**2)).hexdigest() != prepared['seed_sha256']:
            raise RuntimeError('phase7_vm_seed_changed')
        if hashlib.sha256(read(root() / 'source.tar', 256 * 1024**2)).hexdigest() != prepared['source_archive_sha256']:
            raise RuntimeError('phase7_vm_source_archive_changed')
        if digest_file(root() / 'guest.qcow2') != prepared['disk_sha256_before_first_boot']:
            raise RuntimeError('phase7_vm_prepared_disk_changed')
        if repair_driver_sha is not None:
            driver_hash = authenticate_repair_driver(repair_driver_sha)
            write('repair-attempt.json', json.dumps({'source_sha': source_sha, 'repair_driver_sha': repair_driver_sha,
                'repair_driver_sha256': driver_hash, 'original_boot_attempt_sha256': repair_preimage,
                'reason': 'qemu10_spawn_deny_blocks_daemonize_clone', 'started_at': int(time.time())}) + '\n')
        else:
            write('boot-attempt.json', json.dumps({'source_sha': source_sha, 'started_at': int(time.time())}) + '\n')
            write('serial.log', b'')
        guest_pid = launch_foreground()
        started = time.monotonic()
        while time.monotonic() - started < 180:
            result = subprocess.run(ssh_arguments() + ['true'], capture_output=True, timeout=5,
                                    env={'PATH': os.defpath, 'HOME': str(Path.home())})
            if result.returncode == 0: break
            time.sleep(2)
        else: raise RuntimeError('phase7_vm_guest_ssh_not_ready_private_serial_retained')
        run(ssh_arguments() + ['sudo -n cloud-init status --wait'], timeout=180)
        # SCP copies bytes; no host filesystem is mounted into the guest.
        scp = ['scp', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'UserKnownHostsFile=' + str(root() / 'known_hosts'),
            '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none', '-i', str(root() / 'identity'), '-P', str(PORT)]
        run(scp + [str(root() / 'source.tar'), GUEST_USER + '@127.0.0.1:source.tar'])
        script = """import hashlib,io,json,os,pathlib,subprocess,tarfile
p=pathlib.Path('/etc/madar-phase7-disposable.json');m=json.loads(p.read_text())
assert os.getuid()==0 and m['owner']==%r and m['source_sha']==%r and m['production_authority'] is False
assert pathlib.Path('/proc/1/comm').read_text().strip()=='systemd'
b=pathlib.Path('/home/madar-vm/source.tar').read_bytes();assert hashlib.sha256(b).hexdigest()==m['source_archive_sha256']
target=pathlib.Path('/opt/madar-phase7');target.mkdir(mode=0o700)
with tarfile.open(fileobj=io.BytesIO(b)) as t:
 for x in t.getmembers():
  q=pathlib.PurePosixPath(x.name);assert not q.is_absolute() and '..' not in q.parts and q.parts[0]=='source' and (x.isfile() or x.isdir())
 t.extractall(target,filter='data')
pathlib.Path('/var/lib/madar-phase7').mkdir(mode=0o700)
unit=pathlib.Path('/etc/systemd/system/madar-phase7-ownership-proof.service')
unit.write_text('[Unit]\\nDescription=Disposable Madar root/systemd proof\\n[Service]\\nType=oneshot\\nExecStart=/usr/bin/touch /var/lib/madar-phase7/proof.started\\nRemainAfterExit=yes\\nNoNewPrivileges=yes\\n[Install]\\nWantedBy=multi-user.target\\n');unit.chmod(0o644)
for args in (['daemon-reload'],['enable','--now','madar-phase7-ownership-proof.service'],['restart','madar-phase7-ownership-proof.service'],['is-active','--quiet','madar-phase7-ownership-proof.service']):subprocess.run(['systemctl',*args],check=True,capture_output=True)
assert unit.stat().st_uid==0 and pathlib.Path('/var/lib/madar-phase7/proof.started').exists()
print(json.dumps({'guest_root':True,'pid1_systemd':True,'actual_unit_install_start_restart':True,'source_archive_verified':True,'source_sha':m['source_sha']}))
""" % (NAME, source_sha)
        proof = json.loads(run(ssh_arguments() + ['sudo -n python3 -'], data=script.encode(), timeout=120))
        report = {'mode': 'REPAIR' if repair_driver_sha else 'REHEARSE', 'source_sha': source_sha,
            'repair_driver_sha': repair_driver_sha, 'guest_pid': guest_pid, 'official_image_sha256': IMAGE_SHA256,
            'guest_proof': proof, 'memory_mib': MEMORY_MIB, 'vcpus': CPUS, 'standalone_disk_gib': DISK_GIB,
            'ssh_binding': '127.0.0.1:' + str(PORT), 'host_filesystem_mounted': False,
            'outbound_network_restricted': True, 'guest_reboot_tested': False,
            'protected_controller_installed': False, 'production_authority_issued': False, 'production_modified': False,
            'guest_retained_for_parent_coordinated_tests': True,
            'limitations': ['root/systemd bootstrap only; not protected controller acceptance',
                'not host/off-host recovery or production release authorization', 'guest remains owned and resource bounded; parent coordinates shutdown']}
        write('rehearsal.json', json.dumps(report, indent=2) + '\n')
        return report


def main(mode, source_sha, repair_driver_sha=None):
    if (mode not in ('INSPECT', 'PREPARE', 'REHEARSE', 'REPAIR') or not re.fullmatch('[0-9a-f]{40}', source_sha or '')
            or (mode == 'REPAIR' and not re.fullmatch('[0-9a-f]{40}', repair_driver_sha or ''))
            or (mode != 'REPAIR' and repair_driver_sha is not None)):
        raise RuntimeError('phase7_vm_explicit_mode_and_committed_source_required')
    host()
    if mode == 'INSPECT':
        return {'mode': mode, 'fixed_directory': NAME, 'existing_attempt_preserved': root().exists(),
            'missing_dependencies': dependencies(), 'kvm_device_present': Path('/dev/kvm').exists(),
            'memory_mib': MEMORY_MIB, 'vcpus': CPUS, 'disk_gib': DISK_GIB, 'ssh_loopback_port': PORT,
            'official_image_sha256': IMAGE_SHA256, 'source_sha': source_sha,
            'mutations_executed': False, 'production_modified': False}
    return prepare(source_sha) if mode == 'PREPARE' else rehearse(source_sha, repair_driver_sha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=('INSPECT', 'PREPARE', 'REHEARSE', 'REPAIR'), default='INSPECT')
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--repair-driver-sha')
    args = parser.parse_args()
    print(json.dumps(main(args.mode, args.source_sha, args.repair_driver_sha), sort_keys=True))


class AutomaticReleaseGuest:
    """Bounded Node2 test profile using the same official-image/KVM machinery.

    Historical phase7 commands/paths are unchanged. This profile accepts only
    the current owned /opt execution manifest; never a production disk, bridge,
    mount, source-controlled host path or caller-selected QEMU command.
    """
    def __init__(self):
        import uuid
        manifest=Path('/opt/madar-development/inventory/CURRENT-AUTOMATIC-EXECUTION.json')
        value=json.loads(manifest.read_bytes());self.run_id=value['run_id']
        if (socket.gethostname()!='madar-gpu' or os.getuid()!=1000
                or not re.fullmatch(r'codex-[0-9]{8}T[0-9]{6}Z-automatic-execution-[a-f0-9]{8}',self.run_id)
                or value['production_modified'] is not False):
            raise RuntimeError('automatic_guest_owned_node2_manifest_required')
        parent=Path('/opt/madar-development/scratch/codex-runs')/self.run_id
        if value['scratch']!=str(parent) or parent.is_symlink():raise RuntimeError('automatic_guest_scratch_changed')
        private_directory(parent)
        self.directory=parent/'guest';self.directory.mkdir(mode=0o700)
        self.evidence=Path(value['evidence']);private_directory(self.evidence)
        self.uuid=str(uuid.uuid4());self.process=None;self.pid=None
        # Two live application slots plus native providers need the same bounded
        # budget as the accepted historical running-application rehearsal.
        self.memory=8192;self.cpus=4;self.disk_gib=32
        self.mac='52:54:'+':'.join(self.uuid.replace('-','')[i:i+2] for i in (0,2,4,6))
        with socket.socket() as port:port.bind(('127.0.0.1',0));self.port=port.getsockname()[1]
        self.record={'run_id':self.run_id,'guest_uuid':self.uuid,'directory':str(self.directory),
            'memory_mib':self.memory,'cpus':self.cpus,'disk_gib':self.disk_gib,'port':self.port,
            'production_authority':False,'resources_removed':False}
        self.save()

    def save(self):
        path=self.evidence/'automatic-guest.json';path.write_text(json.dumps(self.record,indent=2)+'\n');path.chmod(0o600)

    def command(self,args,*,data=None,timeout=60,pass_fds=()):
        result=subprocess.run(args,input=data,capture_output=True,timeout=timeout,pass_fds=pass_fds,
            env={'PATH':os.defpath,'HOME':'/nonexistent'})
        if result.returncode:
            path=self.evidence/'private-guest-command-error.log';path.write_bytes((result.stdout+result.stderr)[-65536:]);path.chmod(0o600)
            raise RuntimeError('automatic_guest_command_failed_private_evidence')
        return result.stdout

    def write(self,name,body):
        fd=os.open(self.directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:
            out.write(body.encode() if isinstance(body,str) else body);out.flush();os.fsync(out.fileno())

    def prepare(self):
        if shutil.disk_usage(self.directory).free<20*1024**3:
            raise RuntimeError('automatic_guest_disk_headroom_insufficient')
        available=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024
        if available<12*1024**3:raise RuntimeError('automatic_guest_memory_headroom_insufficient')
        bundle=Path('/opt/madar-development/evidence/historical/madar-phase7-official-cloudimage-20261018')
        checksums=read(bundle/'SHA256SUMS');signature=read(bundle/'SHA256SUMS.gpg')
        self.write('SHA256SUMS',checksums);self.write('SHA256SUMS.gpg',signature)
        status=self.command(['/usr/bin/gpgv','--status-fd','1','--keyring',str(KEYRING),str(self.directory/'SHA256SUMS.gpg'),str(self.directory/'SHA256SUMS')])
        if SIGNER not in status.decode() or re.findall(r'^([a-f0-9]{64}) [ *]'+re.escape(IMAGE)+r'$',checksums.decode(),re.M)!=[IMAGE_SHA256]:
            raise RuntimeError('automatic_guest_official_image_signature_refused')
        # Capture/hash one immutable unnamed snapshot before qemu-img reads it.
        with (bundle/IMAGE).open('rb') as source,tempfile.TemporaryFile(dir=self.directory) as frozen:
            sha=hashlib.sha256();size=0
            while block:=source.read(1024**2):
                size+=len(block)
                if size>IMAGE_MAX_BYTES:raise RuntimeError('automatic_guest_image_size_limit')
                frozen.write(block);sha.update(block)
            if not IMAGE_MIN_BYTES<size or sha.hexdigest()!=IMAGE_SHA256:raise RuntimeError('automatic_guest_image_hash_changed')
            frozen.flush();frozen.seek(0)
            info=json.loads(self.command(['/usr/bin/qemu-img','info','--output=json','/proc/self/fd/'+str(frozen.fileno())],pass_fds=(frozen.fileno(),)))
            if info.get('format')!='qcow2' or info.get('backing-filename') or info.get('encrypted'):
                raise RuntimeError('automatic_guest_official_image_layout_refused')
            self.command(['/usr/bin/qemu-img','convert','-f','qcow2','-O','qcow2','/proc/self/fd/'+str(frozen.fileno()),str(self.directory/'guest.qcow2')],pass_fds=(frozen.fileno(),),timeout=120)
        (self.directory/'guest.qcow2').chmod(0o600)
        self.command(['/usr/bin/qemu-img','resize',str(self.directory/'guest.qcow2'),str(self.disk_gib)+'G'])
        for name in ('identity','host-key'):
            self.command(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-C',self.run_id,'-f',str(self.directory/name)])
            for suffix in ('','.pub'):(self.directory/(name+suffix)).chmod(0o600)
        host_public=(self.directory/'host-key.pub').read_text().strip()
        self.write('known_hosts','[127.0.0.1]:'+str(self.port)+' '+host_public+'\n')
        cloud={'hostname':'madar-release-test','manage_etc_hosts':True,'ssh_pwauth':False,'disable_root':True,
            'package_update':False,'package_upgrade':False,
            'ssh_keys':{'ed25519_private':(self.directory/'host-key').read_text(),'ed25519_public':host_public},
            'users':[{'name':'madar','uid':1000,'shell':'/bin/bash','lock_passwd':True,
                'sudo':['ALL=(ALL) NOPASSWD:ALL'],'ssh_authorized_keys':[(self.directory/'identity.pub').read_text().strip()]}],
            'write_files':[{'path':'/etc/madar-disposable-parent.json','permissions':'0600','owner':'root:root',
                'content':json.dumps(self.record)}]}
        self.write('user-data','#cloud-config\n'+json.dumps(cloud)+'\n')
        self.write('meta-data',json.dumps({'instance-id':self.uuid,'local-hostname':'madar-release-test'})+'\n')
        self.write('network-config',json.dumps({'version':2,'ethernets':{'guestnet':{'match':{'macaddress':self.mac},'set-name':'ens3','dhcp4':True,'dhcp6':False}}})+'\n')
        self.command(['/usr/bin/xorriso','-as','mkisofs','-o',str(self.directory/'seed.iso'),'-V','cidata','-J','-r',
            str(self.directory/'user-data'),str(self.directory/'meta-data'),str(self.directory/'network-config')])
        (self.directory/'seed.iso').chmod(0o600)
        self.record['image_sha256']=IMAGE_SHA256;self.save()

    def ssh_args(self):
        return ['/usr/bin/ssh','-F','/dev/null','-o','BatchMode=yes','-o','IdentitiesOnly=yes',
            '-o','StrictHostKeyChecking=yes','-o','GlobalKnownHostsFile=/dev/null',
            '-o','UserKnownHostsFile='+str(self.directory/'known_hosts'),'-o','ConnectTimeout=3',
            '-o','ProxyCommand=none','-o','ProxyJump=none','-i',str(self.directory/'identity'),
            '-p',str(self.port),'madar@127.0.0.1']

    def launch(self):
        args=['/usr/bin/sudo','-n','-u','madar','-g','kvm','--','/usr/bin/qemu-system-x86_64',
            '-name',self.run_id,'-uuid',self.uuid,'-machine','q35,accel=kvm','-cpu','host','-smp',str(self.cpus),'-m',str(self.memory),
            '-nodefaults','-no-user-config','-display','none','-monitor','none',
            '-serial','file:'+str(self.directory/'serial.log'),'-pidfile',str(self.directory/'qemu.pid'),
            '-sandbox','on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny',
            '-drive','file='+str(self.directory/'guest.qcow2')+',if=virtio,format=qcow2,cache=none',
            '-drive','file='+str(self.directory/'seed.iso')+',if=virtio,format=raw,readonly=on',
            '-netdev','user,id=owned,net=10.0.2.0/24,hostfwd=tcp:127.0.0.1:'+str(self.port)+'-:22',
            '-device','virtio-net-pci,netdev=owned,mac='+self.mac]
        with (self.directory/'qemu.log').open('xb') as out:
            self.process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=out,stderr=out,start_new_session=True,
                env={'PATH':os.defpath,'HOME':'/nonexistent'})
        for _ in range(120):
            if self.process.poll() is not None:raise RuntimeError('automatic_guest_qemu_launch_failed')
            path=self.directory/'qemu.pid'
            if path.exists():
                self.pid=int(path.read_text());self.require_owned_pid()
                result=subprocess.run(self.ssh_args()+['true'],capture_output=True,timeout=6)
                if result.returncode==0:
                    facts=json.loads(self.command(self.ssh_args()+['sudo -n python3 -'],data=b'import json,pathlib,socket,subprocess;print(json.dumps({"uuid":pathlib.Path("/sys/class/dmi/id/product_uuid").read_text().strip().lower(),"hostname":socket.gethostname(),"virt":subprocess.check_output(["systemd-detect-virt"]).decode().strip()}))'))
                    if facts!={'uuid':self.uuid,'hostname':'madar-release-test','virt':'kvm'}:
                        raise RuntimeError('automatic_guest_positive_identity_failed')
                    self.record.update(pid=self.pid,identity=facts);self.save();return facts
            time.sleep(1)
        raise RuntimeError('automatic_guest_ssh_deadline_exceeded')

    def require_owned_pid(self):
        p=Path('/proc')/str(self.pid)
        arguments=(p/'cmdline').read_bytes().split(b'\0')
        if (p.stat().st_uid!=1000 or not arguments or b'qemu-system' not in arguments[0]
                or self.run_id.encode() not in arguments or self.uuid.encode() not in arguments
                or not any(str(self.directory/'guest.qcow2').encode() in a for a in arguments)):
            raise RuntimeError('automatic_guest_pid_ownership_refused')

    def close(self):
        if self.pid is not None:
            try:
                self.require_owned_pid();os.kill(self.pid,15)
                for _ in range(100):
                    if not Path('/proc',str(self.pid)).exists():break
                    time.sleep(.1)
                if Path('/proc',str(self.pid)).exists():
                    self.require_owned_pid();os.kill(self.pid,9)
            except FileNotFoundError:pass
        if self.process is not None:
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:raise RuntimeError('automatic_guest_process_not_reaped')
        if self.directory.is_symlink() or self.directory.parent.name!=self.run_id:
            raise RuntimeError('automatic_guest_cleanup_path_changed')
        for name in ('serial.log','qemu.log'):
            p=self.directory/name
            if p.exists():
                target=self.evidence/('private-guest-'+name);target.write_bytes(p.read_bytes()[-65536:]);target.chmod(0o600)
        self.record['resources_removed']=True;self.record['remaining_disk_bytes']=0;self.save()
        shutil.rmtree(self.directory)
