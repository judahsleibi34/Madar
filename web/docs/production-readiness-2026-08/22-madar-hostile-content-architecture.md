# Madar hostile-content architecture

Status: **READY** for staged engineering; current general hostile-document handling is not certified for sensitive launch.

## Target flow

```text
authenticated upload
 -> request/tenant/file-count/byte quota reservation
 -> untrusted quarantine store (opaque server ID; no execution; no public delivery)
 -> streaming hash + magic/MIME/container validation
 -> isolated scanner/decoder/parser job
 -> safe derivative or explicitly approved original
 -> immutable registry metadata and tenant ownership
 -> cookie-less static asset origin with safe headers
 -> publication reference
```

The public path never serves the quarantine object. Filenames are display metadata only; filesystem/object keys are generated identifiers. Every transition is durable and idempotent, reconciles DB quota to bytes on disk/object storage, and has expiry/orphan cleanup. A scan error/timeout is quarantine, not approval.

## Format policy

- Images: reject type mismatch, excessive dimensions/pixels/frames/metadata and malformed decoders; decode and re-encode through a patched, resource-limited library to an approved raster format. Treat SVG as active content: sanitize with a proven policy or serve only as attachment from an isolated origin; never inline untrusted SVG into authenticated pages.
- PDF: treat as active/complex. Default attachment disposition from cookie-less origin; optional CDR/rasterized preview in sandbox; block embedded files/scripts/launch actions from preview paths.
- DOC/DOCX/Office: never server-render in the application container. Deliver as attachment from isolated origin or convert through a no-network disposable sandbox/CDR pipeline.
- Video: validate container/codecs/duration/resolution/bitrate and transcode through a sandbox with strict CPU/RAM/time/output limits; do not trust extension or client MIME.
- Archives are rejected unless a product requirement justifies safe extraction with total expanded-byte/file/depth/ratio/path/link limits. Password-protected or unscannable content stays quarantined/rejected.

## Worker boundary

Hostile-content workers run as distinct non-root identities with no application, DB-admin, OAuth, Cloudflare, SMTP or backup secrets. They receive a one-job opaque input and write only to a bounded output location; root filesystem read-only, capabilities dropped, no-new-privileges, seccomp/AppArmor, no Docker socket, no host mounts, no network/DNS/metadata access, PID/file/output/CPU/RAM/time quotas and automatic disposal after each job. Results are structured allow/reject/error metadata, never executable instructions.

Parser/OCR text remains hostile when passed to AI: delimiter/structured context, byte/token limits, no tools/secret access, evidence ownership validation, safe rendering and explicit uncertainty. OCR for Arabic/English/Hebrew must be benchmarked for accuracy and adversarial behavior before product claims.

## Delivery boundary

Use a dedicated asset hostname that cannot receive SaaS authentication cookies and cannot set parent-domain cookies. Apply `nosniff`, correct content type, explicit `Content-Disposition`, restrictive CSP for browser-rendered derivatives, no credentials/CORS except exact need, immutable identity for immutable published assets, and tenant/publication-aware authorization for private originals. Cloudflare/browser cache keys include asset revision/visibility and never transform private into public.

## Tests and rollout

Maintain a legally sourced malicious/malformed corpus: polyglots, MIME/extension mismatch, SVG scripts/external references, huge dimensions, decompression bombs, traversal/link archives, active PDFs, malformed Office/video, parser crashes/timeouts and prompt injection. Assert no network, secrets, host writes, cross-tenant object/reference, quota leak, public quarantine access, cache leak or unbounded resources. Fuzz parsers in disposable CI where safe. Roll out by allowlisted format behind a feature flag; until certified, reject risky formats rather than falling back to in-process parsing.
