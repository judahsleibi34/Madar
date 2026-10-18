# Disposable privileged controller test guest

`web/staging/integration/phase7_privileged_vm.py` is an explicitly staging-only
bootstrap. It cannot issue production authority or install the host controller.
Its single directory is `$HOME/madar-phase7-privileged-20261018`; preparation and
boot attempts are consumed and never overwritten. It does not use LXD/libvirt,
host filesystem shares, production credentials, existing application volumes,
host systemd changes, host reboot, or alternate production deployment paths.

Read-only discovery on the dedicated staging VM found KVM available, four vCPUs,
5,402 MiB memory and approximately 20 GiB free disk. Initial missing dependencies
were `qemu-system-x86_64`, `qemu-img`, and `cloud-localds`. Parent coordination is
required for `sudo -n apt-get install --no-install-recommends qemu-system-x86
qemu-utils cloud-image-utils`; no virtualization service needs enabling. The
parent subsequently reported installation complete. The script author did not
install packages, launch a VM, restart services, or reboot a host.

The staging user is not in `kvm`, but the read-only test
`sudo -n -u staging-admin -g kvm -- test -w /dev/kvm` passed. QEMU uses that exact
unprivileged UID/group combination instead of running as host root. Guest size
is initially one vCPU, 1,024 MiB RAM and a standalone sparse 8 GiB QCOW2 disk.
Preparation/boot require at least 12 GiB host free space and 2,300 MiB available
memory. Increasing resources or pausing application workloads needs separate
parent coordination; this bootstrap does neither.

## Official image authentication

The parent provisions a private0700 bundle directory
`$HOME/madar-phase7-official-cloudimage-20261018`, with current-user-owned0600
files downloaded from these fixed official URLs:

- https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
- https://cloud-images.ubuntu.com/noble/current/SHA256SUMS
- https://cloud-images.ubuntu.com/noble/current/SHA256SUMS.gpg

The official index identified Ubuntu24.04LTS/Noble daily20261017. The pinned
image SHA256 is
`04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94`.
The mutable `current` URL is a download location, never the identity: a rotated
manifest or different image fails the exact pin. The tool verifies captured
manifest/signature bytes with `gpgv` and the root-owned installed
`/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg`, requiring primary fingerprint
`D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`. It hashes the image on an open regular
file descriptor while copying to an unnamed private snapshot, then supplies the
authenticated snapshot descriptor to `qemu-img`. Renaming or modifying the
original bundle inode after hashing cannot substitute conversion bytes. Arbitrary
URLs, image paths, keys and signing identities are not accepted.

See the [official manifest](https://cloud-images.ubuntu.com/noble/current/SHA256SUMS),
[official image index](https://cloud-images.ubuntu.com/noble/current/) and
[Ubuntu image verification guidance](https://documentation.ubuntu.com/security/software-integrity/image-verification/).
Direct staging DNS for this host was unavailable during discovery, so the parent
downloads/authenticates on the development host and copies this synthetic bundle.
No credentials or production data belong in that directory.

If staging runs an exported source tree without `.git`, the same private bundle
also needs `source.pack`. The parent creates this on the development checkout
for the exact reviewed commit and copies it with0600 permissions. For example:

```python
import subprocess
source_sha = '<exact40hexcommit>'
objects = subprocess.check_output([
    'git', 'rev-list', '--objects', '--no-object-names', source_sha + '^{tree}'])
with open('/private/phase7-bundle/source.pack', 'xb') as output:
    subprocess.run(['git', 'pack-objects', '--stdout'],
        input=source_sha.encode() + b'\n' + objects, stdout=output, check=True)
```

This pack contains one commit object and its complete source tree/blobs, not Git
history or host configuration. The VM bootstrap indexes it into a new private bare
repository and asks Git to archive the exact requested commit. Missing/different
commit objects fail; merely changing a JSON source label cannot change Git's
content-addressed tree. It supplies no CI acceptance or operational authority.

## Coordinated execution

From an exact source checkout on staging, using an explicit committed SHA:

```bash
python3 web/staging/integration/phase7_privileged_vm.py INSPECT --source-sha <sha>
python3 web/staging/integration/phase7_privileged_vm.py PREPARE --source-sha <sha>
python3 web/staging/integration/phase7_privileged_vm.py REHEARSE --source-sha <sha>
```

INSPECT has no effects. PREPARE verifies the official image and produces an
independent converted disk without a backing file, generated private SSH keys,
preseeded guest host key, cloud-init ISO and an archive of the exact requested Git
commit. Dirty checkout files are never substituted for that committed archive.
Private receipt hashes protect source, seed and initial guest disk before boot.

REHEARSE first verifies ownership, consumed-attempt state, dependencies, available
loopback port, disk layout and all prepared hashes. QEMU user networking restricts
outbound access and exposes only `127.0.0.1:23222` to guest SSH. No TAP bridge,
host network service, QMP, VNC, SPICE, host block device, virtiofs or 9p mount is
configured. SSH ignores ambient configuration/agents/proxies and requires the
preseeded host key. The source archive travels by SCP, is verified again inside
the guest, and is safely extracted under `/opt/madar-phase7/source`.

The fixed guest probe requires actual root through passwordless guest sudo,
PID1 systemd, completed cloud-init and the correct private disposable marker.
It installs/enables/starts/restarts only the harmless guest
`madar-phase7-ownership-proof.service`, checking root ownership and its own marker
file. This proves a real root/systemd bootstrap boundary; it does not claim the
Madar protected controller, approval, write issuer, boot/reboot or release handoff
has passed. No full application stack is installed in the initial1 GiB guest.

The VM remains resource-bounded for parent-coordinated privileged tests. A failed
boot/probe retains private serial/output diagnostics and cannot silently relaunch.
The parent must verify ownership/source/known-host key before connecting, and
coordinate guest-only shutdown with `sudo -n systemctl poweroff` over that pinned
SSH channel. Do not kill an unverified PID or remove unidentified disks.

## Evidence scope

The new refusal tests run without QEMU, package installation or service effects.
Actual guest provisioning/systemd proof remains NOT TESTED until the parent runs
the explicit commands and obtains `rehearsal.json`. Guest root is not production
authority. Host-root isolation is the normal KVM/QEMU boundary, not a certification
against hypervisor vulnerabilities. The existing source150 application stays
active and the retained recovery target stays stopped throughout this bootstrap.
