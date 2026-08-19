# Audit evidence and command log

Audit date: 2026-08-18 UTC. Commands below are representative and sanitized; outputs are summarized in the relevant reports. Secret values and customer content are excluded.

## Safety constraints

- Read-only inspection only; no migration, deploy, restart, rebuild, package install, mail send, form submission, reservation, customer write, or load test.
- Production SQL used aggregate/schema/role queries inside read-only transactions and rolled back.
- Mail queue content was not inspected because it could contain addresses.
- Root-only firewall/SSH evidence was attempted read-only and denied; it is not guessed.

## Baseline and Git

```bash
uname -a; cat /etc/os-release; uptime; lscpu; free -h
swapon --show; lsblk -f; df -h; df -i; systemctl --failed
ss -lntup; ps aux; timedatectl
git -C REPO branch --show-current
git -C REPO rev-parse HEAD
git -C REPO remote -v
git -C REPO status --short
git -C REPO log -3 --date=iso-strict --pretty=...
```

Baseline SHAs: Madar/Madar-dev `22e7c94c46ab0fe2df7c23e681495991ecfc1a3d`; Briefedly/Briefedly-dev `7c5adaccac61008a8006b36180ed5fdccf72e62a`; Sleibi `d0f1e535ce3a3d9f68301c6f378fd2386b674e38`; Mailcow `2ac4b1deaee50e1284d644cecc16dcb0b37e67e2`.

## Docker/systemd/network

```bash
docker ps --format ...
docker inspect CONTAINERS                 # selected metadata; secrets redacted/presence only
docker system df -v
docker network inspect ...
docker compose config                    # reviewed locally; values not copied to report
systemctl list-units --type=service
systemctl list-timers --all
systemctl cat UNIT
journalctl -u UNIT --since ...            # summarized/redacted
curl -D - -o /dev/null http://127.0.0.1:PORT/
curl -D - -o /dev/null https://PUBLIC/
```

Root-only attempts that failed: `ufw status verbose`, `nft list ruleset`, `iptables -S`, `ip6tables -S`, and `sshd -T` due unreadable cloud-init include. Readable configs were inspected with `sed`/`stat`.

## DNS/TLS/mail

```bash
dig +short A|AAAA|CNAME|MX|TXT|CAA DOMAIN
curl --max-time 15 -D - -o /dev/null https://DOMAIN/PATH
openssl s_client -connect mail.madarportal.com:PORT -servername mail.madarportal.com
docker exec postfix postconf -h smtpd_relay_restrictions
docker exec postfix postconf -h smtp_tls_security_level
docker exec dovecot doveconf -h ssl_min_protocol
timeout 10 bash -c 'exec 3<>/dev/tcp/gmail-smtp-in.l.google.com/25'
```

The outbound TCP/25 connection timed out; no SMTP command/message was sent. Public mail certificates were valid through 2026-10-08 at inspection.

## Database evidence

Production queries were executed inside container Python processes so credentials were not placed in command arguments. Each connection executed `SET TRANSACTION READ ONLY`; only counts, versions, role flags, table/column names, migration revisions, lock/size metadata, and grants/policies were returned; transactions were rolled back.

Examples:

```sql
SELECT current_user, version();
SELECT table_name FROM information_schema.tables WHERE table_schema='public';
SELECT grantee, privilege_type FROM information_schema.role_table_grants ...;
SELECT policyname, roles, cmd FROM pg_policies ...;
SELECT status, count(*) FROM queue_table GROUP BY status;
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles ...;
SELECT version_num FROM alembic_version;
```

No row content, email, form response, report, token, or personal identity was returned.

## Static review/searches

```bash
rg --files REPO
rg -n 'TODO|FIXME|HACK|XXX' ...
rg -n 'eval\(|exec\(|pickle|yaml.load|shell=True|os.system|subprocess' ...
rg -n 'dangerouslySetInnerHTML|innerHTML|localStorage|sessionStorage' ...
rg -n 'tenant_id|workspace_id|project_id|\.get\(|\.first\(|limit\(1' ...
rg -n 'CORS|CSRF|SameSite|secure=|httponly' ...
rg -n 'requests\.|httpx\.|urllib|redirect|webhook' ...
rg -n 'upload|filename|Path\(|open\(' ...
rg -n 'retention|delete|export|cleanup' ...
```

Findings were traced into surrounding route/service/model/migration/Compose code; raw search hits were not treated as vulnerabilities by themselves.

## Tests and audits

| Test | Result |
|---|---|
| Sleibi `scripts/validate.sh` | pass; HTML tidy/image-Nginx checks skipped because tool/image unavailable |
| Briefedly frontend `npm test` | 5/5 pass |
| Madar focused renderer test | 4 pass, 2 fail |
| Madar full Vitest | began and reproduced failures; did not terminate/emit complete summary in audit window |
| `npm audit --omit=dev` Madar | 0 production advisories |
| `npm audit --omit=dev` Briefedly | 0 production advisories |
| Madar backup verify, 2026-07-31 set | pass |
| Backend suites | skipped: host lacks pytest; production containers/config could contact production and were not safe test targets |
| PostgreSQL integration suites | skipped: designed to create/drop schema; no isolated disposable DB provisioned |
| Browser E2E/load tests | skipped: risk, missing isolation, and task prohibition on load/customer mutation |

## Evidence limitations

No access to Cloudflare account settings/WAF/cache rules/tailnet ACLs/router/NAT/ISP control plane, Supabase dashboard/auth settings, Google Cloud console/token revocation, off-host backup provider, or root-only host policy. Public behavior and local configuration were used where safe. Findings requiring those views are labeled accordingly.
