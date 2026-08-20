# Container and frontend edge hardening

The backend runs as UID/GID 65534, matching the ownership of the durable upload directories. The frontend runs as the Nginx `nginx` user on unprivileged port 8080. Redis runs as its image-provided UID/GID. Compose drops all Linux capabilities, enables `no-new-privileges`, uses read-only root filesystems and bounded tmpfs mounts, configures healthchecks and dependency health ordering, sets CPU/memory limits, and rotates local JSON logs.

Base images are digest-pinned. Update each tag and digest together after an approved image review; never replace a digest without rebuilding and running the full validation suite.

## Edge policy

Nginx emits CSP, content-type, referrer, permissions, frame, and opener policies on the app shell and immutable assets. `unsafe-eval` is forbidden. `unsafe-inline` remains limited to styles because the current React/Page Builder runtime uses inline style properties. HTTPS image, font, and media scheme sources are required for validated tenant-supplied content; executable scripts remain same-origin only. The API connection source is injected through `MADAR_CSP_CONNECT_SRC`, which must be the exact public API origin in production.

HSTS is deliberately empty by default. Set `MADAR_HSTS=max-age=31536000; includeSubDomains` only after confirming that every covered hostname is permanently TLS-only at the terminating proxy. COEP is intentionally omitted because public tenant pages use third-party media that does not consistently return cross-origin resource policy headers. COOP remains enabled.

Run an isolated header check after building the frontend:

```bash
docker run --rm -d --name madar-edge-audit -p 127.0.0.1:38080:8080 \
  -e MADAR_CSP_CONNECT_SRC=https://api.staging.example \
  -e 'MADAR_HSTS=max-age=31536000; includeSubDomains' \
  madar-dev-frontend

cd frontend
EXPECT_HSTS=true npm run edge:audit -- http://127.0.0.1:38080
docker stop madar-edge-audit
```

Use an available loopback port and stop the isolated container after the check. Do not run the audit against production.
