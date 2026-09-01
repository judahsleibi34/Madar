# Application-wide color contrast audit

Date: 2026-09-01

## Outcome

The application chrome passes the rendered contrast matrix with no detected failures.

- 540 route/theme/direction/viewport combinations
- 16,564 rendered text checks
- 282 placeholder checks
- 2,528 interactive-control checks
- 0 failed route checks
- 0 route page errors

The matrix covers light and dark themes, English/LTR and Arabic/RTL, and compact (390 px), intermediate (768 px), and wide (1440 px) viewports.

## Approved palette

| Role | Light | Dark |
| --- | --- | --- |
| Page background | `#f4f0e8` | `#101317` |
| Primary surface | `#fffdfa` | `#181d23` |
| Raised surface | `#f8f4ed` | `#232a32` |
| Primary text | `#162033` | `#f4f6f8` |
| Secondary/muted text | `#465066` | `#c8ced6` / `#9ca6b2` |
| Brand/action red | `#852c21` | `#c94730` |
| Control boundary | `#6f7787` | `#9ca6b2` |

Red is reserved for primary actions, current selections, focus, and deliberate heading accents. Ordinary headings, labels, descriptions, and inactive navigation use neutral text colors.

## Semantic mapping

- `--color-text`, `--color-text-soft`, and `--color-text-muted`: body, supporting, and metadata text.
- `--color-accent-text`: inline accents that must remain readable in the current theme.
- `--color-heading-accent`: the single colored portion of a two-tone heading.
- `--color-border`: decorative card and section separation.
- `--color-border-control`: inputs, selects, textareas, secondary buttons, segmented controls, and editor tools.
- `--color-focus-indicator`: keyboard focus outlines.
- `--color-disabled-*`: readable disabled surfaces, text, and boundaries without opacity fading.
- `--color-status-*-text`: semantic success, warning, and error messaging.

## Corrected failure patterns

| Previous combination | Problem | Correction |
| --- | --- | --- |
| `#6f7787` muted text on light page/surface | 3.96-4.43:1 for normal text | Mapped normal muted copy to the stronger secondary text role. |
| `#852c21` red on dark page/surface | 1.92-2.11:1 | Split accent text from heading/action red; normal dark-theme accent text is neutral and readable. |
| `#ddd6ca` or translucent white borders on adjacent surfaces | About 1.3-1.7:1 | Added a dedicated 3:1 control-boundary role per theme. |
| Disabled controls faded with component opacity | Text and boundaries became indistinct | Replaced opacity fading with explicit disabled surface/text/border roles. |
| Nested sidebar labels on the solid current-page red | 2.99:1 in dark mode | Current-page descendants now inherit inverse text. |
| Restricted-access white text over a white-starting gradient | About 1.08:1 | Changed the action gradient to brand-red stops and restored a theme surface behind the card. |
| Page Builder controls reusing decorative editor borders | About 1.1-1.4:1 | Migrated editor chrome controls to the semantic control boundary while excluding authored canvas/runtime output. |

## Shared components corrected

- Global inputs, selects, textareas, placeholders, focus rings, and disabled states
- Primary, secondary, danger, icon, segmented, and current-page buttons
- Public header/footer links and authentication controls
- Dashboard sidebar, mobile menu, nested active labels, and workspace collapse control
- Settings notifications, account/security controls, ecommerce controls, calendar switches, and weekly activity switches
- Page Builder navigation, inspector controls, page actions, zoom tools, and Data Analysis controls

Decorative cards and section dividers retain the subtle border token; stronger boundaries are limited to interactive controls.

## Route coverage

Public: `/`, `/demo`, `/pricing`, `/pricing/base-plans`, `/pricing/custom-plan`, `/team`, `/about`, `/contact`, `/privacy-policy`, `/terms-and-conditions`, `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/verify-email`.

Admin: `/dashboard`, `/admin/users`, `/admin/account-access`, `/notifications`, `/page-builder`, `/builder-responses`, `/builder-data`, `/archive`, `/my-plan`, `/settings/security`, `/settings`.

User: `/dashboard`, `/page-builder`, `/builder-responses`, `/builder-data`, `/calendar`, `/agenda`, `/archive`, `/ecommerce/tags`, `/ecommerce/categories`, `/ecommerce/products`, `/ecommerce/theme`, `/ecommerce/cv-rerank`, `/ecommerce/store`, `/my-plan`, `/notifications`, `/settings/change-password`, `/settings/security`, `/settings`, `/admin/users`.

## Intentional exception

Customer-authored website and form output inside `.builder-canvas`, `.builder-form-preview-page`, and `.tenant-site-runtime` is excluded from the application-chrome contract. Its colors are selected by the site/form author and must be validated against that authored theme. The surrounding builder and dashboard UI is included.

## Verification commands

```text
npm run contrast:audit
npm run theme:audit
npm run build
```
