# Verification matrix

Statuses apply to the stated scope; synthetic PASS never authorizes production.
Native64=19 coordinated+5 upgrade+18 fencing+22 business. Full backend conditional
skips are not counted as native PASS. Final evidence/CI references: FINAL-REPORT.

| Area | Status | Executed evidence / limitation |
|---|---|---|
|Authentication|PASS|Native valid/invalid password, invalid JWT, refresh rotation; restored original identity; synthetic only|
|MFA|PASS|Real GoTrue TOTP, AAL1 admin denial/AAL2 access, restricted cookie flow, browser and restored original factor|
|Authorization|PASS|Native regular-user admin/path-user spoof rejection; broad regression suite; selected routes|
|Tenant isolation|PARTIAL|Native bidirectional project read/delete IDOR, unchanged foreign rows, disabled membership and business RPC tenant rejection; every domain not certified|
|Database integrity|PASS|Exact native146→147→148, journals/history/ACLs/locks/rollback; synthetic datasets|
|Reservations|PASS|Concurrent capacity, reactivation race/held transaction, cancellation/retry, tenant/direct mutation denial|
|E-commerce/inventory|PASS|Native no-oversell, variants, rollback/restore/idempotency/decimal snapshots|
|Payments|PARTIAL|Native replay/refund/COD/provider-ID integrity; synthetic gateway, no live settlement|
|Forms concurrent edits/deletion|PARTIAL|Existing frontend/backend regression checks; full native multi-browser workflow not executed|
|Website builder/publishing|PARTIAL|Native project tenant reads; complete publish/browser/public-host matrix not executed|
|Assets/Storage|PASS|Native private deny, original restored bytes/metadata/grants, mediated old avatar URL; selected assets|
|Workers|PARTIAL|Native leases/crash/restart/all stale outcomes and real148 HTTP delivery; full privileged supervisor/legacy Python matrix incomplete|
|Counter integrity|PASS|Before40!=0 repro; corrected worker main loop + native stale acknowledgement case; no false sent increment|
|Cache|PARTIAL|Prior cache race regression tests retained; cross-process invalidation not implemented|
|Redis|PARTIAL|Owned stacks healthy/bounded; previous failure drill historical, not a new exhaustive outage test|
|Staging|PARTIAL|Independent native services/fresh image acceptance; selected flows, not complete production-control-plane parity|
|Backup|PASS|Owned synthetic logical/roles/objects and physical base backup checks; no production backup certification|
|Restore|PARTIAL|Fresh independent cluster/full native app + original Auth/MFA/objects +22 business; same VM, no off-host/bare-host|
|PITR|PARTIAL|Actual paused named-target WAL recovery + incomplete/missing/corrupt negative cases; component only|
|API contracts/errors|PASS|Broad backend and native Auth/CSRF/Storage/worker calls; selected native surface|
|Frontend|PARTIAL|Lint/build233 files,1713 PASS/1 skip, selected Chromium flows; complete product E2E pending|
|Performance|PARTIAL|Bounded randomized paired read workload indexed in13; no general speedup/p99/production capacity claim|
|CI|PASS|Exact32c release-code backend/frontend/artifact workflows pass; authenticated run records retained|
|Release safety|PARTIAL|Protected source/interface tests + actual SQL interruptions; real controller installation/reboot/current-data gates not executed|
|Observability|PARTIAL|Actual worker metrics inspection and4 real HTTP alert-injection cases; no production monitoring daemon/alert delivery configured|
|Production|PASS|Read-only inspection only; no production migration/restart/grant/billing/controller/route/customer-data change|

Detailed43-gate production assessment remains NOT READY in15-PRODUCTION-READINESS.md.
