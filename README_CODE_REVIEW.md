# Full Code Review

## Executive Summary

The project has a solid foundation: FastAPI routes are separated by domain, Supabase access is mostly wrapped behind service modules, CSRF/cookie auth is present, request body limits exist, rate limiting is implemented, and the backend has a meaningful test suite around security and builder behavior. The frontend has a broad React/Vite implementation with reusable content modules, routing separation, and a sophisticated PageBuilder/Data Analysis workspace.

The biggest risks are security and maintainability: service-role Supabase access relies heavily on app-side tenant filters, the report builder renders stored HTML with `dangerouslySetInnerHTML`, frontend API/auth logic is duplicated across multiple clients, and the PageBuilder workspace is a very large component with mixed persistence, routing, rendering, and editing logic. There are also deployment issues around dependency pinning, bundle size, and dev/prod path consistency.

## Critical Issues

### 1. Stored HTML Can Be Re-Injected Into Editable Report Content

- **File path:** `frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/report-builder/InlineEditable.jsx:43`, `:44`, `:52`, `:53`; `frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/report-builder/ReportPageCanvas.jsx:79`, `:126`
- **Function/component/module:** `InlineEditable`, report title/block editing
- **Issue:** Editable report text is saved and restored as `innerHTML`, then rendered with `dangerouslySetInnerHTML`. Paste is coerced to plain text, but existing stored values, imported values, or programmatic updates can still contain HTML.
- **Why it matters:** This is a stored XSS risk if a malicious payload reaches report content. It can execute in a trusted authenticated workspace.
- **Severity:** Critical
- **Suggested fix:** Store plain text, not HTML. Use `textContent` on blur and render children normally. If rich text is required, sanitize with a strict allowlist library before storage and before render.
- **Implementation notes:**

```jsx
onBlur={(event) => onChange(event.currentTarget.textContent || "", event.currentTarget.dir)}
// render:
<div {...commonProps}>{value}</div>
```

### 2. Service-Role Database Access Depends On Every Route Remembering Tenant Filters

- **File path:** `backend/database.py:37`; example routes in `backend/routes/builder_routes.py:186`, `:325`, `:425`, `:493`, `:539`, `:575`; `backend/routes/public_site_routes.py:50`, `:255`, `:389`
- **Function/component/module:** `service_supabase` usage across backend routes
- **Issue:** The backend uses the Supabase service role client broadly. This bypasses RLS, so tenant isolation depends on every query adding correct `.eq("tenant_id", ...)` and related checks.
- **Why it matters:** One missed filter becomes a cross-tenant data exposure or write bug. The current code often does this correctly, but the pattern is fragile as the app grows.
- **Severity:** Critical
- **Suggested fix:** Centralize tenant-scoped query helpers/repositories that require a `TenantContext` and apply tenant filters internally. Add route tests for every service-role route proving cross-tenant IDs are rejected. Where possible, use RPCs with `SECURITY DEFINER` and explicit tenant checks rather than raw service-role table access.

### 3. Local AI Generated-Code Execution Has No Hard Timeout

- **File path:** `backend/data_analysis/ai/sandbox.py:88`; `backend/data_analysis/ai/settings.py:108`
- **Function/component/module:** `run_generated_code_locally`, `is_local_ai_exec_allowed`
- **Issue:** The local sandbox uses in-process `exec`; the comment notes it cannot enforce a hard timeout safely. In non-production, local execution defaults to enabled.
- **Why it matters:** A bad or adversarial generated snippet can consume CPU/memory and hang a worker. Environment mistakes can accidentally enable this in deployed environments.
- **Severity:** Critical
- **Suggested fix:** Keep `AI_ALLOW_LOCAL_EXEC=false` in all shared environments. Execute generated code only in an isolated worker/container with CPU, memory, wall-time, network, and filesystem limits. Add a startup guard that refuses production if local exec is enabled.

## High Priority Issues

### 4. Pagination Uses Inclusive Supabase Ranges Incorrectly

