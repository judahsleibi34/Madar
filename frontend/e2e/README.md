# Madar Frontend E2E Tests

Playwright tests live in `frontend/e2e` and cover public smoke routes,
unauthenticated access control, public tenant-site rendering, and optional
credential-backed login smoke tests.

## Commands

Run from `frontend/`:

```sh
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:ui
npm run test:e2e:debug
```

The Playwright config starts the local Vite dev server when one is not already
running.

## Environment Variables

- `E2E_BASE_URL`: frontend URL. Defaults to `http://127.0.0.1:5173`.
- `E2E_BACKEND_URL`: backend API origin exposed to Vite as `VITE_API_URL`.
  If omitted, Vite uses its local `/api` proxy.
- `E2E_USER_EMAIL`: staging/test user email for authenticated user tests.
- `E2E_USER_PASSWORD`: staging/test user password.
- `E2E_ADMIN_EMAIL`: staging/test admin email for admin tests.
- `E2E_ADMIN_PASSWORD`: staging/test admin password.

Do not use production credentials. Use disposable staging accounts. Tests skip
credential-backed flows when the matching env vars are absent.

## Local Expectations

Stage A tests can run against the Vite frontend without a working backend. The
app treats failed auth bootstrap calls as logged out, so public pages and
unauthenticated redirects remain testable.

Stage B authenticated tests require a running backend, a reachable Supabase
environment, and valid test credentials.

## CI Notes

- The config uses Chromium by default.
- Screenshots and videos are retained on failure.
- Traces are collected on retry.
- CI runs with retries and fewer workers.
- Point `E2E_BACKEND_URL` at a non-production backend.

## Debugging

Use `npm run test:e2e:ui` for interactive investigation or
`npm run test:e2e:debug` to step through a single failing test. HTML reports are
written by Playwright and can be opened after a run with:

```sh
npx playwright show-report
```

## Cleanup

The current E2E suite does not create accounts, submit payments, or rely on email
verification. Any staging accounts used through env vars should be reset or
rotated outside the test runner when needed.
