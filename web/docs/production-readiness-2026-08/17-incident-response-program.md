# Incident-response program

Status: **READY** for owner assignment/tabletop; provider and production procedures require later authority.

## Common process

Declare an incident lead and scribe; preserve time, host/provider/container/image/schema identities and relevant redacted logs; minimize customer-content access; contain with the least destructive reversible step; rotate only after dependencies and recovery are known; verify old credentials/tokens are dead; restore from verified clean recovery points; validate tenant boundaries and data integrity; make notification decisions with counsel/provider obligations; and hold a root-cause review with tracked actions. Never paste secrets or private content into chat/tickets.

## Scenario runbooks

| Incident | Detection | Immediate containment/evidence | Recovery and verification |
|---|---|---|---|
| DB/service-role/OAuth secret leak | scanner, provider alert, auth anomaly | stop distribution path; identify credential class/consumers/log exposure; preserve provider audit metadata | staged replacement, least privilege, update consumers, revoke old, prove old fails and new boundary works |
| Gmail refresh-token theft | Google alert or anomalous API use | disable connection/job admission; capture connection/user/workspace metadata; revoke at Google | reconnect through verified flow, inspect affected import scope, lifecycle and Google notification duties |
| tenant isolation incident | customer report, audit/query anomaly | block affected route/feature, preserve request/cache/DB identifiers, avoid broad deletion | patch/test full sibling-object matrix, invalidate caches/tokens as needed, scope exposure and decide notice |
| global admin compromise | unusual AAL2/admin action | revoke sessions/access cookies; disable admin path/account through break-glass procedure | recover deterministic second admin, rotate relevant keys, audit every privileged action and tenant scope |
| host/Docker socket compromise | EDR/log/config/image drift | isolate host from network while preserving console/evidence; assume every container/secret on node exposed | rebuild clean host from code/digests, restore verified data, rotate node-held credentials, forensic/provider review |
| ransomware | file/encryption anomaly, services failing | isolate nodes/storage; disconnect offline copies; do not power-cycle before evidence decision | rebuild, restore last known-good generation, measure loss, rotate secrets, validate malware-free recovery |
| backup corruption | checksum/restore failure | stop pruning and quarantine bad generation; protect previous copies | restore previous good, identify source/tool fault, produce and drill a new generation before resuming prune |
| deletion/data loss | count/storage/tenant report | stop deletion workers and writes narrowly; preserve jobs/audit/cache metadata | point-in-time/logical restore to isolation, scoped forward recovery, suppression markers and tenant validation |
| Cloudflare credential compromise | provider audit/config drift | revoke token/tunnel credential with provider authority; preserve config/audit | reprovision least-privilege tunnel, validate ingress/origin allowlist, DNS/TLS and direct-origin exposure |
| Tailscale compromise | device/grant anomaly | expire/remove affected identity/device/tag; isolate routes without losing console | rotate auth keys, review grants/device approval/tailnet lock, validate all node/service paths |
| Ollama gateway compromise | cert/auth/log/model anomaly | stop AI job admission, isolate gateway/device, preserve model/gateway identity | rebuild gateway/model from approved checksums, rotate bearer/Tailscale identity, red-team prompt/log boundary |
| Mailcow compromise | queue/auth/config/file anomaly | restrict affected interface, preserve queues/logs/config/image/MariaDB metadata | rebuild matching supported version, restore coherent backup, rotate accounts/DKIM/TLS as scoped, mail-flow verification |
| malicious upload/parser | scanner/parser anomaly or resource spike | quarantine object, stop affected worker pool, preserve hash/metadata not content in report | rebuild sandbox worker, revoke any exposed secrets, scan related objects, prove no-network/minimal-secret boundary |

## Required provider/counsel decisions

Maintain current incident contacts and security-reporting paths for Google, Supabase, Cloudflare, Tailscale, mail/DNS and backup provider. Google's Workspace user-data policy requires incident procedures and notification/reporting for unauthorized restricted-data access; consult the current policy and assessment contract at incident time. Counsel decides statutory/contractual customer/regulator notices, evidence preservation and legal holds.

## Readiness exercise

Quarterly tabletop one scenario; semiannual credential and tenant-isolation exercise; annual clean-host recovery plus mail/application restore; after every material architecture change re-run affected scenario. Record detection time, containment time, recovery time, data-loss window, failed dependencies and actions. A runbook is not closed until named on-call and decision owners can execute it without undocumented host state.