- **File path:** `backend/routes/builder_routes.py:330`, `:504`; `backend/services/admin_user_service.py:53`
- **Function/component/module:** `list_builder_projects`, `list_builder_form_submissions`, `list_users_with_features`
- **Issue:** Supabase `.range(from, to)` is inclusive. The code requests `offset + limit`, which fetches `limit + 1` rows intentionally for `has_more`, but then slices in Python. This works as a sentinel pattern, but it is inconsistent and undocumented; pagination metadata can confuse maintainers and increases row transfer.
- **Why it matters:** It risks off-by-one regressions and fetches extra rows on every paginated request.
- **Severity:** High
- **Suggested fix:** Make the sentinel explicit:

```python
end = offset + limit  # inclusive sentinel row
rows = query.range(offset, end).execute().data or []
items = rows[:limit]
has_more = len(rows) > limit
```

If no sentinel is needed, use `offset + limit - 1`.

### 5. Avatar Upload Reads Entire File Into Memory

- **File path:** `backend/routes/user_routes.py:258`
- **Function/component/module:** `upload_user_avatar`
- **Issue:** The route calls `await file.read()` without a size cap before checking `len(content)`.
- **Why it matters:** The request body middleware limits total request size, but this handler still buffers the entire upload in memory. Multiple concurrent uploads can pressure memory.
- **Severity:** High
- **Suggested fix:** Mirror the builder upload pattern (`await file.read(AVATAR_MAX_BYTES + 1)`) or stream chunks with a byte counter.

### 6. Rate Limiter Fails Open By Default

- **File path:** `backend/services/rate_limit_service.py:25`, `:109`, `:292`; `docker-compose.yml`
- **Function/component/module:** `RATE_LIMIT_FAIL_OPEN`, Redis fallback
- **Issue:** `RATE_LIMIT_FAIL_OPEN` defaults to true, falling back to in-memory limits when Redis is unavailable.
- **Why it matters:** In multi-worker/container deployments, in-memory fallback is per-process and can be bypassed. Attackers can hit auth, public contact, form submission, and data endpoints harder than expected during Redis outages.
- **Severity:** High
- **Suggested fix:** Default `RATE_LIMIT_FAIL_OPEN=false` in production. Keep fail-open only for local development and test environments.

### 7. Public Static Mounts Can Expose Generated Files Indefinitely

- **File path:** `backend/app.py:42`, `:46`
- **Function/component/module:** `/generated_charts`, `/uploads`
- **Issue:** Generated charts and uploads are mounted as static directories with no authentication, expiry, cleanup, or object-level authorization.
- **Why it matters:** Uploaded builder assets may be intended to be public, but generated charts and user data-derived visualizations may contain sensitive data. Files can remain accessible after a user deletes a project or dataset.
- **Severity:** High
- **Suggested fix:** Separate public builder assets from private/generated analytical artifacts. Serve private files via signed short-lived URLs or authenticated routes. Add cleanup jobs and avoid exposing filesystem paths in API responses.

### 8. Duplicate Frontend API Clients Have Different CSRF/Auth Behavior

- **File path:** `frontend/src/utils/apiClient.js:55`, `:93`; `frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/api.js:41`, `:60`, `:72`; direct fetches in `frontend/src/components/AuthPages/LoginPage.jsx:75`, `SignUpPage.jsx:204`, `ResetPasswordPage.jsx:44`, `ForgotPasswordPage.jsx:47`, `MainPages/ContactPage.jsx:26`
- **Function/component/module:** `apiFetch`, `authFetch`, direct auth/public fetch calls
- **Issue:** The app has one robust API client and a second data-analysis client with separate refresh logic, plus several raw `fetch` calls.
- **Why it matters:** CSRF token sync, session refresh serialization, error handling, and credentials handling can drift. Auth bugs tend to be intermittent and hard to reproduce.
- **Severity:** High
- **Suggested fix:** Route all authenticated calls through `apiFetch`. Keep a small wrapper for public unauthenticated endpoints if needed. Remove duplicate refresh logic in DataAnalysisWorkspace.

