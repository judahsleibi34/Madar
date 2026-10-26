# Madar C4 Step 2A — Final Accessibility Gate

**Date:** 2026-10-24

**Final decision:** **C4 — PASS, OFFLINE VERIFIED**

This decision closes the local C4 accessibility blocker only. It does not classify C4 as staging-tested, deployed, production-ready, or externally provider-verified.

## 1. Root cause and affected controls

The 444 failing route checks in the Step 2 report were genuine WCAG 1.4.11 non-text-contrast failures in two normal-state controls rendered by `NotificationPermissionPrompt`:

- `button.notification-permission-secondary` (`Not now` / Arabic equivalent);
- `button.notification-permission-close` (`Close notification prompt` / Arabic equivalent).

Both controls used `--theme-border` (`#ddd6ca`) as their only visible boundary against `--theme-surface` (`#fffdfa`). The computed boundary contrast was **1.42:1**, below the required **3:1**. The secondary button's surface fill matched its surrounding surface, and the close button was transparent, so neither had another qualifying visual boundary. There was no overlay, inherited opacity, disabled state, selected state, or unexpected background causing these two findings. Text and icon contrast did not fail.

The prompt is mounted once in the authenticated application shell. It appeared on 37 admin/user route-role checks in every combination of three viewports, two requested theme labels, and two directions: `37 × 3 × 2 × 2 = 444`. Each route check contained both defective controls, producing 888 raw findings.

The source component is `web/frontend/src/notifications/NotificationPermissionPrompt.jsx`; the defect was in `web/frontend/src/styles/admin/dashboard/notification-permission-prompt.css`. The decorative `--theme-border` token itself was not changed because it has many non-control consumers. The two controls now use the existing semantic `--color-border-control` token. Focus outlines now use the existing opaque `--color-focus-indicator` token, including a restored explicit outline on the close control.

## 2. Earlier zero-failure baseline versus the 444-failure run

The earlier 672-check, zero-failure baseline was not proof that these controls were conforming. Its offline mock returned no usable response for `/notifications/push-public-key`, so `NotificationPermissionPrompt` did not render. The later non-mocked run made the prompt visible and exposed the latent CSS defect. The component and stylesheet were tracked and unchanged at that point; this was newly exercised coverage, not a new notification regression and not a false positive.

The audit fixture now returns an enabled test-only push-public-key response, waits for the authenticated prompt to become visible, and records prompt-bearing route checks. No element is skipped, whitelisted, suppressed, or evaluated against a weaker threshold. The final audit observed the prompt in exactly **444** route checks.

During the first corrected full run, four unrelated findings appeared intermittently on `/archive` and `/ecommerce/orders`. The captured computed styles proved that inspection sometimes occurred across a loading transition: a button was already enabled while retaining the prior background and the new text fill. Waiting for network idle and settled animations produced stable, reproducible steady-state inspection. No archive or orders styling was retained as part of this correction.

The repository currently enforces light mode in `src/utils/themeMode.js`; therefore the audit's historical `dark` labels also resolve to the effective light runtime theme. This was true for both the old and final 672-check runs and is now explicitly diagnosed rather than presented as genuine dark-runtime coverage. The notification fix nevertheless uses existing theme tokens; token-level measurements are conforming in both defined palettes. Runtime dark mode is not currently a supported product state.

## 3. Before and after measurements

| Indicator | Before | After | Required |
|---|---:|---:|---:|
| Light control border on surface | 1.42:1 (`#ddd6ca` / `#fffdfa`) | 4.43:1 (`#6f7787` / `#fffdfa`) | 3:1 |
| Dark-token control border on surface | about 1.37:1 | 6.87:1 (`#9ca6b2` / `#181d23`) | 3:1 |
| Light focus indicator on surface | translucent/insufficiently deterministic; close outline removed | 8.69:1 (`#852c21` / `#fffdfa`) | 3:1 |
| Dark-token focus indicator on surface | translucent/insufficiently deterministic | 4.65:1 (`#e5564b` / `#181d23`) | 3:1 |

The enabled/disabled behavior, permission workflow, accessible dialog name/description, localized close name, Arabic direction, responsive stacking, and reduced-motion rule are unchanged.

## 4. Files changed in Step 2A

