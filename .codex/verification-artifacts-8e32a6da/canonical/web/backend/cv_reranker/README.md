# Authenticated CV Semantic Reranker

A private FastAPI service that accepts a role profile and PDF, DOCX, or UTF-8 TXT CVs, then ranks each CV with a CPU cross-encoder. The API and worker are separate processes. PostgreSQL is both the system of record and the durable queue.

## Architecture and data flow

```text
client -> FastAPI (auth, validation, private downloads) -> PostgreSQL 16
                                                        -> protected file storage
PostgreSQL durable queue -> CPU worker -> extraction -> token chunks
                                      -> whole-job reranking batches -> results
```

The API never imports or loads the model. `app.workers.ranking_worker` constructs one reranker at process startup, records the worker in PostgreSQL, and reuses that model for every claimed job. Normal tests inject a deterministic fake reranker and never contact Hugging Face.

## Security

- Argon2id password hashing and short-lived signed access JWTs with issuer, audience, type, expiry, issued-at, subject, and JTI checks.
- Opaque refresh tokens stored only as SHA-256 hashes. Each refresh rotates the token; reuse revokes the family.
- Every private query includes the authenticated user ID. Foreign IDs and missing IDs return the same 404.
- Streamed uploads have file and batch limits, sanitized names, extension and signature checks, encrypted-PDF rejection, and atomic owner-scoped storage.
- Originals and parsed text are available only through authenticated endpoints. Never expose the storage directory through a web server.
- Structured logs contain identifiers and stage metadata, never role profiles, CV text, passwords, or tokens.
- Database-backed rate limits work across replicas.

Registration hashes passwords with Argon2id. Login issues a short-lived access JWT and an opaque refresh token. JWT decoding requires the configured algorithm, issuer, audience, subject, token type, issued-at, expiry, and JTI. Refresh rotates the opaque token under a row lock; only its SHA-256 hash is stored, and reuse revokes the complete token family. Logout revokes the supplied session. Inactive or soft-deleted users cannot log in or use an existing access/refresh token.

Every job/document query is scoped by both resource ID and authenticated `user_id`. Parsed text, matching excerpts, result data, cancellation, deletion, and original downloads are reachable only through an owned job. Missing and foreign-owned UUIDs produce the same `404 RESOURCE_NOT_FOUND` response.

## Docker

`docker compose config` works without an `.env` and uses loopback-only development defaults. For any persistent or shared environment, create `.env` from `.env.example` and replace `POSTGRES_PASSWORD`, both database URL passwords, and `JWT_SECRET_KEY` together. Then run:

```powershell
docker compose up --build
```

The API listens on `http://localhost:8080`. The migration service completes before the API and worker start. The first worker start downloads `cross-encoder/ms-marco-MiniLM-L6-v2` into the persistent model cache. ONNX is attempted first, with PyTorch fallback.
PostgreSQL is also bound to `127.0.0.1:${POSTGRES_PORT:-54329}` for host-side migrations and integration tests; do not expose that port publicly.

For production, terminate TLS at a trusted proxy, configure explicit `ALLOWED_ORIGINS`, enable secure refresh cookies when cookie transport is used, mount `/data` on encrypted persistent storage, and inject secrets using the platform secret manager.

## Local development

Python 3.11+ and PostgreSQL 16+ are required outside tests.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,model]"
Copy-Item .env.example .env
# For host-side processes, change database host `postgres` to `127.0.0.1:54329`.
.venv\Scripts\alembic upgrade head
.venv\Scripts\uvicorn app.main:app --reload --port 8080
```

Run the worker separately:

```powershell
.venv\Scripts\python -m app.workers.ranking_worker
```

Set `RERANK_BACKEND=pytorch` to bypass ONNX. Tune inference batch size, thread counts, and worker count against actual CPU and memory limits.

To populate the local production-model cache before starting a worker:

```powershell
.venv\Scripts\python -c "from app.core.config import get_settings; from app.services.ranking.reranker import SentenceTransformerReranker; r = SentenceTransformerReranker(get_settings()); print(r.model_id, r.backend)"
```

This command intentionally downloads model artifacts. Do not run it in normal tests.

## Configuration

Settings are loaded from environment variables or `.env`. The main groups are:

- Database: `DATABASE_URL`, `WORKER_DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `DB_POOL_RECYCLE_SECONDS`.
- Authentication: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, access/refresh lifetimes, password length, and cookie/CSRF settings.
- Private storage: `UPLOAD_DIRECTORY`, `TEMP_DIRECTORY`, `MODEL_CACHE_DIRECTORY`, per-file/count/batch limits, and baseline/CV character limits.
- Ranking: `RERANK_MODEL_ID`, `RERANK_MODEL_VERSION`, `RERANK_BACKEND`, `RERANK_BATCH_SIZE`, `TOP_CHUNKS_FOR_SCORE`, `MATCHING_EXCERPT_COUNT`, chunk size/overlap, and baseline token limit.
- Queue/retention: polling, heartbeat, stale timeout, max attempts, active/stored job limits, retention, cleanup batch size, and cache retention.
- CPU: `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, and `TORCH_NUM_THREADS=2` are conservative defaults. `MAX_CONCURRENT_JOBS=1` documents the intended one-job-per-worker default; scale by running additional worker processes only after measuring memory.
- HTTP controls: explicit `ALLOWED_ORIGINS` and database-backed registration/login/refresh/job rate limits.

`APP_ENV=production` rejects a default/short JWT secret, wildcard/empty CORS, insecure refresh cookies, non-PostgreSQL URLs, and missing/unwritable storage directories.

## API

All routes use `/api/v1`.

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /ranking-jobs` with multipart `baseline` and repeated `files`
- `GET /ranking-jobs`
- `GET /ranking-jobs/{job_id}`
- `GET /ranking-jobs/{job_id}/documents`
- `GET /ranking-jobs/{job_id}/documents/{document_id}/parsed`
- `GET /ranking-jobs/{job_id}/documents/{document_id}/original`
- `POST /ranking-jobs/{job_id}/cancel`
- `DELETE /ranking-jobs/{job_id}`
- `GET /health/live`
- `GET /health/ready`

