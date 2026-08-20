# Briefedly database least-privilege design

## Selected role model

```text
briefedly_dba       LOGIN SUPERUSER, operator-only, escrowed, never injected into app
briefedly_owner     NOLOGIN, owns database/schema/migration objects
briefedly_migrator  LOGIN, member of owner, used only by Alembic operations profile
briefedly_runtime   LOGIN, API and worker CRUD/sequence access only
briefedly_backup    LOGIN, SELECT-only logical backup role
briefedly_bootstrap NOLOGIN legacy cluster bootstrap after finalization
```

API and worker share `briefedly_runtime`. Separating them would not materially reduce access because worker jobs span sessions, OAuth nonces, connections, messages, reports, exports, retention, and account/workspace deletion. A second credential with nearly identical grants would add rotation complexity without meaningful blast-radius reduction.

## Ownership and grants

- Database and public schema owner: `briefedly_owner`.
- Migration-controlled tables, sequences, functions, and application-defined types: `briefedly_owner`.
- Runtime: database CONNECT; schema USAGE; table SELECT/INSERT/UPDATE/DELETE; sequence USAGE/SELECT.
- Backup: database CONNECT; schema USAGE; table/sequence SELECT only.
- PUBLIC: database/schema/object privileges revoked where appropriate.
- Future objects: owner default privileges grant only the same runtime and backup rights.
- Runtime and backup are not members of owner.
- Migrator connects using its own credential and Alembic explicitly `SET ROLE briefedly_owner`.

The required `plpgsql` extension remains owned by the disabled legacy bootstrap role because `REASSIGN OWNED` is unsafe for the cluster bootstrap role. Only application-controlled public objects are transferred.

## Required flags

Isolated verification passed for owner, migrator, runtime, and backup:

```text
rolsuper=false
rolcreatedb=false
rolcreaterole=false
rolreplication=false
rolbypassrls=false
```

The operator-only DBA remains superuser by design. The legacy bootstrap remains technically superuser due PostgreSQL’s bootstrap-role invariant, but its password is rotated, LOGIN is disabled, and it is renamed after cutover.

## Negative tests passed on clone

The runtime role was denied:

- CREATE ROLE;
- CREATE DATABASE;
- SET ROLE to owner;
- ALTER owner role;
- CREATE TABLE in public;
- DROP public schema;
- reading `pg_authid`;
- Alembic migration execution.

It also could not gain owner membership or grant itself broader authority. Positive rollback-only CRUD and future default grants passed. A synthetic cross-workspace child relationship was rejected by the composite foreign key.

## Alembic separation

- `MIGRATION_DATABASE_URL` is required independently from runtime `DATABASE_URL`.
- `MIGRATION_DATABASE_ROLE` must be a valid identifier.
- Alembic imports metadata without instantiating runtime application settings.
- The migrator service is in an explicit `operations` Compose profile.
- Deploy scripts call the migrator service; the backend and worker do not receive migration credentials.
- An explicit connection commit preserves `SET ROLE` before Alembic’s transactional DDL block. Rehearsal identified that omitting this commit could log successful upgrades that were rolled back on connection close.

## DB-container secret boundary

Production Compose now sources the database service from its database-only Compose env file, not the backend application env. This prevents Gmail, encryption, application-session, and Ollama secrets from being injected into the PostgreSQL container.

## Production state

Unchanged. Live `briefedly_app` is still login superuser and object owner. BRF-DB-001 remains partially fixed until the gated production sequence completes and the old identity is proven unable to authenticate.
