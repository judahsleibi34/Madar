# Monorepo web deployment

The Git checkout and web Compose project now have distinct roots:

```text
REPO_ROOT=/home/madar/saas/Madar
WEB_ROOT=/home/madar/saas/Madar/web
COMPOSE_FILE=/home/madar/saas/Madar/web/docker-compose.yml
ENV_FILE=/home/madar/saas/Madar/.env
COMPOSE_PROJECT=madar
```

Git fetch, status, revision, and reset operations remain rooted at
`REPO_ROOT`. Production Compose commands must use all of the following:

```bash
docker compose \
  --project-name madar \
  --project-directory /home/madar/saas/Madar/web \
  --env-file /home/madar/saas/Madar/.env \
  -f /home/madar/saas/Madar/web/docker-compose.yml \
  --profile workers \
  config --quiet
```

The CLI `--env-file` supplies interpolation values. The deployment script also
exports the same absolute `MADAR_ENV_FILE`, so the backend, notification worker,
and calendar worker service-level `env_file` declarations load that exact file.
The file remains outside Git and must stay mode `0600` or otherwise readable
only by the deployment identity.

The four writable application mounts intentionally remain under
`REPO_ROOT/backend/`, matching the paths used before the monorepo move. Code and
read-only migration/script mounts resolve under `WEB_ROOT`. Redis uses tmpfs and
PostgreSQL is external to this Compose stack; neither is recreated by the path
change. The production script exports `MADAR_STORAGE_ROOT` as the absolute
legacy directory; the Compose fallback `../backend` provides the same result
when commands are run from `web/`.

## Deployment-script installation gate

The reviewed source copies are:

- `web/deployment/bin/madar-auto-deploy`
- `web/deployment/bin/madar-production-deploy`

They are candidates for `/usr/local/sbin/madar-auto-deploy` and
`/home/madar/docker_auto.sh`. Do not replace the live scripts while the timer is
active: because production is behind `origin/main`, the next timer event would
immediately attempt a deployment. An operator must first establish an approved
maintenance/deployment window, prevent timer races, install and checksum the
reviewed files, install the updated storage-preparation drop-in, run
`systemctl daemon-reload`, validate the exact Compose command above, and only
then explicitly start or re-enable the deployment path.

The deploy script preserves the Compose project name `madar`, includes the
notification-worker profile, validates configuration before building, waits for
container health, checks backend readiness and frontend HTTP health, and can
select the old root Compose layout after resetting to a pre-monorepo commit.
Migrations are deliberately not automatic because application rollback cannot
undo schema or data changes safely.

## Manual development

From `web/`, use the repository-root environment file explicitly:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.dev.yml config
```

Use a non-production environment file for local development whenever possible.
The mobile application has its own dependency and build lifecycle and is not a
Compose service.
