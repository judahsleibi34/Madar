# Mailcow production-readiness lane

Status: **REQUIRES MAINTENANCE** and backup hardware. Mailcow was inspected read-only and not modified.

Evidence date: 2026-08-19. Installed repository identity is `2ac4b1d` with tag `2026-05c-dirty`. Pre-existing local modifications include certificate examples and Dovecot/Postfix configuration plus two untracked pre-change configuration files. These must be preserved, explained and included in encrypted recovery material; never reset or update over them blindly.

## Backup and restore

Use Mailcow's supported helper for coherent MariaDB, vmail, crypt, Rspamd and configuration coverage, or its documented cold-standby procedure. The official cold-standby procedure uses `mariabackup` plus `rsync --delete`, is not itself versioned, and leaves the source unchanged; therefore target a staging generation and publish an immutable/versioned encrypted backup only after both steps and checks pass. Do not aim a destructive sync at the only good generation.

Restore drill: provision an empty matching-version host or isolated VM; install the same Mailcow code/config identity; restore the supported components; verify MariaDB integrity, mailbox counts/metadata (not content in reports), DKIM/crypt material, account authentication, queues and service health; then test controlled internal delivery without affecting public DNS. A cold standby is availability capacity, not a backup. Official references retrieved 2026-08-19:

- <https://docs.mailcow.email/backup_restore/b_n_r-backup-export/>
- <https://docs.mailcow.email/backup_restore/b_n_r-restore/>
- <https://docs.mailcow.email/backup_restore/b_n_r-coldstandby/>
- <https://docs.mailcow.email/getstarted/prerequisite-system/>

## Required inventory

Record container image digests, Compose/config hashes excluding secret values, MariaDB version/schema, vmail size/count, crypt/DKIM/TLS artifact presence and permissions, custom Rspamd/Postfix/Dovecot changes, certificate issuer/expiry/renewal, Redis role in restoration, queue counts/oldest age, disk/inodes and last successful backup. Encrypt secret recovery separately and escrow its key off-host.

## Port and perimeter decision

Do not close ports until client evidence is complete. Review current public exposure independently on IPv4 and IPv6:

- 25 is required for public SMTP receipt and depends on correct NAT/PTR/ISP egress;
- 465/587 are submission alternatives according to client policy;
- 993 is IMAPS; 995 is POP3S if used;
- 110 and 143 are cleartext/STARTTLS legacy endpoints and should be disabled unless a documented client requires them and TLS enforcement is proven;
- 8080 and 8443 are direct Mailcow web ports in current configuration and should not remain Internet-accessible unless they serve a deliberate, authenticated, TLS-correct purpose;
- 80/443 and Sieve/ManageSieve exposure follow approved webmail/client requirements.

Reconcile listener, Docker publication, host firewall, router NAT and an external dual-stack scan. Separate server configuration from ISP/router limitations; the historical outbound TCP/25 block is not an application defect.

## Mail readiness gates

1. supported current version and local modifications documented;
2. two encrypted versioned recovery copies, one offline/offsite;
3. isolated restore proven;
4. SPF, DKIM, DMARC, MX, PTR, TLS and CAA assessed with public evidence;
5. relay restrictions and brute-force controls tested safely;
6. certificate renewal and queue/disk/service alerts active;
7. required-port owner matrix approved and surplus ports closed in a lockout-safe maintenance window;
8. recovery/RPO/RTO drill measured.

Rollback for configuration/perimeter work is the captured exact prior rules/config plus console access; rollback for an update is version-compatible documented restore, not a Git reset over dirty production state.
