# Deferred prerequisites

Only these prerequisites are intentionally deferred.

## Tenant commercial mapping

Twelve production tenants currently require authorized mapping. No assignment was performed. The canonical resolver remains fail-closed, and the read-only inventory plus dry-run-first apply tooling are ready for an authorized operator decision.

G15 remains **BLOCKED ON AUTHORIZED COMMERCIAL MAPPING**.

## Physical backup media and full DR

The software path is prepared and a local manifest/checksum backup was verified. Dedicated drives are not yet available. A full replacement-host restore is not yet possible and was not simulated with another machine, cloud provider, Node 2, laptop, or unencrypted local directory.

G18 remains **BLOCKED ON PHYSICAL BACKUP DRIVES / FULL REPLACEMENT-HOST RESTORE**.

## Payment gateway

Payment gateway implementation is future work and is not required for this technical hardening phase. No provider was selected or integrated. The canonical entitlement architecture remains provider-neutral. A future payment implementation requires its own security, webhook, reconciliation, and reliability review.