### 9. Vite Build Warns About Undefined Three.js API

- **File path:** `frontend/src/components/MainPages/OrbitVisual.jsx:306`
- **Function/component/module:** `OrbitVisual`
- **Issue:** The build warns that `THREE.sRGBEncoding` is undefined in the installed `three` version.
- **Why it matters:** Color management may be broken now and can become a runtime failure later.
- **Severity:** High
- **Suggested fix:** Use current Three.js API:

```js
renderer.outputColorSpace = THREE.SRGBColorSpace;
```

### 10. Frontend Bundle Is Large

- **File path:** `frontend/package.json`; `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`
- **Function/component/module:** Vite bundle, PageBuilder/Data Analysis dependencies
- **Issue:** Production build reports a JS chunk around 1.6 MB minified. Heavy features such as Three.js, PageBuilder, Data Analysis, and report builder are likely bundled together.
- **Why it matters:** Slower first load, especially on mobile or weaker networks. Public marketing pages should not pay the cost for authenticated builder workspaces.
- **Severity:** High
- **Suggested fix:** Lazy-load dashboard/workspace routes with `React.lazy`; split Three.js hero; code-split PageBuilder/DataAnalysisWorkspace; consider route-level prefetch after login.

## Medium Priority Issues

### 11. PageBuilder Workspace Is Too Large And Mixes Responsibilities

- **File path:** `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`
- **Function/component/module:** `PageBuilder`
- **Issue:** The component is roughly 2,981 lines and contains routing, persistence, backend loading, drag/drop, rendering, tabs, forms, quiz logic, uploads, publishing, previews, and modal state.
- **Why it matters:** It is difficult to review safely, test, optimize, or change without regressions.
- **Severity:** Medium
- **Suggested fix:** Extract hooks by concern: `useBuilderProjectPersistence`, `useBuilderRouting`, `useBuilderSelection`, `useBuilderDrag`, `useBuilderPublishing`, `useRuntimeForms`. Move render blocks into focused components.

### 12. Backend And Supabase Migration Trees Are Duplicated

- **File path:** `database/migrations/*`; `supabase/migrations/*`
- **Function/component/module:** Migration management
- **Issue:** The same migration set appears in two folders, including duplicate numbering (`023`, `024`).
- **Why it matters:** Drift between directories or duplicate numbering can break fresh database setup and deployment automation.
- **Severity:** Medium
- **Suggested fix:** Choose one source of truth. If both are required, add a CI check that compares file hashes and validates migration order.

### 13. Root `.env` Exists In The Workspace

- **File path:** `.env`
- **Function/component/module:** Environment configuration
- **Issue:** A root `.env` file is present in the working tree. It is ignored by Git, but it is easy to leak through archives, screenshots, or manual deployment bundles.
- **Why it matters:** This project depends on Supabase service keys and AI provider keys; accidental disclosure is high impact.
- **Severity:** Medium
- **Suggested fix:** Keep only `.env.example` in the repo. Rotate any secrets that may have been shared. Add secret scanning in CI.

### 14. Contact And Auth Forms Use Direct Fetch Instead Of Shared Error/Auth Handling

- **File path:** `frontend/src/components/MainPages/ContactPage.jsx:26`; `frontend/src/components/AuthPages/LoginPage.jsx:75`; `SignUpPage.jsx:204`; `ResetPasswordPage.jsx:44`; `ForgotPasswordPage.jsx:47`
- **Function/component/module:** Auth/public form components
- **Issue:** Direct fetch calls duplicate API URL logic and error parsing.
- **Why it matters:** Inconsistent UX and auth behavior; easier to forget credentials, CSRF, or response parsing when new forms are added.
- **Severity:** Medium
- **Suggested fix:** Create `postPublicJson`, `postAuthJson`, and `readApiError` helpers based on `apiFetch` conventions.

