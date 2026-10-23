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
parent subsequently completed installation. The script author did not install
packages, change retained services, or reboot a host. Parent-authorized native
PREPARE later passed; the first launch exposed the QEMU daemonization defect
described below before any guest disk write or running guest.

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

## Narrow unstarted-launch repair

The first native launch used source
`1b1dc54d8f19a2b1c83c618da89a42d8758b6993`. Ubuntu's QEMU 10.2.1 applies its
`spawn=deny` seccomp filter before its own `-daemonize` fork. An isolated,
diskless/networkless paused diagnostic reproduced the failed `clone(...)=EPERM`
and exit1. The equivalent foreground nonboot diagnostic retained the same
sandbox and ran until its three-second timeout. There was no QEMU process, PID
file, listener or serial output after the failed real launch; disk, seed and
archive hashes remained equal to their prepared values.

The correction retains all four QEMU sandbox restrictions and launches QEMU in
the foreground from a new host session established before seccomp. QEMU remains
the unprivileged staging owner with group `kvm`. The recorded live PID comes from
QEMU's own pidfile and is checked against UID, fixed guest name and disk path;
the intermediate sudo launcher PID is not treated as guest identity.

`REHEARSE` still rejects a consumed attempt. A separate, explicit `REPAIR` accepts
only this diagnosed, unstarted failure, once. It requires the original boot
receipt and empty serial/launch-error evidence, the retained matching seccomp
diagnostic, no PID file (including broken symlinks), no matching live QEMU process,
an unused loopback port, and all three unchanged initial hashes. It authenticates
the repair driver's exact tool blob from a separately supplied fixed private
`source.pack`, records a new repair receipt, and preserves the original attempt.

```bash
python3 web/staging/integration/phase7_privileged_vm.py REPAIR \
  --source-sha 1b1dc54d8f19a2b1c83c618da89a42d8758b6993 \
  --repair-driver-sha <exact-reviewed-repair-commit>
```

The original guest marker/archive retain source1b1dc54d; the repair-driver commit
is separately reported. Neither is relabelled as the other. Unknown failures,
changed guest bytes, an existing process or any prior repair require independent
inspection rather than automatic retry. Native repair subsequently passed using
committed driver `7ec7a2bb512d881002e2f5d42cd5f5fe69800893`; original guest source
remains `1b1dc54d8f19a2b1c83c618da89a42d8758b6993`.

## Evidence scope

The new refusal tests run without QEMU, package installation or service effects.
Actual guest root/systemd proof passed and produced `rehearsal.json`. Guest root is not production
authority. Host-root isolation is the normal KVM/QEMU boundary, not a certification
against hypervisor vulnerabilities. The existing source150 application stays
active and the retained recovery target stays stopped throughout this bootstrap.

## Native acceptance obtained

The parent authorized provisioning and subsequent operations only within this
positively identified disposable guest. Private evidence is retained outside Git
under the staging owner's `phase7-vm-native-20261018/` and fixed VM directory.
Raw boot IDs, generated keys, cloud-init configuration and full diagnostics are
not included here.

