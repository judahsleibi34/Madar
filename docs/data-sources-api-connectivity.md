# Data Sources provider-independent API connectivity

This document defines the C2 source-only outbound HTTP foundation. It does not
select migrations147–155, enable a production connector, or authorize external
traffic. The only executable provider added by C2 is a deterministic loopback
fixture (`http_fixture` / `records`) that requires `APP_ENV=test` exactly.

## Trust boundaries

Data Source rows contain only a bounded provider key and resource key. They never
contain URLs, headers, access tokens, storage keys, or arbitrary request parameters.
An operator-owned registry maps those keys to an exact HTTPS origin, fixed resource
paths, authentication scheme, and rate policy. C2 represents that registry with
immutable `ProviderSpec` and `ResourceSpec` instances created by server code; no
public API constructs them.

Before connecting, the transport resolves the configured HTTPS hostname, rejects an
empty, mixed, private, loopback, link-local, multicast, unspecified, metadata-service,
or CGNAT answer, and permits only port443. It then connects to the validated numeric
address while retaining the configured hostname for TLS SNI and certificate checks.
The address remains pinned for the session, preventing a second DNS lookup from
redirecting the connection. Redirects are rejected. Proxy environment variables are
not used. A plain-HTTP loopback origin is accepted only for the local fixture when
`APP_ENV` is exactly `test`; its address is pinned to `127.0.0.1`.

Only idempotent GET exists. Paths and query names come from the registry/adapter;
continuation and cursor values are length/control-character bounded and encoded.
Connections, response reads, total fetch elapsed time, pages, records, compressed
bytes, decompressed bytes, JSON depth, columns, scalar sizes, and normalized bytes are
bounded. Cancellation and ingestion-lease heartbeat callbacks run before requests and
during response reads. Retries are limited to transport failures, 5xx, and bounded
429 `Retry-After` values. Audit events contain only provider key, outcome, safe error
code, status, attempt, byte count, and elapsed time—never targets, bodies, or secrets.

## Candidate credential lifecycle (schema155, unselected)

Candidate155 adds the separately reviewed Data Sources credential service. It remains
unselected and is not operational in any persistent environment. The schema stores
tenant/project/source/provider-scoped immutable AES-256-GCM envelopes and secret-free
lifecycle events. HashiCorp Vault Transit generates, wraps, unwraps, and rewraps a
fresh 256-bit data key for each version; PostgreSQL never stores plaintext keys.
Calendar's key remains isolated and is not reused. The candidate enforces:

- ciphertext rows are tenant/source scoped and reference a key version; source JSON
  stores only a non-secret credential reference;
- encryption uses a dedicated Vault Transit envelope-key boundary, with old-key decrypt
  during rotation and current-key encrypt for new versions;
- service-role RPCs require exact tenant, project, source, actor, active membership,
  source status, and credential revision; browser roles receive no table privileges;
- workers receive decrypted material only for one fenced ingestion lease, keep it out
  of logs/errors/audit/LLM inputs, and erase references after the request;
- rotation is compare-and-swap, revocation prevents new leases immediately, active
  leases re-check revision/revocation before each page and before commit, and all
  actions emit secret-free audit evidence;
- backup/restore, key loss, revocation races, collaborator authorization, and incident
  recovery receive an independent security rehearsal before production use.

Madar reads a short-lived renewable application token only from a private Vault Agent
file sink. AppRole RoleID and response-wrapped SecretID bootstrap occur outside source,
ordinary environment files, and PostgreSQL. Root tokens, unseal material, key
administration, policies, audit administration, and backups belong to a separate
operator identity. See `web/deployment/vault/README.md`.

Before schema155, or whenever Vault/configuration is unavailable, persistent
credential operations fail closed while legacy uploads remain unchanged. The
exact-test-only in-memory store remains solely for deterministic unit fixtures.

OAuth, user-supplied generic endpoints, webhook secrets, scheduled synchronization,
and named providers are outside C2.

## Provider response contract

The neutral JSON response contains `records`, an optional intermediate
`continuation`, and a terminal `cursor`. A record has a stable `id`, `operation`
(`upsert` or `delete`), optional monotonic `revision`, optional deduplication
`event_id`, and scalar `data`. A cursor is accepted only on the terminal page.
Continuation loops, partial pagination, duplicate IDs within a run, inconsistent
schemas, nested values, stale/duplicate changes, and malformed tombstones fail or are
classified by the existing incremental ingestion contract. The database advances the
resource cursor only in the same fenced transaction that commits current state,
immutable history, revision, run lineage, and quota-accounted storage.

## Activation boundary

No real destination is registered by this milestone. Staging a future provider
requires an explicit operator registry entry, dedicated encrypted credentials, egress
policy review, synthetic tenant/project tests, DNS/TLS/redirect/rate/failure evidence,
and the full Data Sources schema and worker gates. Data Logs remains outside this
workflow.
