# Storage and quota validation

## Avatar accounting

The operator tool is dry-run by default and requires explicit `--apply`. Synthetic tests verify tenant/user scope, size calculation, already-accounted avatars, duplicate registry entries, missing files, idempotency, transaction safety, and exact reconciliation. The production inventory was not mutated.

## Reconciliation

The final staging dry-run completed with status `complete`, batch limit 100, and no eligible deletion, missing file, or hash mismatch in the final clean fixture. Synthetic tests additionally covered referenced, unreferenced active, expired, DB/file mismatch, hash mismatch, a concurrently created reference, deletion recheck, batch bounds, and lock collision. No production asset was deleted.

## Permissions

Staging storage directories use reviewed `0750` ownership and files use `0600`. The runtime identity (UID 65534, trusted GID 1000) successfully created and read a `0600` write probe; an unrelated host account could not read it. Restrictive umask is applied and recursive ownership repair is absent from the deploy timer hot path.

## Asset boundary and limits

- Draft assets are same-tenant authenticated and `no-store`.
- Published referenced assets are public/cacheable only through a validated publication.
- Cross-project and cross-tenant asset references are rejected.
- Missing/deleted publication behavior fails closed.
- Exact 25 MiB image acceptance and 25 MiB + 1 byte rejection remain regression-tested, along with document/video limits, storage outage, quota boundaries, and concurrent avatar replacement.

A production permission migration remains an explicit future promotion command; it was not run in this campaign.
