# Configuration inventory and documentation validation

No values in this inventory are secrets. The production `.env` has 29 explicit keys and Compose supplies many safe defaults. Source reads roughly 175 environment names across runtime, tests and compatibility aliases.

## Required production configuration

| Keys | Class | Notes |
| --- | --- | --- |
| `APP_ENV` | Required, production-only | Compose forces `production`; readiness validates it |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` | Required, secret except URL | Present through Compose/env; runtime foundation |
| `FRONTEND_URL`, `FRONTEND_URLS`, `PUBLIC_API_URL`, `FRONTEND_PRIMARY_URL`, `VITE_API_URL` | Required public URL | Exact prod URLs configured |
| `COOKIE_SECURE`, `COOKIE_SAMESITE`, CSRF secret/origins | Required security; secret where named | Secure enabled; missing CSRF secret falls back to other application secret and should be made explicit |
| `REDIS_URL`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_FAIL_OPEN`, `TRUSTED_PROXY_IPS` | Required security | Production effective defaults are enabled/fail-closed/loopback |
| `CALENDAR_CREDENTIALS_SECRET` | Required secret when calendar enabled | Present |
| Google/Microsoft calendar client ID/secret | Provider-specific secret | Google present; Microsoft not present |
| VAPID public/private/subject | Required secret/public pair when push enabled | Present and push has delivered |
| SMTP host/port/user/password/from/TLS | Required when email enabled | Missing; real dead deliveries |
| `RESERVATION_TOKEN_SECRET`, verification/session/admin-access secrets | Required security secrets | Source accepts fallbacks; make explicit and independently rotated in production |
| `METRICS_TOKEN` | Required if metrics exposed | Metrics hides on absent/wrong token; effective status not externally tested |
| `BACKUP_FRESHNESS_REQUIRED`, marker, max age | Required for production operations | Effective check disabled |

## Bounded defaults / optional tuning

| Group | Keys/classification |
| --- | --- |
| Request/upload | `MAX_REQUEST_BODY_BYTES`, `MAX_BUILDER_ASSET_REQUEST_BODY_BYTES`, JSON limits, builder image/video/document limits, dataset/CSV/Excel/archive/parser/result limits — optional tunables with bounded defaults; production-effective limits documented in report 08 |
| Rate limits | auth, password, public, contact, form, data workspace/upload/analysis/visualization, avatar and builder-upload limit/window keys — optional tunables, security-relevant |
| Workers | worker enabled/required/health URL/host/port/poll/batch/concurrency/timeout/result keys — production-only tunables; required flags should be explicit |
| Storage paths | public/private/chart/avatar/workspace/bucket/disk-floor keys — production-only paths with Compose overrides; legacy aliases `UPLOADS_DIR`/`GENERATED_CHARTS_DIR` are deprecated compatibility |
| Analytics/data | row/cell/cache/chunk/preview/full-frame/remote size keys — optional bounded tuning |
| Catalog/cache | ecommerce and calendar workspace cache TTL/max keys — optional bounded tuning |
| Logging/readiness | `LOG_LEVEL`, `STRUCTURED_LOGS`, readiness timeout/cache, third-party log level — optional operations |

## Disabled, development-only and roadmap

- `COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS`, `POSTGRES_TEST_URL`, `MADAR_TEST_REPOSITORY_ROOT`, placeholder Supabase keys: test-only.
- `DEV`, `PROD`, `ENV`, `ENVIRONMENT`, `FASTAPI_ENV`: legacy/unknown aliases; consolidate on `APP_ENV`.
- `PYGWALKER_TELEMETRY_ENABLED`: privacy hardening; set false in tests, production effective state not explicitly documented.
- `AI_PROVIDER`, model/provider keys, `AI_ALLOW_LOCAL_EXEC`, `AI_ISOLATED_WORKER_ENABLED`: feature-specific; production execution disabled and no provider key present.
- Google Drive/OCR configuration: not implemented/roadmap.
- `PASSWORD_RESET_LEGACY_LINKS_ALLOWED_UNTIL`, legacy upload/path keys: deprecated compatibility; remove after an explicit expiry inventory.

Production `.env` uses dotenv colon syntax for several Supabase keys and equals syntax elsewhere; Compose accepts it, but generic shell sourcing fails. Operational documentation must warn operators to use Compose dotenv parsing rather than `source .env`.

Development `VITE_API_URL` and allowed origins are loopback, but `FRONTEND_URL` points to production. This can generate production-facing links during dev flows and should be corrected. Development and production key sets differ substantially because Compose defaults hide requiredness; provide a checked `.env.example` schema with type, requiredness, secret flag, environment and owner.

## Documentation claims

| Claim | Classification | Current evidence |
| --- | --- | --- |
| Public publication hardening is atomic/tenant-bound | Verified current | Code, migration 072, live uniqueness/mismatch checks |
| CORS remains outermost and errors receive CORS | Verified current | `app.py` plus external 404 probes |
| Runtime direct PostgreSQL URL is removed | Verified current | Compose override and running environment-name inspection |
| Parser/remote ingestion isolation exists | Verified current | Compose, healthy workers, tests |
| Notification worker/preferences/VAPID are ready | Partially verified | worker/push/preferences exist; SMTP dead and health masks it |
| Redis uses tmpfs | Incorrect for live runtime | tracked Compose says tmpfs; live mount is anonymous volume |
| Restore drill proves full Madar recovery | Incorrect if interpreted broadly | partial public-schema/files only; docs themselves acknowledge platform limitation |
| Auto-deploy health rollback is safe | Outdated/incorrect | real rollback failed 2026-08-23 |
| Entitlements fail closed | Incorrect | compatibility grants nearly all capabilities |
| Backup program is production-ready | Outdated/planned | valid local backup, no schedule/off-host/freshness gate |
| OCR/Drive/advanced chatbot are available | Not implemented/roadmap | catalog future entries and absent runtime |

Older readiness documents combine Madar with other systems and contain planned target-state language. Operators should use this Node-1/Madar-only report and archive/supersede stale launch claims.
