# Storage and upload review

## Effective limits

| Payload | Limit |
| --- | ---: |
| Builder image | **25 MiB exactly (26,214,400 bytes)** |
| Builder document | 50 MiB |
| Builder video | 250 MiB |
| Whole builder multipart request | 252 MiB |
| Generic request | 12 MiB |
| Builder JSON | 3 MiB |
| Small JSON | 256 KiB |
| Data JSON | 1 MiB |
| Avatar | 5 MiB |

The image limit is defined as `25 * 1024 * 1024` and production Compose defaults to `26214400`. The endpoint checks the multipart file size before reservation and the streamed byte count while copying (`builder_routes.py:1611-1637,1688-1701`). The middleware independently caps the entire request.

## Validation and storage flow

Images: PNG/JPEG/WebP only. Videos: MP4/WebM. Documents: PDF/DOC/DOCX. Declared MIME, extension and detected signature must agree. DOCX validation bounds entry count, entry sizes, total uncompressed size and compression ratio. SVG/XML and executable extensions are rejected. Files are copied in chunks to exclusive-create random names inside a tenant directory; path helpers resolve and assert confinement.

After local validation the service writes to durable Supabase Storage, registers the tenant-owned asset, updates references and commits the database quota reservation. Failure paths remove local/remote objects and release reservations where possible. Storage readiness performs an actual create/write/delete probe and currently passes.

## Quota/accounting result

Migration 056 serializes each `(tenant_id, scope_key)` account through insert/update row locks. Live data has zero negative/over-quota counters, zero expired storage reservations, and tenant `used_bytes` exactly equals active storage-object bytes (148,121,559). Concurrent builder/dataset/chart reservations are therefore sound.

The lifecycle is incomplete:

- expired reservation release and unreferenced asset deletion are operator scripts, not scheduled jobs;
- 52 unreferenced assets are already past retention;
- avatars upload directly to the public avatar bucket and are not registered in `storage_objects` or tenant quota;
- the four host roots are `0755` and all observed files are `0644`, allowing other host users to read private datasets/charts;
- root storage preparation recursively `chown -R`s all content every two-minute timer invocation, an O(number of files) privileged operation;
- malware scanning/content disarm is absent. Signature/structure checks are not malware detection.

## Failure behavior

Low free disk or inaccessible roots return controlled 507/storage errors and readiness fails. Durable Storage or registry failure attempts compensating cleanup. Process death after reservation can strand quota until reconciliation; no live expired reservations existed at audit time, but no scheduler guarantees recovery. Fix cleanup scheduling, quota coverage, host modes and monitoring before declaring the storage gate unconditional.
