# Briefedly security, Gmail, AI, and privacy audit

## OAuth and Gmail

State contains issuer/audience/user/workspace/provider and expiry, while the database stores only its hash. Callback atomically consumes the nonce once and requires the same authenticated user/workspace. Redirect URI is operator-configured and production-validated as HTTPS. Tokens are encrypted with Fernet at rest; provider account identity is fetched and bound to the workspace connection. Scope is read-only Gmail plus OpenID/email.

PKCE is absent. It is defense-in-depth for this confidential server flow rather than a primary bypass, but should be added. Disconnect attempts provider revocation and clears local ciphertext even if revocation fails; this gives the user a successful local disconnect while a refresh token may remain usable until Google revokes/expires it. Persist a bounded revocation-retry state and surface an audit status without logging tokens.

## Import pipeline

Gmail search/import uses bounded results, message/thread limits, pagination for synchronization, content hashes/provider IDs for deduplication, durable job accounting, and controlled retry. MIME depth and body length are bounded. Raw bodies have a default 720-hour retention marker; cleanup also removes report excerpts derived from expired raw content.

HTML email is stored as hostile data and not injected into the frontend DOM. Remote tracking images are not rendered by the reviewed UI. Attachments are not a broad general-purpose ingestion surface in the current implementation. Partial and failed counts remain explicit in job/report records.

## AI integrity and prompt injection

Imported email is clearly delimited as untrusted evidence. The prompt forbids obeying email instructions, requests structured JSON, and requires source identifiers. Outputs are Pydantic-validated and mapped back to known message/thread evidence. Empty/all-failed input does not become a successful authoritative report. Reports expose analyzed/skipped/truncated/failed counts and should retain uncertainty language.

AI output is not used to authorize, execute commands, fetch arbitrary URLs, or mutate external systems. No dangerous Markdown/HTML sink was found. These are strong controls. They reduce but do not eliminate semantic prompt injection/hallucination; reports must remain advisory and source-linked.

## Ollama transport

Running production and development both use unauthenticated HTTP to a Tailscale IP on port 11434. Tailscale encrypts the overlay, but application identity/authentication depends entirely on tailnet ACL/device integrity. Another authorized/compromised tailnet peer or endpoint compromise could impersonate the model or read prompts. No host-public 11434 listener was found here.

More urgently, current production config validation permits HTTP only for loopback/`ollama` container hosts. Therefore the current source cannot start with the deployed Tailscale URL. Choose and test one design before deployment: authenticated HTTPS with certificate validation, or a local authenticated proxy/sidecar over a constrained tailnet. Do not weaken the validator to accept arbitrary private HTTP.

## Privacy lifecycle

Current source has workspace/account export and deletion jobs, recent-password/CSRF checks, idempotency, expiring private export artifacts, OAuth nonce cleanup, raw-email retention, and provider disconnect. In production these workflows are unavailable because the worker and five schema revisions are missing. Thus documented lifecycle capability is not effective operational capability.

The production DB currently contains no customer workspace/email rows, reducing present data impact but not launch risk. Before real Gmail: prove token re-encryption rotation, revocation, raw-body cleanup, workspace/account deletion, backup retention, artifact expiry, and restore/deletion interaction in staging.
