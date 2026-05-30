# Madar CSS Structure

Use `src/styles/index.css` as the single CSS entrypoint for the app.

## Main React/Vite import

In `src/main.jsx` or `src/main.tsx`, keep only:

```js
import "./styles/index.css";
```

Avoid importing individual CSS files directly inside React components unless there is a very specific reason.

---

## Current structure

```txt
src/styles/
  index.css

  core/
    tokens.css
    base.css

  public layout/
    header.css
    footer.css

  public pages/
    auth.css
    contact.css
    features.css
    home.css
    pricing.css
    subscription-modal.css
    team.css

  shared/
    buttons.css
    gradient-text.css
    split-text.css

  utils/
    rtl.css
    responsive.css

  admin/
    MyPlanPage.css

    dashboard/
      index.css
      shell.css
      layout.css
      sidebar.css
      overview-cards.css
      panels.css
      settings.css
      skeleton.css
      page-builder-dashboard.css
      auth-admin.css
      change-password.css
      responsive.css

    PageBuilder/
      index.css
      app.css
      canvas.css
      forms.css
      data-pages.css
      pages-panel.css
      modals.css
      tenant-runtime.css
      responsive.css
      legacy/
```

---

## Root import order

`src/styles/index.css` should import files in this order:

```css
@import "./core/tokens.css";
@import "./core/base.css";

@import "./public layout/header.css";
@import "./public pages/home.css";
@import "./public pages/contact.css";
@import "./public pages/features.css";
@import "./public layout/footer.css";

@import "./utils/rtl.css";
@import "./utils/responsive.css";

@import "./public pages/auth.css";
@import "./public pages/pricing.css";
@import "./public pages/team.css";
@import "./public pages/subscription-modal.css";

@import "./shared/buttons.css";
@import "./shared/gradient-text.css";
@import "./shared/split-text.css";

@import "./admin/dashboard/index.css";
@import "./admin/MyPlanPage.css";
@import "./admin/PageBuilder/index.css";
```

---

## Folders

### `core/`

Global foundation files.

- `tokens.css` — shared colors, gradients, shadows, CSS variables.
- `base.css` — reset rules, fonts, root/body defaults.

### `public layout/`

Public site layout files.

- `header.css` — desktop header, responsive hamburger, mobile menu, language switcher.
- `footer.css` — public footer.

### `public pages/`

Public marketing/auth pages.

- `home.css` — homepage sections.
- `contact.css` — contact page and form.
- `features.css` — product/features page.
- `auth.css` — login, signup, forgot password, auth states.
- `pricing.css` — pricing cards and plan UI.
- `team.css` — team page.
- `subscription-modal.css` — subscription status modal.

### `shared/`

Reusable UI helpers.

- `buttons.css` — shared button system.
- `gradient-text.css` — reusable gradient text.
- `split-text.css` — split text animation/effects.

### `utils/`

Global helper files.

- `rtl.css` — global RTL layout fixes.
- `responsive.css` — global responsive rules.

---

## Admin dashboard

Dashboard styles are now chunked under:

```txt
src/styles/admin/dashboard/
```

Use only:

```css
@import "./admin/dashboard/index.css";
```

Do not import the old file:

```css
@import "./admin/dashboard.css";
```

### Dashboard chunks

- `shell.css` — app shell/root layout.
- `layout.css` — dashboard page layout and header.
- `sidebar.css` — admin sidebar, user block, logout, language button.
- `overview-cards.css` — dashboard stat cards.
- `panels.css` — dashboard panels, charts, metrics, uptime.
- `settings.css` — settings/profile page.
- `skeleton.css` — loading skeleton UI.
- `page-builder-dashboard.css` — PageBuilder route inside dashboard.
- `auth-admin.css` — admin/auth states.
- `change-password.css` — change password page.
- `responsive.css` — dashboard responsive rules.

---

## PageBuilder

PageBuilder styles are now chunked under:

```txt
src/styles/admin/PageBuilder/
```

Use only:

```css
@import "./admin/PageBuilder/index.css";
```

Do not import the old file:

```css
@import "./admin/PageBuilder/PageBuilder.css";
```

### PageBuilder chunks

- `app.css` — PageBuilder shell, topbar, side panels, general workspace UI.
- `canvas.css` — rendered site canvas, built header/footer, site sections/elements.
- `forms.css` — form builder, runtime forms, quiz UI.
- `data-pages.css` — responses, analytics, data pages.
- `pages-panel.css` — main/branch page actions and page panel controls.
- `modals.css` — delete modal, go-live modal fixes, subdomain modal.
- `tenant-runtime.css` — tenant runtime page/login fallback styles.
- `responsive.css` — PageBuilder responsive rules. Keep this imported last.

### Legacy folder

`PageBuilder/legacy/` contains old backup CSS chunks. Do not import from it.

Only delete `legacy/` after full QA confirms:

- PageBuilder editor works.
- Tenant runtime works.
- Forms/quiz pages work.
- Delete and subdomain modals work.
- Responsive preview modes work.

---

## Cleanup rules

1. Keep `styles/index.css` as the single source of CSS imports.
2. Avoid direct CSS imports inside components unless absolutely necessary.
3. Keep responsive files last inside their local `index.css`.
4. Do not delete legacy files until search confirms they are not imported.
5. After renaming or moving CSS, search the project for old paths before deleting files.

Useful terminal checks:

```powershell
Select-String -Path "src\**\*.*" -Pattern "PageBuilder\.css","admin/dashboard\.css" -CaseSensitive:$false
```

```powershell
Select-String -Path "src\**\*.*" -Pattern "admin/PageBuilder/index\.css","admin/dashboard/index\.css" -CaseSensitive:$false
```