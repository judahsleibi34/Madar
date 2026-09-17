# Madar monorepo

This repository contains two separate applications:

- `web/` — the production web backend, frontend, database migrations, Docker
  Compose stack, and web operations tooling.
- `mobile/` — an independent Expo/React Native application. It is not built or
  deployed by the production web Compose stack.

Run Git commands from the repository root. Run web application commands from
`web/`, and mobile commands from `mobile/`.

Production web deployment uses the repository-root environment file explicitly
and preserves the existing repository-root `backend/{uploads,avatar_uploads,
private_uploads,private_generated_charts}` host directories. See
[`web/docs/monorepo-deployment.md`](web/docs/monorepo-deployment.md) before
changing the production timer or deploying.
