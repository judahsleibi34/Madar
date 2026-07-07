# Setup

## Prerequisites

- Docker and Docker Compose
- Node.js for frontend-only development
- Python for backend-only development

## Environment

Create the root `.env` file with the runtime values used by Docker Compose.
Keep `.env` local; it is ignored by Git.

Required values include:

```sh
FRONTEND_URLS=https://your-frontend-origin.example
VITE_API_URL=https://your-backend-origin.example
COOKIE_SECURE=true
COOKIE_SAMESITE=none
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
TRUSTED_PROXY_IPS=127.0.0.1,::1
MAX_REQUEST_BODY_BYTES=12582912
MAX_JSON_BODY_BYTES=3145728
MAX_SMALL_JSON_BODY_BYTES=262144
MAX_DATA_JSON_BODY_BYTES=1048576
ALLOW_INSECURE_HTTP_URLS=false
ALLOW_REMOTE_DATASET_URLS=false
ALLOW_INSECURE_REMOTE_DATASET_HTTP=false
MAX_EXCEL_FILE_BYTES=10485760
MAX_DATASET_UPLOAD_BYTES=209715200
LARGE_DATASET_THRESHOLD_BYTES=52428800
MAX_FULL_DATAFRAME_BYTES=52428800
CSV_CHUNK_SIZE_ROWS=3000
MAX_PREVIEW_ROWS=120
CSV_DUPLICATE_TRACK_ROWS=100000
MAX_EXCEL_UPLOAD_BYTES=52428800
MAX_EXCEL_UNCOMPRESSED_BYTES=52428800
MAX_EXCEL_ZIP_ENTRIES=200
MAX_EXCEL_SHEETS=20
MAX_EXCEL_ROWS=100000
MAX_EXCEL_COLUMNS=1000
MAX_EXCEL_CELL_CHARS=10000
DATA_WORKSPACE_RATE_LIMIT_LIMIT=60
DATA_WORKSPACE_RATE_LIMIT_WINDOW_SECONDS=300
DATA_UPLOAD_RATE_LIMIT_LIMIT=20
DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS=300
DATA_ANALYSIS_RATE_LIMIT_LIMIT=20
DATA_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS=300
DATA_VISUALIZATION_RATE_LIMIT_LIMIT=60
DATA_VISUALIZATION_RATE_LIMIT_WINDOW_SECONDS=300
DATA_VISUALIZATION_TENANT_RATE_LIMIT_LIMIT=300
DATA_VISUALIZATION_TENANT_RATE_LIMIT_WINDOW_SECONDS=300
DATA_WORKSPACE_RATE_LIMIT_USER_OVERRIDES={"42":{"analysis_assist":{"limit":5,"window_seconds":300}},"tenant:7:user:42":{"*":{"limit":10,"window_seconds":300}}}
AI_FREE_DAILY_MESSAGES=5
AI_FREE_DAILY_CODE_GENERATIONS=1
AI_FREE_MAX_OUTPUT_TOKENS=900
AI_PRO_DAILY_MESSAGES=100
AI_PRO_DAILY_CODE_GENERATIONS=25
AI_PRO_MAX_OUTPUT_TOKENS=1800
PUBLIC_UPLOADS_DIR=uploads
DATA_UPLOAD_DIR=private_uploads
PRIVATE_CHARTS_DIR=private_generated_charts
BUILDER_ASSET_MAX_BYTES=5242880
BUILDER_ASSET_UPLOAD_RATE_LIMIT_LIMIT=30
BUILDER_ASSET_UPLOAD_RATE_LIMIT_WINDOW_SECONDS=300
AVATAR_UPLOAD_RATE_LIMIT_LIMIT=20
AVATAR_UPLOAD_RATE_LIMIT_WINDOW_SECONDS=300
```

`TRUSTED_PROXY_IPS` is a comma-separated list of reverse proxy or tunnel IPs/CIDR
ranges whose `X-Forwarded-For` and `X-Real-IP` headers may be trusted for rate
limits. In production, configure only the real proxy/tunnel peers and block
direct backend access with firewall or proxy rules.

Request body size limits reject oversized JSON and multipart requests before route
processing. Keep `MAX_REQUEST_BODY_BYTES` large enough for the expected largest
upload plus multipart overhead, and keep `MAX_JSON_BODY_BYTES` above the Builder
schema limit. Tune the smaller JSON limits for public/auth/data routes based on
production usage.

Persisted tenant/user URLs are validated before storage. External URLs should use
`https://`; leave `ALLOW_INSECURE_HTTP_URLS=false` in production. Only set it to
`true` for local development fixtures that must reference `http://` resources.

Authenticated data workspace routes are rate limited per action and authenticated
user, with the tenant included when available. Tune `DATA_*_RATE_LIMIT_*` values
for production based on server capacity, dataset size, and expected chart or
analysis usage.

Visualization limits are short-window abuse-protection controls, not product
tier quotas. `DATA_VISUALIZATION_RATE_LIMIT_*` limits a user's chart-generation
burst, and `DATA_VISUALIZATION_TENANT_RATE_LIMIT_*` limits aggregate chart
generation for a tenant in the same short window. Do not configure daily
visualization quotas unless product requirements explicitly add them; normal
users should be able to generate plots freely within reasonable burst limits.

Use `DATA_WORKSPACE_RATE_LIMIT_USER_OVERRIDES` when one user needs a custom
limit. The JSON keys can be the user id, or `tenant:<tenant_id>:user:<user_id>`
for a tenant-specific override. Inside each user entry, use an action name such
as `read`, `upload`, `analysis_assist`, `analysis_run`, `visualization_create`,
or `visualization_profile`; `*` or `default` applies to all workspace actions
for that user. Values can be a number for the request limit or an object with
`limit` and `window_seconds`.

