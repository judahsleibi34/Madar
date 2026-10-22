# Madar Data Sources Vault Transit runbook

These are reviewed installation templates, not an enabled service. C2 Step 2 does
not install Vault, initialize a persistent cluster, create real keys, change the
active release, or authorize customer credentials.

## Security boundary

PostgreSQL stores only AES-256-GCM ciphertext, a random 96-bit nonce, and the
Vault-wrapped per-version 256-bit data key. Vault integrated Raft stores the Transit
root material. The application never receives that root material. Running Vault and
Madar on one physical host provides process, identity, policy, and backup separation,
but it does **not** protect credentials from an attacker who controls the whole host,
kernel, root account, memory, or both services.

The implementation follows HashiCorp's documented Transit data-key/rewrap API,
integrated Raft storage, AppRole response-wrapping, Agent auto-auth file sink, and
hashed audit-device behavior. The Transit key must be created with `derived=true`
because the versioned credential scope is supplied as Transit context.

Authoritative references: [Transit API](https://developer.hashicorp.com/vault/api-docs/secret/transit),
[integrated Raft storage](https://developer.hashicorp.com/vault/docs/configuration/storage/raft),
[AppRole Agent auto-auth](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth/methods/approle),
[Agent file sink](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth/sinks/file),
[response wrapping](https://developer.hashicorp.com/vault/docs/concepts/response-wrapping),
[audit guidance](https://developer.hashicorp.com/vault/docs/audit/best-practices), and
[Raft snapshots](https://developer.hashicorp.com/vault/docs/commands/operator/raft).

## Operator-only initial setup

Perform these steps interactively under a separate Vault operator identity after an
independent installation review:

1. Install a pinned, verified Vault package and create a dedicated non-login `vault`
   service user. The configuration, TLS private key, Raft directory, and audit
   directory must be owned by that identity with no group/world write access.
2. Bind the API to loopback or an isolated management network, enable TLS, and verify
   certificates. Never publish ports 8200/8201 to the internet.
3. Initialize once with distinct Shamir key holders. Move unseal shares and the
   initial root token to separate offline custody. Revoke ordinary use of the root
   token after policy/auth bootstrap.
4. Enable Transit at `transit/`, then create `madar-data-sources` as a derived AES-256
   key with deletion disabled and plaintext backup disabled.
5. Load `data-sources-transit-policy.hcl`. Create a separate AppRole limited to this
   policy, with short token TTLs, bounded maximum TTL, renewable tokens, and SecretID
   use/TTL limits. Operator/admin policies must never be attached to this role.
6. Deliver the RoleID and a short-lived response-wrapped SecretID through a protected
   root/operator channel into the private bootstrap paths shown in `agent.hcl.example`.
   Do not place either value in source control or the normal Madar `.env`; Vault Agent
   consumes and removes the wrapped SecretID and writes a mode-0400 renewable token
   into a tmpfs-backed sink.
7. Configure Madar with only non-secret address/key metadata and file locations:
   `DATA_SOURCE_VAULT_ADDR`, `DATA_SOURCE_VAULT_TRANSIT_KEY`,
   `DATA_SOURCE_VAULT_TRANSIT_MOUNT`, `DATA_SOURCE_VAULT_CA_CERT`, and
   `DATA_SOURCE_VAULT_TOKEN_FILE`. The token itself remains in the private sink file.
8. Enable a Vault audit device on a dedicated protected filesystem. Leave HMAC
   hashing enabled for sensitive request/response fields; never enable raw logging.

If secure delivery of the wrapped SecretID and private token sink cannot be provided,
the connector must remain disabled. A permanent token in Compose, `.env`, a unit
file, source, or PostgreSQL is not an acceptable fallback.

## Restart and unsealing

With Shamir sealing, a Vault restart leaves the server sealed. Required independent
key holders manually submit the threshold shares over a verified local TLS channel.
Only after Vault reports unsealed and post-unseal setup is complete should Vault Agent
authenticate and Madar workers resume. Until then, all credential operations fail
closed and ingestion cursors remain unchanged. Do not store shares beside Vault or
script unsafe automatic unsealing.

## Backup and disaster recovery

- Take authenticated Raft snapshots on a reviewed schedule. Encrypt snapshots again
  with a separately controlled backup key and replicate them off-host.
- PostgreSQL and Vault snapshots form a coordinated recovery set. A database backup
  alone contains unusable ciphertext; a Vault snapshot alone contains no datasets or
  credential ownership metadata.
- Retain every Transit key version referenced by any retained database backup. Rotate
  the Transit key, rewrap data keys, verify reads, and only then consider key-version
  retirement under a separate destructive review.
- Rehearse restoration on an isolated host: restore Raft, unseal, restore PostgreSQL,
  verify TLS/policies/AppRole, resolve synthetic credentials, then destroy the test.
- Never copy production unseal shares, tokens, credentials, or backups into developer
  tests.

## Disposable tests

Tests may use Vault dev mode only inside an isolated, loopback-only disposable
container/process with synthetic tokens and credentials. The test token is passed via
a mode-0400 temporary file, not an environment variable consumed by Madar. Destroy
the container, volume, token file, and disposable database after every run.
