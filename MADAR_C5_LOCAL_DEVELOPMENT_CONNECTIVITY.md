# Madar C5 Step 2A — Local Development API Connectivity

## Owner correction — production database through SSH

The owner confirmed that this workstation intentionally uses the production
database through the existing SSH tunnel. The temporary local-database repair
was therefore reverted completely.

Current browser path:

```text
Chrome localhost:5173
  -> Vite /api proxy
  -> native FastAPI 127.0.0.1:8000
  -> SSH-forwarded production Supabase 127.0.0.1:18080
  -> production schema 146
```

The existing SSH PostgreSQL forward at `127.0.0.1:15433` is also accepting
connections. FastAPI normally uses the Supabase Auth/PostgREST/Storage API, so
its configured provider URL is the SSH HTTP forward on port 18080. It does not
bypass the tunnel or use the public production API URL.

Local-only cleanup completed:

- Stopped the temporary native schema-142 API process.
- Ran `supabase stop --no-backup` for the exact local project `web`, deleting
  its containers and local data volumes as explicitly requested by the owner.
- Removed `web/.env.database.local` and
  `web/.env.database.local.disabled`.
- No service remains on local Supabase ports 54321/54322.

The native API now loads the existing protected production credentials while
pinning `SUPABASE_URL=http://127.0.0.1:18080`, schema compatibility 144–146,
and localhost browser origin/cookie settings. Workstation-only worker, backup,
calendar, and push readiness requirements are disabled in this local process;
their production services and configuration were not changed.

Final evidence through the actual port-5173 Vite process:

- `GET /api/health/ready`: 200; database, Auth, Storage, and schema all `ok`.
- `GET /api/health/version`: 200; compatibility range 144–146.
- Service-role read through the SSH relay reported production schema 146.
- `pg_isready` on the SSH PostgreSQL forward at 15433: accepting connections.
- An unauthenticated Data Sources request reaches FastAPI and returns 401, not
  the previous route-mismatch 404.

No production migration, data mutation, service restart, deployment, release
selection, commit, push, or merge was performed. Only read-only production
health/schema checks were made through the already-running SSH tunnel.

## 1. Exact reason for the 404

The Data Sources route was present in the current FastAPI source and in the running local backend image. The 404 did not originate from FastAPI route registration, a route-prefix mismatch, or an older-schema capability response.

The owner-specific ignored file `web/frontend/.env.development.local` contained:

```dotenv
VITE_DEV_PROXY_TARGET=https://api.madarportal.com
VITE_DEV_PROXY_REQUEST_ORIGIN=https://madarportal.com
```

Vite therefore accepted the browser request at `localhost:5173`, removed the `/api` prefix as designed, and forwarded the request to the production API. That remote backend did not expose the local candidate Data Sources contract and returned the observed 404. The browser Network panel showed port 5173 because Vite was the browser-facing origin; it was not evidence that Vite itself generated the response.

There was also no listener on the native-backend default port 8000. The actual local Compose backend was bound to port 8002. The explicit production override took precedence over both the Vite default and the correct Compose port.

Direct evidence:

- The running backend OpenAPI document contains `/users/{user_id}/data/projects/{project_id}/sources` plus the complete dataset-version, source, webhook, and dashboard route set.
- A direct unauthenticated request to port 8002 returned 401 `Not logged in`, not 404.
- After correction, the same request through live port 5173 returned the identical 401 response from Uvicorn.
- `/api/health/version` through port 5173 and `/health/version` through port 8002 returned the same local `development` identity.

## 2. Actual frontend and backend processes/ports

Observed on 2026-10-25 (Asia/Hebron):

- Frontend: Node/Vite PID 1325612, started 15:44:22, command `node .../web/frontend/node_modules/.bin/vite`, listening on `127.0.0.1:5173`.
- Backend: Docker container `madar-dev-backend`, image `sha256:973e7412c6f311e99fe509cfdf42cc4e429165abb2b7c632f076e36814943f83`, listening as `127.0.0.1:8002 -> container:8000`.
- Redis: Docker container `madar-dev-redis`; not exposed publicly.
- Native port 8000: no listener.
- A temporary corrected Vite process used for comparison selected port 5174 because 5173 was occupied; it was stopped after the comparison.

The existing Vite process hot-reloaded after `vite.config.js` and its local environment were corrected, so it did not need to be killed. Port 5173 remained owned by the original local process.

The backend image is current enough to expose all C4/C5 routes. Its liveness is 200, but its readiness is 503 because its configured database API hostname is `madar-supabase:8000` and no such local container/network service is running. This database-readiness issue is distinct from the fixed 404/proxy mismatch.

## 3. Exact fix and startup configuration

The ignored owner-local configuration now uses the existing Compose development backend:

```dotenv
VITE_DEV_PROXY_TARGET=http://127.0.0.1:8002
VITE_DEV_PROXY_REQUEST_ORIGIN=http://localhost:5173
```

`vite.config.js` now rejects any non-loopback `VITE_DEV_PROXY_TARGET` or `VITE_DEV_PROXY_REQUEST_ORIGIN` while serving development. This prevents an ordinary `npm run dev` session from silently proxying authenticated local browser traffic to production or another remote API. Production builds are unaffected and continue to use the separately enforced same-origin `/api` contract.

`web/README.md` now documents both supported local pairings:

- Host Vite 5173 + Compose backend 8002: use the ignored loopback overrides above.
- Host Vite 5173 + native `backend/run_local.py` backend 8000: omit the overrides and use Vite's loopback default.

The README explicitly requires restarting Vite after changing the local environment. In this repair, the tracked Vite configuration change triggered its own safe development-server reload.

