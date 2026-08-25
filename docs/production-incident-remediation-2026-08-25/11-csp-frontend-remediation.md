# CSP/frontend remediation

The two executable inline theme scripts were removed from `web/frontend/index.html`. Equivalent early bootstrap behavior is served from same-origin `/theme-bootstrap.js`; it sets the root theme before the application module and applies the matching body class as soon as the body exists.

Validation:

- source and production build contain zero executable inline scripts;
- production CSP retains `script-src 'self'`;
- `'unsafe-inline'` was not added to `script-src`;
- jsDelivr is absent and not whitelisted;
- the local i18next asset is present and referenced under `/assets/`;
- `/theme-bootstrap.js` returns HTTP 200;
- `mobile-web-app-capable=yes` accompanies the retained Apple metadata;
- frontend unit, lint, and production build gates pass.

No UI layout, style, branding, or visual design changed. Browser-extension/injected jsDelivr requests are not Madar dependencies and were not accommodated by weakening policy.
