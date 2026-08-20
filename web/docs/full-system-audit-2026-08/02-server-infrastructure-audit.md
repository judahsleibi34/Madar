# Server infrastructure audit

## Capacity and kernel

The host has adequate current disk and memory headroom but little redundancy: a single root filesystem contains source, Docker, local databases, uploads, mail, configuration, and backups. Swap was in use (~233 MiB) after only a few hours uptime, which is not itself a fault but warrants trending. No current OOM event or failed unit was observed. Timezone is UTC and time synchronization appeared active.

Kernel exposure reports include CPU speculative-execution caveats, including an MDS/MMIO stale-data SMT exposure and missing microcode mitigation for one class. Treat this as defense-in-depth: confirm BIOS/microcode packages and whether SMT is acceptable for the threat model. ASLR is enabled (`randomize_va_space=2`), ptrace is restricted (`yama/ptrace_scope=1`), and protected link/FIFO controls are enabled.

`/tmp` is isolated on tmpfs with `nosuid,nodev`; adding `noexec` is optional defense-in-depth and requires compatibility testing. Root is mounted `rw,relatime`; no separate filesystem/quotas isolate Docker, databases, mail, logs, uploads, or backups from each other.

## Users and privilege

Only `root` and `madar` have normal interactive shells. `madar` belongs to `sudo`, `docker`, and `adm`. Docker membership is root-equivalent; the account also owns source, production secrets, deploy scripts, and backups. This collapses developer, operator, deployment, log-reader, secret-reader, and host-root trust boundaries.

`/home/madar` is mode 750, limiting traversal by unrelated local accounts. No world-writable object was found beneath it. Production `.env` files are mode 600. Some old dumps and a development `.env` backup are mode 664, but the 750 home directory limits exposure to the `madar` group/root. Their modes should still be normalized because copies may later move to broader paths.

SSH key-directory permissions are reasonable: `.ssh` 700, authorized/private keys 600, public keys 644. No host-level `auditd` or conventional fail2ban service was found; Mailcow has its own netfilter component.

## Packages and boot health

No reboot-required marker was present. A small number of packages were listed as upgradeable, but no urgent security update was conclusively identified from the non-root view. No automated evidence was found for unattended security-update alerting, firmware checks, SMART monitoring, filesystem scrubs, or reboot orchestration.

## Filesystem and growth risks

- Docker build cache is 79.29 GiB, 63.28 GiB reclaimable.
- Journald is about 575 MiB.
- Several services rely on Docker's default JSON logging without project-specific rotation.
- Mail, Postgres WAL, uploads, temporary parses, failed jobs, and backups share the root filesystem.
- No disk quota or separate volume prevents one subsystem from exhausting the host.

The immediate disk state is healthy, but a single Docker build/cache or mail/WAL growth incident can cause simultaneous database, application, and mail failure.

## Limitations

Effective SMART data, full kernel/boot error history, root-only permissions, sudoers content, full setuid inventory, active firewall rules, and effective SSH settings could not be read without interactive root authentication. These are explicitly marked for operator verification rather than assumed safe.
