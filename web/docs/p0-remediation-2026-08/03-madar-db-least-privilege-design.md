# Madar database least-privilege design

## Decision

Eliminate the direct PostgreSQL connection from all Madar application runtime services. Do not replace it with another runtime SQL role. Retain direct SQL only for operator-controlled backup, migration, and narrowly reviewed verification commands.

## Implemented in development

- API, notification worker, and calendar worker explicitly override `SUPABASE_DB_URL` to an empty value after the shared env file is loaded.
- A regression test validates that all three runtime services drop the direct credential.
- Backup and restore scripts use standard libpq environment variables instead of putting credential-bearing URLs in process arguments.
- Restore supports a reviewed TOC list for environments where provider-specific extension objects must be excluded.
- Documentation distinguishes full Supabase recovery from a partial vanilla-PostgreSQL restore.

## Access categories

| Operation | Path | Credential class |
|---|---|---|
| Runtime CRUD/RPC | Supabase PostgREST/RPC | service role, only for services that require it |
| Public/browser requests | Supabase public interface | anon/public key |
| Backup | direct PostgreSQL | operator-only backup credential |
| Migration/schema maintenance | direct PostgreSQL/provider tooling | operator/migration credential |
| RLS/grant verification | direct PostgreSQL | temporary operator verification path |
| Parser/remote ingestion | no DB path | no DB/admin credential |

## Required production verification

Before cutover, prove the replacement operator role has:

```text
rolsuper=false
rolcreatedb=false
rolcreaterole=false
rolreplication=false
rolbypassrls=false
```

It must not create roles/databases, alter protected schemas, read unrelated internal schemas, bypass RLS, grant itself privileges, or perform unapproved migrations. Runtime services must show the direct URL as absent/empty and must still pass auth, tenant, builder, publication, form, reservation, storage, billing, notification, calendar, parser, and readiness tests.

## Current limitation

Madar’s database dump contains the provider-specific `supabase_vault` extension and vault schema. A raw PostgreSQL 17 image cannot faithfully restore those objects. The reviewed partial restore excluded exactly those provider-specific entries and restored the public application schema and files, but full disaster recovery requires a compatible Supabase recovery environment or provider-supported restore procedure.

## Production state

Unchanged. The current runtime containers still receive the exposed direct credential. MADAR-DB-001 is therefore only partially fixed.
