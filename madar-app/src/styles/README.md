# Madar CSS chunked structure

Use `styles/index.css` as the only CSS import in your app.

## Import in React/Vite

```js
import "./styles/index.css";
```

## Structure

- `core/tokens.css` — brand colors, gradients, shadows.
- `core/base.css` — resets, fonts, root/body defaults.
- `shared/buttons.css` — shared gradient/outline button system.
- `layout/header.css` — desktop/mobile header, nav, language switcher.
- `layout/footer.css` — footer layout.
- `sections/home.css` — hero, orbit visual, about section.
- `pages/contact.css` — contact page and form.
- `pages/auth.css` — register, login, forgot password, shared form status.
- `pages/pricing.css` — pricing cards.
- `pages/team.css` — team cards and profile links.
- `admin/dashboard.css` — dashboard/sidebar/admin styles.
- `utils/rtl.css` — global RTL direction/layout fixes.
- `utils/responsive.css` — global responsive rules from the original public site CSS.

## Review notes

1. The original file had duplicate base resets; they are consolidated in `core/base.css`.
2. The original file had two Team Page sections; both are kept in `pages/team.css` in cascade order for compatibility.
3. Shared colors/buttons are centralized so future changes happen in one place.
4. After visual QA, remove the older duplicate Team block if the newer one fully replaces it.
