# Node B commissioning runbook

Status: `BLOCKED BY HARDWARE`. Execute from local console with a second operator/fallback path. Record output in a dated commissioning evidence package; never paste secrets.

## 1. Hardware identity and firmware

Record exact models and versions:

```bash
sudo dmidecode -t system -t baseboard -t bios -t memory
lscpu
sudo lshw -class network -class disk -class display
lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS
sudo nvme list
sudo nvme smart-log /dev/nvme0
sudo smartctl -x /dev/DEVICE
```

- Photograph/record chassis and drive serial for custody, not in a public repository.
- Update BIOS/UEFI and SSD firmware only from vendor-verified packages with rollback/recovery instructions.
- Record TPM and Secure Boot state. Prefer Secure Boot enabled if the chosen NVIDIA driver path works; do not silently disable it.
- Confirm exact RTX 4060 model and VRAM using `nvidia-smi --query-gpu=name,memory.total,driver_version,vbios_version --format=csv` after driver installation.
- Record negotiated NIC speed/duplex with `ethtool INTERFACE`; do not assume 1 or 2.5 GbE.

## 2. Burn-in and power testing

Before any production secret is installed:

- Run a complete memory test from boot media, at least one full pass and preferably overnight.
- Run vendor SMART/NVMe self-tests and record media/error counters.
- Run CPU and GPU sustained tests for an approved duration while recording temperatures, clocks, throttling, errors, and wall power. Stop at vendor-safe thermal limits.
- Run concurrent disk I/O and model inference only on disposable data.
- Perform at least three cold boots, three warm reboots, network-link interruption, and controlled AC-loss/UPS recovery tests.
- Verify BIOS `Restore on AC Power Loss` matches the approved policy and does not start services before storage/network are healthy.

Pass: no memory/GPU/kernel errors, no thermal throttling affecting SLO, no disk errors, and predictable reboot/recovery. Exact tools and thresholds are chosen after model/firmware discovery.

## 3. OS selection and clean installation

Recommended baseline: **Ubuntu Server 24.04 LTS amd64**, minimal installation, encrypted system volume where unattended-boot requirements allow. It is explicitly supported by current Docker Engine and NVIDIA Container Toolkit documentation; Tailscale supports Ubuntu-based distributions; Ollama lists RTX 4060 support. Ubuntu 26.04 is also listed by Docker/NVIDIA as of retrieval, but 24.04 has the more mature operational history. Re-evaluate at commissioning date.

Official compatibility references retrieved 2026-08-19:

- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [NVIDIA Container Toolkit supported platforms](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/supported-platforms.html)
- [NVIDIA Container Toolkit installation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [Tailscale Linux installation](https://tailscale.com/docs/install/linux)
- [Ollama GPU support](https://docs.ollama.com/gpu)

Do not clone Node A. Verify ISO signature, install clean, enable time synchronization, apply security updates, install CPU microcode, and record package/kernel versions. Disable unattended feature upgrades; keep security-update visibility and a tested reboot policy.

## 4. Identities and filesystem ownership

Create separately:

- named human operator: keys/MFA-backed sudo for approved commands, not Docker group;
- `deploy-madar` and `deploy-briefedly`: no interactive password, constrained deployment service/API;
- per-application runtime UIDs: no shell, no shared source ownership;
- `backup-writer`: read only approved snapshot paths and write encrypted generations, no prune authority;
- `monitor-agent`: read only required metrics/status;
- root break-glass: offline credential, dual-custody procedure.

Prefer rootless Docker for stateless application/staging workloads if GPU, networking, storage, and operational tests pass. GPU rootless support is documented by NVIDIA but requires host configuration. Otherwise use rootful Docker behind a root-owned deployment service; humans still do not receive socket access.

## 5. SSH staged rollout

1. Install two independently held operator keys and verify fingerprints locally.
2. Keep physical console active.
3. Validate candidate with `sshd -t -f CANDIDATE` and `sshd -T -f CANDIDATE`.
4. Target: `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitEmptyPasswords no`, `X11Forwarding no`, `AllowAgentForwarding no`, `AllowTcpForwarding no` unless a named requirement exists, `MaxAuthTries 3`, explicit `AllowGroups ssh-operators`, and bounded keepalive/idle policy.
5. Reload, do not restart, and prove a second new session before closing the first.
6. Test failure and console rollback. Capture effective config.

## 6. Host firewall and network

- Default deny unsolicited IPv4 and IPv6 ingress.
- Permit management SSH only from approved operator sources/Tailscale policy.
- Permit application origin ports only from the local tunnel/proxy path; do not publish them globally.
- Permit Ollama gateway only from Node A/Node B application identities as designed; raw 11434 remains loopback.
- Add explicit Docker `DOCKER-USER` policy and test container publishing on both protocol families.
- Validate from a separate LAN host, a Tailscale peer, and an external dual-stack host.

## 7. Tailscale

Use machine tags owned by an infrastructure-admin group: `tag:node-a-mail`, `tag:node-b-app`, `tag:ollama-gateway`, `tag:monitoring`, `tag:backup-source`. Use current grants syntax and policy tests. No `*:*` grants.

Minimum flows: operator group to SSH; Node B app to its gateway port; monitoring identity to exporter ports; backup identity to the explicit transfer endpoint; no mail-to-app administration. Enable device approval; evaluate tailnet lock and keep signing keys off both nodes.

## 8. Container and GPU baseline

- Pin image digest and record SBOM/provenance.
- Non-root process, read-only root, `cap_drop: ALL`, no-new-privileges, bounded tmpfs/writes, PID/CPU/memory limits, healthchecks, and bounded logs.
- Internal networks by trust domain; no default inter-project reachability; no Docker socket.
- Install the distribution-packaged NVIDIA driver and toolkit only after recording versions. Validate `nvidia-smi`, a pinned disposable GPU container, suspend/reboot behavior, and device access limited to Ollama.
- Ollama binds loopback/internal only. Gateway validates a trusted certificate and bearer token, strips/avoids request logging, caps body/time/concurrency, and returns separate gateway/model health.
- Inventory model name, immutable digest/checksum, context size, quantization, disk/VRAM footprint, and license.

## 9. Acceptance gate

Node B remains non-production until hardware evidence, burn-in, patch baseline, SSH/firewall dual-stack tests, Tailscale policy tests, root-boundary tests, encrypted backup/restore drill, monitoring alerts, Ollama security tests, and production-shaped capacity tests all pass. Record deviations in the master register.