AI chatbot free users get `AI_FREE_DAILY_MESSAGES=5` questions per day by
default. `AI_FREE_MAX_OUTPUT_TOKENS` caps provider output length so free answers
stay focused on statistical calculations instead of long exploratory responses.
AI usage is enforced by `POST /users/{user_id}/analysis/ai` after authentication,
tenant/user dataset scoping, request body limits, and prompt safety preflight.
AI is intentionally different from visualization: AI keeps daily plan quotas and
also goes through the short-window analysis abuse limiter.
Blocked unsafe prompts do not increment usage. Once a request is accepted, the
backend atomically reserves one daily message before calling the planner
provider; provider failures after the attempted call still count. Generated-code
requests reserve one code-generation count before calling the code-generation
provider. Per-user daily counters are stored in `ai_usage_daily`; the free global
pool is checked before reservation and is best-effort under concurrency.

Remote dataset URL imports are disabled by default for SSRF safety. Keep
`ALLOW_REMOTE_DATASET_URLS=false` for the MVP and have users upload CSV/XLS/XLSX
files instead. Only enable remote URL imports in controlled environments after
reviewing the SSRF protections, and keep
`ALLOW_INSECURE_REMOTE_DATASET_HTTP=false` unless a local fixture explicitly
requires `http://`.

Excel uploads are checked before parsing. `.xlsx` workbooks are validated as ZIP
containers without extracting them to disk, with limits for compressed file size,
uncompressed ZIP size, ZIP entry count, sheet count, worksheet dimensions, and
cell text length. `.xls` files cannot be inspected the same way, so keep
`MAX_EXCEL_FILE_BYTES` conservative and prefer `.xlsx` or CSV for untrusted data.

Large data-analysis uploads are accepted up to `MAX_DATASET_UPLOAD_BYTES`, which
defaults to 200 MiB. CSV uploads above `LARGE_DATASET_THRESHOLD_BYTES` default to
`large_dataset` processing: the backend streams the upload to private storage,
then extracts metadata with `pandas.read_csv(..., chunksize=CSV_CHUNK_SIZE_ROWS)`
instead of loading the full file into memory. Preview/read responses return at
most `MAX_PREVIEW_ROWS` rows, row/column counts, inferred dtypes, missing-value
counts, duplicate-count metadata, and CSV parsing assumptions, but never return
private absolute filesystem paths. Full-DataFrame operations such as export,
cleaning, analysis, AI analysis, and visualization are limited by
`MAX_FULL_DATAFRAME_BYTES` until a chunked implementation exists for that
workflow. Duplicate counting tracks up to `CSV_DUPLICATE_TRACK_ROWS` row
signatures; if that cap is reached, the response marks duplicate counting as a
partial hash sample instead of exact.

Excel workbooks are not processed in chunked mode. Files above
`MAX_EXCEL_UPLOAD_BYTES` are rejected with guidance to convert the workbook to
CSV, because parsing Excel requires workbook-level loading and validation.

Builder and website image assets are uploaded through the backend and served from
managed `/uploads/...` paths. `BUILDER_ASSET_MAX_BYTES` defaults to 5 MiB and
only PNG, JPEG, and WebP files are accepted. Tune
`BUILDER_ASSET_UPLOAD_RATE_LIMIT_*` based on expected editor usage.
Profile avatar uploads use the same image type and size validation pattern and
are protected by `AVATAR_UPLOAD_RATE_LIMIT_*`.

Spreadsheet-compatible exports sanitize formula-like text values at export time
only. Backend CSV exports and browser-side CSV/XLSX downloads prefix string
cells whose first content character is `=`, `+`, `-`, `@`, tab, or carriage
return with a single quote so users opening files in spreadsheet programs are
protected without changing stored data.

Uploads are split into public and private roots. `PUBLIC_UPLOADS_DIR` is exposed
only through managed `/uploads/tenant_{id}/builder_assets/...` routes and should
contain only intentionally public assets, such as builder images. `DATA_UPLOAD_DIR` stores private data-analysis CSV/XLS/XLSX
uploads and dataset exports; it defaults to `private_uploads` and must not be
served through FastAPI `StaticFiles`, Nginx, a CDN, or any other public static
file mount. The backend rejects startup when `DATA_UPLOAD_DIR` is the same as,
or nested under, the public uploads directory.

Generated charts from user datasets are private by default. `PRIVATE_CHARTS_DIR`
stores chart images and optional explorer HTML under tenant/user-scoped
subdirectories; it defaults to `private_generated_charts` and must not be served
through FastAPI `StaticFiles`, Nginx, a CDN, or any public static file mount.
Charts are returned through authenticated
`/users/{user_id}/visualization/charts/{chart_id}` requests after tenant/user
scope checks. Explorer HTML is treated as private dataset-derived output and is
served as an attachment with `Content-Security-Policy`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and
`X-Frame-Options: DENY` headers. The backend rejects startup when
`PRIVATE_CHARTS_DIR` is the same as, or nested under, the public uploads
directory.

## Full Stack

```sh
docker compose up -d --build
```

The backend runs from `backend/` and installs Python dependencies from
`backend/requirements.txt`. The frontend runs from `frontend/` and installs
dependencies from `frontend/package.json` and `frontend/package-lock.json`.

## Backend Only

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Frontend Only

```sh
cd frontend
npm install
npm run dev
```