### 15. Forced Scroll Reset Is Global And Aggressive

- **File path:** `frontend/src/main.jsx:8`, `:24`, `:35`-`:41`
- **Function/component/module:** app bootstrap scroll handling
- **Issue:** The app forces scroll top on load, beforeunload, and multiple timers.
- **Why it matters:** It breaks expected browser scroll restoration and can hurt accessibility, deep links, and back-button UX.
- **Severity:** Medium
- **Suggested fix:** Use route-scoped scroll restoration via `ScrollToTop` only where desired. Preserve hash navigation and browser back restoration.

### 16. Public Site API Returns Entire Published Schema

- **File path:** `backend/routes/public_site_routes.py:311`
- **Function/component/module:** `get_public_site`
- **Issue:** The public route returns full `published_schema`.
- **Why it matters:** Published schema may contain internal IDs, hidden forms, workflow metadata, or draft-ish data accidentally copied into published data.
- **Severity:** Medium
- **Suggested fix:** Add a schema serializer that returns only runtime-safe fields needed by `TenantSiteRuntime`.

### 17. Admin Deletion Depends On Supabase Auth Cascades

- **File path:** `backend/services/admin_user_service.py:188`-`:200`
- **Function/component/module:** `delete_user_account`
- **Issue:** If `auth.admin.delete_user` succeeds but DB cascades do not fully remove local rows, the code does not explicitly verify cleanup before deleting the tenant.
- **Why it matters:** Partial deletions can leave orphaned membership, feature, website, audit, or project rows.
- **Severity:** Medium
- **Suggested fix:** Wrap deletion in explicit ordered cleanup or RPC transaction; verify affected local rows; add tests for partial failure behavior.

### 18. Request Body Limits Do Not Cover New Non-Legacy Data Routes By Regex

- **File path:** `backend/services/request_body_limits.py:35`-`:42`, `:104`-`:112`
- **Function/component/module:** `RequestBodyLimitMiddleware`
- **Issue:** Some regexes target `/users/{id}/...` routes, while newer builder routes also exist as `/builder/...`; this is handled for builder, but future new canonical routes can easily miss specialized limits.
- **Why it matters:** Routes may silently fall back to broader limits.
- **Severity:** Medium
- **Suggested fix:** Add tests for every route category and centralize route size classification by APIRouter prefix constants.

### 19. Backend Tests Depend On Running From `backend/`

- **File path:** `backend/tests/*`; imports such as `from routes import ...`, `from services import ...`
- **Function/component/module:** backend test harness
- **Issue:** `python -m pytest --collect-only` from the repository root fails with `ModuleNotFoundError` for `routes`, `services`, `data_analysis`, and `app`. Running from `backend/` with the backend venv collects 230 tests successfully.
- **Why it matters:** CI or new developers running tests from the repo root will see a broken suite even though the tests are present.
- **Severity:** Medium
- **Suggested fix:** Add `backend/pytest.ini` or root `pyproject.toml` with `pythonpath = backend`, or convert imports to package-qualified imports. Document the exact test command until fixed.

## Low Priority Issues

### 20. README Is Still The Default Vite Template

- **File path:** `README.md`
- **Function/component/module:** project documentation
- **Issue:** The root README describes the Vite template rather than this application.
- **Why it matters:** New contributors lack setup, architecture, environment, and test instructions.
- **Severity:** Low
- **Suggested fix:** Replace with project-specific setup and link `docs/setup.md`, `docs/development.md`, and this review.

### 21. Mixed Encoding/Mojibake In UI Text

- **File path:** examples in `frontend/src/content/pages/myPlanContent.js`; `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`
- **Function/component/module:** Arabic/localized strings
- **Issue:** Some Arabic text appears mojibaked in source output, and some symbols render as corrupted sequences.
- **Why it matters:** Localization quality and trust are affected, and it can indicate editor/encoding drift.
- **Severity:** Low
- **Suggested fix:** Ensure files are UTF-8, run a script checking for mojibake patterns, and move all UI copy to i18n JSON/content modules.

