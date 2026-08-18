# Madar builder, publication, forms, reservations, and storage audit

## Builder and publication

Draft writes use expected revisions, semantic schema validation, bounded payloads, tenant/project scope, and audit events. Publishing validates and snapshots a schema, then atomically activates a project/site publication. The public renderer refuses ambiguous site/project/page/form state rather than silently selecting a first row. Header/footer/settings are carried through the selected snapshot, limiting live-table drift.

Frontend recovery is scoped by user/tenant/project and is not automatically authoritative, but full builder data is persisted in localStorage and broadcast between tabs. A shared browser, compromised extension, or same-origin XSS can therefore expose unpublished tenant content. Recovery/export should eventually use an encrypted, bounded, expiring store or clearly documented local-device risk.

The frontend test suite exposed two current Page Builder renderer regressions: saved two-column alignment and authored under-text artwork positioning. The full Vitest run did not terminate cleanly within the audit execution window and did not produce a complete summary. These are not cross-tenant defects, but they undermine confidence in cross-device publication fidelity.

## Upload and parser chain

Upload → request/body ceiling → per-type size limit → extension/MIME/magic check → quota reservation → atomic local/Supabase write → registry/object accounting → parser worker when applicable → reference reconciliation/publication.

Strong controls: path components are generated rather than trusted; SVG/HTML/JS are excluded; PDF and Office containers receive structural checks; DOCX ZIP members and expansion ratios are bounded; quota reservations are committed/released transactionally; failed files are cleaned up; unreferenced assets receive retention state; parser worker is non-root, read-only, resource-limited, and on an internal network.

Residual risks: there is no AV/CDR layer; image/video checks rely mainly on signatures rather than safe decode/transcode; PDFs/DOC/DOCX are delivered inline from the application origin. Hostile active PDF behavior or browser/plugin quirks should be contained with attachment disposition or a separate cookie-less asset domain. Future OCR must never parse hostile Office/PDF content inside the credential-bearing backend container.

Production aggregates: 85 builder asset rows, 95 active storage objects, 10 storage accounts totaling ~291 MB used and zero reserved; 95 committed and 14 released reservations. These counts are internally plausible but not a proof of byte-for-byte filesystem/DB consistency. A scheduled reconciler should compare registry, objects, references, and files without reading customer content.

## Forms and tests

Public submissions bind the form to the selected tenant/project/publication; bound arrays/string sizes, form field counts, honeypot/timing checks, rate limiting, and request idempotency are present. Stored values are rendered as text in reviewed dashboards, and CSV formula neutralization is present. Arbitrary sensitive custom fields remain a product/privacy risk: the platform lacks a tenant-configurable privacy notice/consent and retention/deletion policy at collection time.

Randomized tests must continue to treat the server-side published form/snapshot as authoritative. UI-only tab-leave behavior is deterrence/telemetry, not secure anti-cheat. No claim should suggest it prevents a determined client from switching applications or modifying JavaScript.

## Reservations

Availability and booking use a database RPC with exclusive overlap checks, tenant/project/block scope, idempotency hash, bounded input, and timezone-aware timestamps. Cancellation tokens are random, stored hashed, expire, and are single-use. This is strong concurrency design. Calendar synchronization remains eventually consistent; production has 1,901 successful and three failed inbound connection-sync jobs, which requires operator visibility but is below the readiness failure threshold.
