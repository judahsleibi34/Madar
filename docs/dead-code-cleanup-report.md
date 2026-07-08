# Dead Code Cleanup Report

Date: 2026-07-08

Scope: conservative unused-code and unused-file inventory for frontend routes/imports, backend router/import wiring, package scripts, old chart output behavior, upload/static-file behavior, archive visualization backups, replaced helper shims, components/hooks/utils, CSS/assets, and stale tests.

## Deleted

| Candidate | Evidence unused | Risk | Action |
| --- | --- | --- | --- |
| `backend/data_analysis/visualization/archive/visualization_backup.py` | `rg` found no imports or dynamic references outside documentation. Active chart code imports `data_analysis.visualization.visualization.DataVisualization` through `backend/data_analysis/services.py`; routers include `visualization_routes.py`, not the archive module. The archive file contained historical `CHART_OUTPUT_DIR` defaults to public-looking `generated_charts`. | Low for runtime deletion; high if left as reusable sample. | Deleted. This removes unsafe obsolete chart-output behavior from importable backend code. |
| `backend/data_analysis/visualization/archive/__init___backup.py` | `rg` found no references to `__init___backup`. The filename is a typo backup, not a Python package initializer, and only re-exported active visualization code. | Low. | Deleted. |
| `frontend/src/styles/admin/dashboard/AdminAccountAccessPage.jsx` | `frontend/src/routes/AdminRoutes.jsx` lazy-loads `../components/DashboardBuilder/AdminAccountAccessPage`. `rg` found no references to the JSX file under `styles/`. Its implementation was an older stub and did not include the live API-backed account-access flow. | Low. | Deleted. |
| `tmp_visual_qa.mjs` | Tracked root-level temporary QA script. `rg` found no package scripts, docs, or imports referencing it. | Low. | Deleted. |
| `routing-search-results.txt` | Tracked root-level generated search output. `rg` found no references from code, scripts, or docs. | Low. | Deleted. |
| `frontend-route-sync.txt` | Tracked root-level generated route-sync notes. `rg` found no references from code, scripts, or docs. | Low. | Deleted. |

## Kept

| Candidate | Evidence / rationale | Risk | Action |
| --- | --- | --- | --- |
| `database/migrations/**`, `supabase/migrations/**` | Migration files are duplicated across two trees but explicitly protected by cleanup rules. | High. | Kept. |
| `backend/tests/test_*security*`, `backend/tests/test_authorization_*`, privacy/rate-limit/upload/chart tests | Security, auth, tenant isolation, private file access, upload privacy, AI limits, spreadsheet sanitization, and rate-limit coverage is active and explicitly protected. | High. | Kept. |
| Setup and production docs under `docs/` | Setup, production launch, backup/restore, authorization, and readiness docs are explicitly protected. | Medium. | Kept. |
| `backend/data_analysis/{analysis_i18n,analysis_catalog,analysis_router,finance_analysis,forms_analysis,meal_analysis,ngo_meal_analysis,data_reading,data_cleaning,assisted_analysis}.py` | These are compatibility shims. Tests and existing imports still reference them directly, while active services use newer package paths. Removing them would break public import paths. | Medium. | Kept. |
| `backend/data_analysis/visualization/*.py` active mixin modules | Active `DataVisualization` composes these mixins, and `backend/data_analysis/services.py` imports the active class. | High. | Kept. |
| `backend/app.py` `/uploads/tenant_{tenant_id}/builder_assets/{filename}` route | This is intentional managed public builder-asset serving with filename and path validation. Tests cover private upload and generated-chart privacy. | High. | Kept. |
| `frontend/public/madar-push-sw.js`, `robots.txt`, `sitemap.xml`, favicon/header SVGs | Public assets can be loaded by browser conventions, Vite public paths, or deployment tooling. | Medium. | Kept. |
| `frontend/src/i18n/locales/**` and content modules | Locale/content modules are imported through i18n/content aggregation and route components; dynamic language usage makes deletion risky. | Medium. | Kept. |
| `frontend/src/assets/MadarTemplates/**` | Some assets are imported directly (`madar_header.svg` in `Header.jsx` and `Footer.jsx`); design/source assets may be brand originals. | Medium. | Kept. |
| `frontend/src/styles/admin/PageBuilder/legacy/**` | Appears unreferenced by CSS imports, but prior review notes identify it as migration/reference material. Large legacy style removal is outside this small pass. | Medium. | Kept. |
| `docs/archive/backup-pagebuilder-root-file/PageBuilder.root.wrong.jsx` | Already quarantined under docs archive. Not imported by runtime code. | Low. | Kept. |

## Needs Manual Review

| Candidate | Evidence / rationale | Risk | Action |
| --- | --- | --- | --- |
| `frontend/playwright-report/index.html` | Tracked generated Playwright report. It is not runtime code and has no code references, but the requested e2e command may regenerate it. | Low. | Needs manual review; kept in this pass to avoid validation churn. |
| `frontend/src/assets/MadarTemplates/Old content/**` and `frontend/src/assets/MadarTemplates/New folder/**` | `rg` found no active imports for these specific folders, but they appear to be brand/source design assets. | Medium. | Needs manual review; kept. |
| `frontend/src/styles/admin/PageBuilder/legacy/**` | Prior frontend report says these are likely unreferenced but intentionally left for a separate audit. | Medium. | Needs manual review; kept. |
| `backend/data_analysis/domains/hr_analysis.py` | Used by `AnalysisRouter`; not directly covered by the legacy top-level shim tests seen in this pass. | Low. | Needs test-awareness review only; kept. |
| Root review notes `README_CODE_REVIEW.md` and `README_FRONTEND_FIXES.md` | Not setup/production docs, but they document previous audits and known cleanup candidates. | Low. | Needs manual review; kept. |
| `docs/builder-backend-roadmap.md` legacy `generated_charts` note | A final scan found an old roadmap statement that chart generation writes to `generated_charts`. Current production/setup docs and code use private chart storage. | Low. | Needs manual review; kept because docs cleanup beyond the report was intentionally minimal. |

## Validation Results

Backend:

- `python -m pytest` from `backend/`: could not run with the system Python because `pytest` is not installed for `C:\Python313`.
- `.\\madar_back\\Scripts\\python.exe -m pytest` from `backend/`: passed, 386 tests.
- `python -m compileall app.py services data_analysis` from `backend/`: passed.

Frontend:

- `npm run lint`: PowerShell did not have `npm` on PATH. Re-run with `C:\Users\Admin\anaconda3` added to PATH: passed.
- `npm run build`: passed with existing Vite chunk-size/plugin-timing warnings.
- `npm run test -- dataframeExport`: passed, 1 file and 11 tests.
- `npm run test:e2e -- --reporter=list --workers=1`: passed, 17 tests and 2 skipped.

## Remaining Cleanup Opportunities

- Audit tracked generated artifacts such as `frontend/playwright-report/index.html`.
- Do a dedicated brand/source asset review for unused files under `frontend/src/assets/MadarTemplates/**`.
- Do a separate PageBuilder legacy CSS audit with visual regression checks before deleting `frontend/src/styles/admin/PageBuilder/legacy/**`.
- Review non-production roadmap notes for stale historical chart-storage wording.
- Consider documenting whether duplicate migration trees are intentional, but do not remove migrations in this cleanup pass.