### 22. CSS Organization Has Legacy And Duplicate Styling

- **File path:** `frontend/src/styles/admin/PageBuilder/legacy/*`; `frontend/src/styles/admin/PageBuilder/data-analysis-workspace.backup.css`; `frontend/src/styles/admin/PricingPage.css`; `frontend/src/styles/public pages/pricing.css`
- **Function/component/module:** stylesheets
- **Issue:** Legacy, backup, admin, and public pricing styles coexist.
- **Why it matters:** Increases CSS cascade risk and makes visual changes harder to reason about.
- **Severity:** Low
- **Suggested fix:** Remove unused backup/legacy files after confirming imports; document active style entry points.

## Front-End Review

Strengths:

- Route separation exists for public, admin, user workspace, and tenant site surfaces.
- `apiFetch` has useful CSRF handling, cookie credentials, 401 refresh, and serialized session calls.
- Content modules and i18n files keep much UI copy outside components.
- The PageBuilder has significant validation and preview logic, including overlap warnings and URL validation before backend save.

Findings:

- **Security:** `InlineEditable` stores/renders HTML and should be changed to plain text or sanitized rich text.
- **State management:** `PageBuilder.jsx` is too broad. Extract hooks and smaller components before adding more features.
- **Persistence:** The builder writes the entire project to `localStorage` on every project change (`PageBuilder.jsx:337`). This can block the main thread for large projects and can conflict with backend state.
- **API usage:** Multiple direct `fetch` calls bypass the shared client and duplicate error behavior.
- **Performance:** Public routes likely load heavy authenticated-workspace code because the app does not use route-level lazy imports.
- **Accessibility:** The global scroll reset can harm keyboard and back-button users. ContentEditable controls need clear labels and sanitized text handling.
- **Responsiveness:** The PageBuilder uses a mobile blocker rather than a responsive authoring experience. This may be acceptable for complex editing, but should be explicit product behavior.

## Back-End Review

Strengths:

- Auth cookies are `HttpOnly`; CSRF token is bound to session fingerprint.
- Request body limits are implemented at ASGI middleware level.
- Public form submissions validate field IDs, required fields, answer counts, string lengths, and JSON size.
- Data uploads are scoped by tenant/user directories and local file reads are constrained to scoped uploads.
- Backend tests cover many security boundaries and route hardening paths.

Findings:

- **Authorization:** Good checks exist, but broad `service_supabase` usage makes tenant filtering an ongoing footgun.
- **API design:** Several routes have both canonical and legacy `/users/{user_id}/...` paths. This helps compatibility but increases test matrix size.
- **Database access:** Pagination should be standardized and documented.
- **Validation:** Avatar upload should stream/limit reads before buffering. Contact and auth payloads could use stronger field constraints in Pydantic models.
- **Error handling:** Many routes return generic errors, which is good for security, but structured error codes would improve frontend handling.
- **Logging:** Logging is present and avoids obvious secret logging; add request IDs/correlation IDs for production tracing.
- **Scalability:** Rate limiting and dataframe cache are process-local fallbacks; multi-worker deployments need Redis and shared storage decisions.

## Performance Bottlenecks

- **Large frontend bundle:** Build reports a ~1.6 MB JS asset. Use route-level lazy imports and split PageBuilder/Data Analysis/Three.js.
- **Main-thread localStorage writes:** Full builder project serialization on every state change can block typing/dragging. Debounce and persist only dirty slices.
- **Repeated dataframe reads:** Data analysis creates new `DataCleaning` readers for multiple operations; shared cache helps, but operations still copy dataframes. Consider dataset IDs and server-side prepared dataset sessions.
- **Static generated charts:** Chart files accumulate and are served from disk. Add cleanup and object storage lifecycle policies.
- **Admin list feature loading:** `list_users_with_features` does a second query for tenants in the current page, which is acceptable now; monitor as features grow or switch to a DB view/RPC.

