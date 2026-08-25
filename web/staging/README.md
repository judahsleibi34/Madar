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
2. Run `prepare_networks.py`. It creates/attests labeled, slot-specific
   networks with explicit `10.251.0.0/21` child ranges so staging does not
   depend on Docker's finite implicit address pools.
3. Start `docker-compose.control.yml`; prepare a fresh schema 81 with
   `prepare_database.sh 81`.
4. Build immutable SHA images and start slots through `madar-release-deploy`
   with `docker-compose.slot.yml` as the override.
5. Generate and verify a format-3 backup, then use `madar-migrate` for 82/83.
6. Start the schema-83-only deletion-worker profile explicitly.
7. Switch only the local staging proxy. Production ports and routing are never
   modified.

After preparation, deploy a committed candidate with the wrapper so host-side
gateway, storage, and file-proxy settings cannot drift between drills:

```bash
web/staging/deploy.sh "$(git rev-parse HEAD)"
web/staging/deploy.sh "$(git rev-parse HEAD)" --manual-retry
```

The control database uses tmpfs. Loss on teardown is intentional.