| Boundary | Result | Actual evidence and limit |
| --- | --- | --- |
| Official image and independent disk | PASS | Signed manifest, exact image pin, authenticated snapshot and standalone 8 GiB conversion. |
| Original boot failure containment | PASS | Consumed attempt preserved; no guest writes; initial disk/seed/archive hashes unchanged. |
| Explicit repair | PASS | Driver 7ec authenticated from its committed Git blob; guest archive/marker retain 1b; no sandbox restriction removed. |
| Real root/systemd | PASS | Actual root sudo, PID 1 systemd, cloud-init, source extraction and harmless unit install/start/restart. |
| Exact controller installer | PASS | Actual unchanged 1b installer dry-run and apply at canonical guest paths; synthetic fixtures only. |
| Atomic controller replacement | PASS | Second apply used a new private backup and native RENAME_EXCHANGE. 175 installed source files matched exact 1b bytes/ownership. |
| Effective actual units | PASS | Fourteen actual Madar unit files match source; auto-deploy executes canonical immutable path as madar with NoNewPrivileges=yes. All six timers remain disabled/inactive; proxy and auto-deploy remain inactive. |
| Supported privilege refusal | PASS | Installed isolated upgrader rejects nonroot; isolated release entry rejects wrong root identity; installed authorization module rejects missing recovery approval. |
| Full recovery CLI authorization probe | BLOCKED | It stopped earlier at the intentionally root0600 synthetic environment fixture. Module-level refusal does not substitute for that full path. |
| Persistent test barrier | PASS | Actual systemctl and busctl start calls returned 0 while execution stayed blocked: ActiveState=inactive, ConditionResult=false, Job=(0,"/"). Success exit status alone does not prove activation. |
| Guest-only reboot | PASS | New private guest boot ID, same staging host boot ID, same QEMU process/disk/command and pinned SSH host key. Persistent barrier/drop-in hashes and execution marker unchanged. |
| Installed state after reboot | PASS | 175 source files still matched and no bytecode. Actual Madar timers remained disabled/inactive. |
| New PhaseVII installer source | PASS | Exact bd0c614c source reconstructed separately; actual dry-run/apply and atomic exchange verified 182 root-owned source files, all six schema150 helpers imported from installed paths, and unselected 150 metadata. |
| Graceful guest poweroff | PASS | Pinned guest-only systemctl poweroff; actual QEMU process exited and loopback 23222 closed. Disk, seed, private backups and consumed receipts retained. |
| Full provider/controller handoff | NOT TESTED | No Docker/provider stack, accepted release artifacts, approved admission, database migration or write-authority handoff in this guest. |

The initial unsupported raw-root Python release-entry refusal generated one
root-owned package bytecode file before rejecting the identity. This was
preserved with its hash in private evidence and the second install's backup,
rather than hidden. The supported installed upgrader uses `python3 -I -B`;
subsequent direct diagnostic module probes also used `-I -B`. The authoritative
tree was verified bytecode-free after replacement, probes and reboot.

After the 1b reboot rehearsal, the parent supplied exact committed candidate
`bd0c614cfb92417740ce8d8bffacb98f6636e48a`. Its clean source was reconstructed
under a separate `/opt/madar-phase7/controller-bd0c614c` root. The original1b
bootstrap source/archive/marker stayed intact. The actual unchanged new installer
passed dry-run and apply using another private backup. All 182 installed source
files and fourteen actual unit files matched this newer commit with root
ownership, and the six schema150 helpers imported successfully from installed
paths. The 150 release metadata remained unselected.

Four isolated native refusals passed for that newer installation: nonroot
supported upgrader, wrong release identity, missing recovery authorization in
the installed module, and a concrete provider adapter call without an owned
coordinator lock. No fake approval, lock, migration receipt or authority was
created. The harmless test barrier stayed armed; no provider, worker, proxy or
auto-deploy operation was started. This is installed-helper/refusal evidence,
not a full approved provider-maintenance or release-handoff rehearsal.

The harmless persistent barrier is a dedicated negative `ConditionPathExists`
drop-in for `madar-phase7-ownership-proof.service`, backed by a test-only file
under `/var/lib/madar-phase7`. It is not an operational approval, deployment
receipt or provider-maintenance record. Its persistence validates native systemd
semantics and the guest reboot boundary; it does not prove protected provider
maintenance integration or completed-NORMAL release acceptance.

Private evidence files include `controller-installation-evidence.json`,
`barrier-pre-reboot.json`, `barrier-post-reboot.json` and the exact private
preparation/verification procedures. Newer-source evidence is in
`controller-bd0c614c-installation-evidence.json`. After the parent-authorized
guest-only graceful poweroff, `guest-poweroff-evidence.json` confirmed actual
QEMU exit, closed loopback SSH, retained disk/seed/receipts and unchanged staging
host boot. Host available memory was 2,868 MiB and free disk 17,345,482,752 bytes
(about 16.15 GiB) at that observation; no forced kill or disk/container cleanup ran.
The original source150 eleven-service stack
remained active and the retained recovery project remained stopped. No shared
host service, production controller or production workload was changed.