## 4. Disposable candidate-schema database requirement

The source registry begins at schema 148, Google Sheets at 161, webhooks at 162, and persistent BI dashboards at 163. Therefore full C4/C5 verification requires candidate schemas beyond the selected release schema 146.

The existing Compose backend advertises an older 81–105 compatibility range and currently has no reachable local database service. It can prove route identity and authentication handling, but it cannot provide an authorized project session or C5 data until an appropriate local database is supplied.

No candidate migration was applied to that existing/persistent development target. Full authorized verification used a fresh disposable PostgreSQL/PostgREST/Vault/private-storage stack, progressed through the required candidate schemas, and removed its containers/database afterward. This was necessary and is safer than altering an unidentified retained database merely to make the UI load.

On a reachable database below schema 148, the source-list route returns the existing honest response:

```json
{
  "available": false,
  "items": [],
  "pagination": { "has_more": false }
}
```

It does not return a missing-route 404 or pretend the source registry exists.

## 5. Real browser verification results

### Live ordinary Vite process on port 5173

A headless Chromium page opened the actual `http://127.0.0.1:5173` process and performed same-origin browser `fetch` calls:

- `GET /api/health/version`: 200, local `development` backend identity.
- `GET /api/users/1/data/projects/00000000-0000-4000-8000-000000000001/sources?limit=100`: 401 `Not logged in`.

The 401 is the correct unauthenticated FastAPI behavior and proves the route reached the local backend. The unexpected 404 is gone. No production fallback occurred.

### Authorized disposable browser stack

The full real Vite → FastAPI → PostgreSQL/PostgREST → Vault/private storage browser suite passed with synthetic tenant/project accounts:

- Older schema 141 capability fallback: 1/1 passed (4.0 seconds).
- Authorized Data Sources onboarding, source listing, automatic synchronization, freshness, project isolation, and revocation: 1/1 passed (1.0 minute).
- Google Sheets offline OAuth/mapping/stable sync/conservative deletion/revocation: 1/1 passed (49.6 seconds).
- Signed webhook → durable history → checkpoint → browser status: 1/1 passed (1.5 minutes).
- Business Intelligence navigation, dataset/history selection, versioned exploration/metrics, persistent dashboard reload, permission denials, and deletion: 1/1 passed (12.1 seconds).

The tests include anonymous, mismatched-user, cross-project, and cross-tenant denials. Data Logs remains separate. Browser artifacts are in `/tmp/madar-data-sources-c3-step5-browser-10708-1372972`.

## 6. Tests executed and outcomes

- Live Chromium port-5173 proxy check: passed; health 200 and source route 401, not 404.
- Direct port-8002 source route check: passed; 401, not 404.
- Proxied/direct backend identity comparison: passed; identical local development identity.
- Non-loopback development target rejection: passed by expected startup refusal with `VITE_DEV_PROXY_TARGET must remain loopback-only`.
- Frontend edge/proxy configuration tests: 10/10 passed.
- Focused Data Sources and authorization tests: 25/25 passed.
- Full frontend suite: 240 files passed; 1,780 tests passed; 1 expected skip; zero failures.
- Frontend lint: passed.
- Frontend build and API/theme/bundle/tenant audits: passed.
- Full disposable browser regression: 5/5 phase tests passed.
- `git diff --check`: passed before report creation and repeated afterward.

One preliminary focused-backend invocation was rejected before test collection because the diagnostic command accidentally supplied identical anon/service placeholder keys. The backend correctly failed closed. The corrected invocation used distinct non-secret placeholders and passed all 25 tests; this was a harness-input error, not an application failure.

## 7. Files changed

Tracked changes for Step 2A:

- `web/frontend/vite.config.js` — fail-closed loopback-only development proxy/origin validation.
- `web/backend/tests/test_frontend_edge_config.py` — regression assertion for the loopback development policy.
- `web/README.md` — explicit host-Vite/Compose-backend startup configuration and native-backend alternative.
- `MADAR_C5_LOCAL_DEVELOPMENT_CONNECTIVITY.md` — this report.

Local operational correction (intentionally ignored by Git):

- `web/frontend/.env.development.local` — changed from production URLs to loopback backend 8002 and frontend origin 5173.

All earlier owner and C3/C4/C5 changes were preserved.

## 8. Remaining limitations

- The owner's ordinary browser intentionally reaches the production schema-146
  Supabase services through the SSH relay. It therefore exposes real production data
  and must not be treated as disposable test infrastructure.
- Candidate Data Sources, webhook, dashboard, and reporting capabilities above schema
  146 remain unavailable in that ordinary session. They must continue to use the
  isolated disposable candidate-schema harness unless a later persistent release is
  separately authorized.
- The ignored `.env.development.local` is machine-specific. For this workstation's
  SSH-backed native API it targets loopback port 8000. The Compose alternative on 8002
  is a different workflow and is not the active API.
- The Vite guard permits only a loopback API target. The native API—not Vite—holds the
  protected production credentials and reaches production through SSH port 18080.

## 9. No persistent or production modification

Read-only production health, Auth, Storage, and schema checks were made through the
already-running SSH tunnel to prove the intended local connection. No production data
was mutated, no production or staging service was restarted, and no persistent database
was migrated. Candidate migrations were applied only inside disposable tmpfs-backed
containers and removed afterward. The active release remains schema 146. No public
webhook, real Google authorization, persistent worker, commit, push, or merge occurred.
Qwen was not invoked, modified, restarted, or integrated.

**Result: PASS — LOCAL API CONNECTIVITY REPAIRED AND OFFLINE/AUTHORIZED BROWSER VERIFIED.**

Stop here for owner review; no next product milestone was started.