- `web/frontend/src/styles/admin/dashboard/notification-permission-prompt.css` — semantic control borders and opaque focus indicators.
- `web/frontend/src/notifications/NotificationPermissionPrompt.test.jsx` — focus/Escape restoration and Arabic RTL/localized-name coverage.
- `web/frontend/scripts/check-color-contrast.mjs` — deterministic prompt coverage, prompt-count evidence, richer diagnostics, and steady-state timing.
- `MADAR_C4_FINAL_ACCESSIBILITY_GATE.md` — this report.
- `MADAR_C4_WEBHOOK_END_TO_END_VALIDATION.md` — appended final-status addendum; original FAIL evidence remains intact.

The worktree was already extensively modified by the owner. Those changes were preserved. No Qwen file was edited.

## 5. Fresh Step 2A verification

### Accessibility and frontend

- Notification prompt component: **6/6 passed**.
- Notification/PWA interactive group: **39/39 passed** across 5 files.
- Combined notification and webhook management UI: **22/22 passed**; the webhook panel remains **16/16**.
- Focus behavior: primary action receives initial focus; Escape dismisses; prior focus is restored.
- RTL behavior: Arabic direction and localized close-button accessible name passed.
- Focused browser contrast (`/dashboard`): **24/24 passed**, prompt visible in 24/24 checks.
- Full repository contrast: **672/672 route checks passed**, **0 failed route checks**.
  - 28,296 text inspections;
  - 324 placeholder inspections;
  - 8,122 control inspections;
  - 10,072 icon inspections;
  - 444 authenticated route checks with the notification prompt visibly present.
- Frontend lint: passed.
- Frontend production build and its API-origin, theme, bundle-origin, and tenant-bundle audits: passed. The existing chunk-size advisory remains non-blocking.
- Full frontend suite: **239 files passed; 1,765 tests passed; 1 skipped; 0 failed**. The two new tests explain the increase from 1,763.
- `git diff --check`: passed.

The browser audit exercised compact (390×844), intermediate (768×1024), and wide (1440×900) layouts, English LTR and Arabic RTL, public/admin/user shells, and all original 56 route-role entries across 12 permutations. Route coverage remained 672; it was not reduced.

### Fresh disposable Data Sources/browser integration

The complete disposable harness was rerun after the correction:

- older-schema safe fallback: **1 passed**;
- API onboarding, automatic sync, freshness, and revocation: **1 passed**;
- Google Sheets offline OAuth/mapping/sync/deletion/revocation: **1 passed**;
- signed webhook through durable inbox, worker, immutable history, checkpoint, recovery, fencing, rotation, revocation, and tenant isolation: **1 passed** (1.6m).

Result: **4/4 browser scenarios passed**. Disposable artifacts are under `/tmp/madar-c4-step2a-full-browser`.

No backend, webhook API, authorization, ingestion, migration, or dependency source changed in Step 2A. The earlier hermetic backend result (**3,715 total; 3,032 passed; 683 skipped; 0 failed/errors**) and focused webhook backend result (**17/17 passed**) therefore remain applicable. The complete browser harness additionally re-exercised the real local FastAPI → PostgreSQL/PostgREST → Vault → worker → dataset history → checkpoint → React workflow.

## 6. Remaining limitations

- This is offline evidence only. No persistent staging environment or real external webhook provider was tested.
- Only the test HMAC adapter is registered; no production provider integration is claimed.
- The synthetic notification provider has no outbound reader, so reconciliation remains honestly scheduled rather than fabricated as completed.
- Local Vault used disposable development mode.
- The application runtime currently supports light mode only; dark CSS-token resilience is measured, but a user-visible dark runtime was not activated.
- The mocked repository contrast suite can surface existing caught route-render errors when a generic fixture lacks route-specific product-editor data; this does not suppress contrast findings and did not prevent the notification prompt from being inspected on all 444 expected checks. It should be treated as a future audit-fixture hardening item, not as staging evidence.
- Migrations 161 and 162 remain candidates. Active release selection remains schema 146.

## 7. Operational boundary confirmation

No staging or production infrastructure was contacted or modified. No persistent migration was applied. No release selection changed. No public webhook endpoint or persistent worker was activated. No customer data was used. No commit, push, merge, deployment, or server activation occurred. Qwen, Google Sheets product code, C5 dashboards, and the independent Data Logs workflow were not modified.

## 8. Decision

The previously established webhook E2E evidence remains valid, the complete disposable browser integration was freshly rerun, the full 672-route contrast gate is green with explicit coverage of all 444 prompt-bearing checks, and all required frontend/accessibility regressions pass.

**C4 — PASS, OFFLINE VERIFIED**