Example job:

```bash
curl -X POST http://localhost:8080/api/v1/ranking-jobs \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "baseline=Senior Python engineer with FastAPI and PostgreSQL" \
  -F "files=@candidate-one.pdf" \
  -F "files=@candidate-two.docx"
```

Scores are raw cross-encoder relevance values, not percentages or calibrated probabilities. A CV score is the mean of its top K chunk scores.
Originals are stored under random internal owner-scoped keys outside public directories and streamed with the sanitized submitted filename. Parsed records retain raw and normalized text, hashes, extractor/normalizer versions, page count, warnings, metadata, and truncation state.

## Queue and caches

Workers claim queued rows with `FOR UPDATE SKIP LOCKED`, commit immediately, and run model work outside the claim transaction. After every CV is extracted/chunked, all uncached `(baseline, one CV chunk)` pairs are flattened across the job and sent in bounded CPU batches. Candidates are never concatenated. Pair metadata maps every raw score back to its exact document and chunk. Top-K averaging, excerpt selection, filename/UUID tie-breaking, and final ranking are deterministic.

Workers heartbeat between steps/batches. Stale processing jobs are requeued up to `JOB_MAX_ATTEMPTS` and then failed; stale cancellation requests are finalized as cancelled. Retry progress is reset as derived state and persistent cache upserts make reprocessing idempotent. Cancellation is checked between documents, before chunking, between inference batches, and before result attachment.

Original upload deduplication, extraction, normalized content, token chunks, ranking results, and chunk scores are persistent user-scoped caches. SHA-256 identities include extractor/normalizer versions, tokenizer model/version and chunk settings, baseline/CV content, model/backend/version, Top-K, excerpt count, and ranking implementation version as applicable. PostgreSQL unique constraints plus `INSERT ... ON CONFLICT` protect concurrent content, chunk, result, score, and upload writes. Changing a baseline reuses extraction/chunks; changing a model invalidates model-dependent cache entries.

Deleting a job removes its private relationships/results and immediately removes unreferenced content/files; a shared original remains until the final referencing job is deleted. Retention cleanup removes expired sessions/jobs and old unreferenced caches. Schedule it with:

```powershell
.venv\Scripts\python scripts\cleanup.py
```

## Verification

```powershell
.venv\Scripts\ruff format --check .
.venv\Scripts\ruff check .
.venv\Scripts\mypy app scripts
.venv\Scripts\pytest -q
docker compose config
```

The default offline run uses SQLite and skips tests marked `postgres`; it never downloads model weights. Run the complete suite against the Compose PostgreSQL 16 instance with:

```powershell
docker compose up -d postgres
$env:WORKER_DATABASE_URL='postgresql+psycopg://cv_ranker:local-development-password@127.0.0.1:54329/cv_ranker'
$env:DATABASE_URL='postgresql+asyncpg://cv_ranker:local-development-password@127.0.0.1:54329/cv_ranker'
.venv\Scripts\alembic upgrade head
$env:POSTGRES_TEST_URL=$env:WORKER_DATABASE_URL
.venv\Scripts\pytest -q
```

The PostgreSQL tests exercise real two-worker claims, `SKIP LOCKED`, rollback, concurrent identical uploads, concurrent cache-stack upserts, retry idempotence, stale recovery, cancellation during inference, the API, and ownership/IDOR behavior.

To verify the reversible migration cycle on a disposable database:

```powershell
.venv\Scripts\alembic upgrade head
.venv\Scripts\alembic upgrade head
.venv\Scripts\alembic downgrade base
.venv\Scripts\alembic upgrade head
.venv\Scripts\alembic check
```

## Model and privacy

Review the model card and license for `cross-encoder/ms-marco-MiniLM-L6-v2` before redistribution. Validate ranking quality, language coverage, bias, and employment-law requirements with representative data. This service assists human review and must not be the sole basis for employment decisions. Configure retention, deletion, encryption, access logging, and backups appropriate for CV personal data.

OCR, malware scanning, antivirus/CDR, and macro execution are not provided. Uploaded code is never executed, but production deployments should add a trusted scanning/quarantine layer. Scanned/image-only PDFs produce a per-file extraction error (or page warning) because OCR is intentionally out of scope. TLS termination, secret rotation, encrypted volumes/backups, audit retention, and regional privacy/employment compliance remain deployment responsibilities.
