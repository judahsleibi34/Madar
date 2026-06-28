# Front-End Fixes

## Executive Summary

This pass fixed the highest-risk front-end items from `README_CODE_REVIEW.md`: report-builder stored HTML is now handled as plain text, duplicated auth/session refresh logic was consolidated behind the shared API client, the Three color-space warning was removed, major route/workspace code paths are lazy-loaded, PageBuilder draft persistence is debounced, aggressive global scroll resets were removed, and clearly unused CSS files were deleted.

`npm run build` passes. `npm run lint` still fails on older project-wide React Compiler and cleanup issues that are outside the safe scope of this pass; the remaining categories are documented below.

## Fixed Issues

### Report Builder Stored HTML/XSS

- Files:
  - `frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/report-builder/InlineEditable.jsx`
  - `frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/report-builder/ReportPageCanvas.jsx`
- Change:
  - Removed stored HTML flow from editable report text.
  - `InlineEditable` now reads `textContent`, renders plain string children, blocks rich HTML paste, and exposes textbox semantics with `aria-label` / `aria-multiline`.
  - Report toolbar updates now use plain text from the selected editable region.
- Why it matters:
  - Existing/imported report values can no longer persist executable HTML through report editable fields.
- Regression test case:
  1. Open the report builder.
  2. Paste `<img src=x onerror=alert(1)><b>Safe text</b>` into a report title/body editable field.
  3. Blur the field, switch away, and return to the report.
  4. Expected: the literal text is saved/displayed as text only, no markup is rendered, no alert runs, and line breaks in multiline fields remain visible.

### Shared API Client

- Files:
  - `frontend/src/utils/apiClient.js`
  - `frontend/src/components/AuthPages/LoginPage.jsx`
  - `frontend/src/components/AuthPages/SignUpPage.jsx`
  - `frontend/src/components/AuthPages/ForgotPasswordPage.jsx`
  - `frontend/src/components/AuthPages/ResetPasswordPage.jsx`
  - `frontend/src/components/MainPages/ContactPage.jsx`
  - `frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/api.js`
- Change:
  - Added shared `API_URL`, `getApiUrl`, `readApiResponse`, `readApiError`, `postAuthJson`, and `postPublicJson`.
  - Auth pages and the contact form now use shared JSON helpers.
  - DataAnalysisWorkspace re-exports shared API behavior instead of maintaining a second refresh/session implementation.
- Why it matters:
  - Reduces inconsistent CSRF/session behavior and avoids future auth bugs caused by duplicate request clients.

### Performance and Bundling

- Files:
  - `frontend/src/App.jsx`
  - `frontend/src/routes/PublicRoutes.jsx`
  - `frontend/src/routes/UserWorkspaceRoutes.jsx`
  - `frontend/src/components/MainPages/HeroSection.jsx`
  - `frontend/src/components/PageBuilder/tabs/DataTab.jsx`
- Change:
  - Added route-level `React.lazy` / `Suspense` for public, admin, tenant-site, and user-workspace route groups.
  - Lazy-loaded PageBuilder, DataAnalysisWorkspace, public pages/auth pages, and the Three-based Orbit visual.
- Result:
  - Build output now emits separate chunks for `PublicRoutes`, `UserWorkspaceRoutes`, `PageBuilder`, `DataAnalysisWorkspace`, and `OrbitVisual`.
  - `OrbitVisual` is still large because Three.js is large, but it no longer sits in the initial route bundle.

### Three.js Warning

- File: `frontend/src/components/MainPages/OrbitVisual.jsx`
- Change:
  - Replaced deprecated/undefined `renderer.outputEncoding = THREE.sRGBEncoding` with `renderer.outputColorSpace = THREE.SRGBColorSpace`.
  - Removed unused Orbit helper functions that also contained mojibake comments.

### PageBuilder Persistence

- Files:
  - `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`
  - `frontend/src/components/PageBuilder/workspace/hooks/useDebouncedProjectStorage.js`
- Change:
  - Added `useDebouncedProjectStorage` to debounce frequent localStorage draft writes.
  - Preview actions and backend-load paths explicitly flush the current project when needed.
- Why it matters:
  - Reduces repeated synchronous localStorage writes while editing large PageBuilder projects.

### Scroll Behavior

- Files:
  - `frontend/src/main.jsx`
  - `frontend/src/components/DashboardBuilder/ScrollToTop.jsx`
  - `frontend/src/components/DashboardBuilder/Dashboard.jsx`
- Change:
  - Removed app-start/load/beforeunload scroll forcing.
  - Removed dashboard-local repeated scroll forcing.
  - `ScrollToTop` now skips browser back/forward navigations and respects hash navigation.
- Why it matters:
  - Preserves expected browser scroll restoration and anchor behavior.

### CSS Cleanup

- Removed:
  - `frontend/src/styles/admin/PricingPage.css` because it was empty and stale.
  - `frontend/src/styles/admin/PageBuilder/data-analysis-workspace.backup.css` because it was an unused backup stylesheet.
- Updated:
  - Removed stale imports from pricing pages.
- Deferred:
  - The `frontend/src/styles/admin/PageBuilder/legacy/` styles appear unreferenced, but they were left in place for a separate audit because they are numerous and may be used as migration references.

## Remaining Front-End Work

- `npm run lint` still fails with 45 errors and 13 warnings after this pass.
- Main remaining categories:
  - React Compiler `set-state-in-effect`, purity, refs, immutability, and preserve-manual-memoization errors in `SettingsPage`, `UserManagementPage`, `DataAnalysisWorkspace`, `BuilderFormPreviewPage`, and `PageBuilder`.
  - Duplicate `average` keys in `frontend/src/components/PageBuilder/DataAnalysisWorkspace/constants/uiText.js`.
  - Unused values in several PageBuilder/DataAnalysisWorkspace modules.
  - Control-character regex lint failures in `SettingsPage.jsx` and `PageBuilder.url.js`.
  - Remaining mojibake in translated Arabic/content files should be fixed from a trusted translation source, not guessed.
  - `npm install` reports 2 audit findings: 1 low and 1 high. Run `npm audit` and choose safe dependency upgrades.

## Verification

- `npm install`: passed; reported 2 audit vulnerabilities.
- `npm run build`: passed.
- `npm run lint`: failed on existing project-wide lint issues listed above.

## Recommended Next Steps

1. Fix duplicate keys and control-character regex lint errors first; they are small and high-signal.
2. Split the React Compiler cleanup into focused passes by module: settings, user management, DataAnalysisWorkspace, form preview, then PageBuilder.
3. Add a real test runner for frontend regression tests, then automate the report-builder XSS case.
4. Run `npm audit` and update the affected dependency with the least disruptive version change.
5. Audit the remaining PageBuilder legacy CSS folder after confirming no dynamic imports or documentation workflows depend on it.