## Security Review

- Fix stored HTML/XSS in report builder first.
- Reduce service-role blast radius by centralizing tenant-scoped repositories and adding cross-tenant tests for every route.
- Keep `RATE_LIMIT_FAIL_OPEN=false` in production.
- Keep `AI_ALLOW_LOCAL_EXEC=false` outside isolated local development.
- Do not expose generated/private analysis files as public static files.
- Rotate any secrets that may have been in `.env` if shared outside the machine.
- Keep remote dataset URLs disabled by default; current SSRF protections are good when enabled, including private IP blocking and redirect validation.
- Add dependency/security scanning for Python and npm packages.

## Testing Gaps

- No frontend test framework is configured in `frontend/package.json`.
- Add React Testing Library tests for auth routing, language/theme toggles, pricing cards, settings save flows, and PageBuilder tab routing.
- Add Playwright E2E smoke tests for signup/login/logout, dashboard access, builder save/publish, public site rendering, public form submission, and admin user management.
- Add backend tests for production env guards: `RATE_LIMIT_FAIL_OPEN=false`, `AI_ALLOW_LOCAL_EXEC=false`, secure cookies, and allowed origins.
- Fix backend test collection from the repository root, or document that tests must be run from `backend/`.
- Add regression tests for `InlineEditable` ensuring HTML input is stored/rendered safely.
- Add migration validation tests comparing `database/migrations` and `supabase/migrations`.
- Add route tests for static/private generated chart access once access rules are redesigned.

## Recommended Enhancements

- Introduce a single frontend API layer with typed endpoint wrappers.
- Convert the most critical frontend modules to TypeScript or add runtime schema validation for API responses.
- Add route-level code splitting with `React.lazy`.
- Create backend repository/service classes for tenant-scoped tables.
- Add correlation IDs and structured logs.
- Add CI steps: backend tests, frontend lint, frontend build, migration drift check, dependency audit.
- Replace root README with real setup/deployment docs.
- Create `.env.example` and document required production values.

## Prioritized Action Plan

1. Fix `InlineEditable` stored HTML/XSS by storing plain text or sanitized allowlisted rich text.
2. Set production guards for `RATE_LIMIT_FAIL_OPEN=false` and `AI_ALLOW_LOCAL_EXEC=false`.
3. Restrict generated chart/data artifacts behind authenticated or signed access.
4. Centralize tenant-scoped service-role queries and add cross-tenant tests.
5. Consolidate frontend API clients and remove duplicate refresh logic/direct fetches.
6. Fix Three.js color API warning in `OrbitVisual`.
7. Code-split public, dashboard, PageBuilder, Data Analysis, and Three.js routes.
8. Stream avatar uploads with a max read size.
9. Standardize Supabase pagination helper and update route/service usage.
10. Fix backend test discovery from the repository root.
11. Add frontend unit and E2E tests.
12. Extract PageBuilder concerns into hooks/components.
13. Resolve migration directory duplication and add a drift check.
14. Replace default README with project-specific setup, environment, test, and deployment instructions.

## Quick Wins

- Replace `THREE.sRGBEncoding` with `THREE.SRGBColorSpace`.
- Change avatar upload to `await file.read(AVATAR_MAX_BYTES + 1)`.
- Remove always-on/duplicate API clients in new code and route all authenticated requests through `apiFetch`.
- Add `.env.example` and update README.
- Add `npm run build` and backend test commands to CI.
- Add `pythonpath = backend` to pytest config so root-level collection works.
- Delete unused backup CSS once imports are verified.

## Larger Refactors To Plan

- PageBuilder decomposition into focused hooks and feature modules.
- Tenant-scoped repository layer around Supabase service-role access.
- Signed/private file service for uploads and generated analysis artifacts.
- Route-level frontend code splitting and performance budget.
- Full frontend test suite with Playwright smoke coverage.
