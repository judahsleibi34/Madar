# Backup and off-host design

## Current emergency recovery points

### Madar

- Timestamp: 2026-08-18T13:32:32Z.
- Location: local protected backup storage.
- Coverage: PostgreSQL custom dump, builder assets, private uploads, generated artifacts/charts, avatars, metadata manifest, and SHA-256 checksums.
- Modes: backup metadata, dump, and checksum manifest are mode 0600.
- Verification: every manifest entry verified; the DB archive contains 1,059 entries.
- File inventory: 68 builder assets, 3 private uploads, 8 generated artifacts, and 10 avatars.

A separate failed partial run exists with a zero-byte database dump. It is not a recovery point and must never be selected as latest-good.

### Briefedly

- Timestamp: 2026-08-18T13:35:51Z.
- Format: PostgreSQL custom dump.
- Size: 950,863 bytes.
- Mode: 0600.
- Verification: archive listing succeeded with 99 entries; SHA-256 was recorded and later reverified.

### Mailcow

No new Mailcow backup was executed. The installed supported helper covers MariaDB, vmail, crypt, Redis, Rspamd, Postfix, and `mailcow.conf`, but it may pull a floating backup image, exposes the MariaDB root password in process arguments, and requires consistency-aware operational handling. Existing custom Mailcow configuration and DKIM/TLS/cryptographic material must be included without resetting or overwriting the dirty repository.

## Required off-host architecture

Recommended target: an independently administered, versioned object store or backup service with immutable/object-lock retention where available.

```text
source snapshots/dumps
  -> local manifest and checksums
    -> client-side authenticated encryption
      -> restricted append/create backup credential
        -> versioned off-host storage
          -> independent integrity verification
            -> external failure notification
```

Requirements:

- encryption before upload, with keys escrowed separately from application and storage credentials;
- TLS in transit;
- backup identity restricted to creating new objects and reading only what verification requires;
- separate retention/immutability authority so the host credential cannot delete history;
- daily logical recovery set, with more frequent DB snapshots where provider/tooling permits;
- periodic Mailcow-consistent backup during a controlled window;
- daily/weekly/monthly retention sized after provider capacity is known;
- never delete last-known-good before a replacement is verified;
- non-zero job exit on any dump, checksum, encryption, transfer, or remote-confirmation failure.

## Manifest contents

Every run should record, without secrets or customer content:

- timestamp and source host identity;
- repository SHAs and deployed image IDs/digests;
- database schema/Alembic revision;
- object/file counts and aggregate sizes;
- checksum tree/root;
- included configuration categories;
- encryption key identifier, not key material;
- remote object/version identity;
- local and remote verification status.

## Recovery-set coverage

The off-host set must include Madar DB/assets, Briefedly DB, Mailcow’s supported backup set, critical Compose/deploy scripts/systemd unit definitions, Cloudflare tunnel re-provisioning metadata, encrypted application configuration/secrets escrow, Git/image identities, schema revisions, and the manifest itself.

Plaintext `.env` files must not be uploaded to ordinary object storage. Secrets require independent encryption and documented break-glass access control.

## Scheduling recommendation

This is a recommendation, not an established business RPO:

- Madar/Briefedly logical DB: at least daily; 6-hourly is preferable while customer data changes.
- Madar assets: daily plus incremental synchronization where available.
- Mailcow: daily consistency-aware backup if operational impact permits.
- Full manifest/off-host verification: every run.
- Restore drill: monthly for DB/application data; quarterly replacement-host exercise.

With only the current one-time local backups, the effective RPO grows continuously and host-loss recovery remains unavailable.

## Blocker

No restic/borg/rclone/age client, remote mount, off-host endpoint, or restricted backup credential was available. No plaintext or unencrypted upload was attempted. DR-001 remains partially fixed.
