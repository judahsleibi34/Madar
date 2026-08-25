# Isolated Node 1 staging harness

This harness is loopback-only and uses disposable PostgreSQL, local PostgREST,
synthetic Auth/Storage fixtures, slot-local Redis, and separate blue/green
Compose projects. It never depends on production data, Cloudflare, SMTP, OAuth,
AI providers, or customer endpoints.

The provider facade is intentionally not production software. It exists to
exercise Madar's application/REST/database boundary while provider-specific
failure behavior remains covered by fake-adapter tests.

Lifecycle:

1. Create a private runtime root and generated environment/JWT fixtures.
2. Start `docker-compose.control.yml`; prepare a fresh schema 81 with
   `prepare_database.sh 81`.
3. Build immutable SHA images and start slots through `madar-release-deploy`
   with `docker-compose.slot.yml` as the override.
4. Generate and verify a format-3 backup, then use `madar-migrate` for 82/83.
5. Start the schema-83-only deletion-worker profile explicitly.
6. Switch only the local staging proxy. Production ports and routing are never
   modified.

The control database uses tmpfs. Loss on teardown is intentional.
