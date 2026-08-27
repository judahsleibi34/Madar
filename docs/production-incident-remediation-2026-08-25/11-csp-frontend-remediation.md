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

## Cloudflare edge evidence

After the corrective promotion, the origin HTML remained 3,860 bytes with zero
executable inline scripts and no Cloudflare Insights source. The Chrome-like
public edge response was 5,157 bytes and contained one Cloudflare-marked inline
block plus a `static.cloudflareinsights.com` script reference. These elements
appear only after Cloudflare serves the response. Madar's CSP correctly remains
`script-src 'self'` and blocks them.

No third-party script origin was whitelisted. If Browser Insights/Web Analytics
is not operationally required, the preferred resolution is for an authorized
Cloudflare operator to disable that injection. If it is required, its exact
minimal CSP changes require separate operator approval; this remediation does
not weaken CSP merely to silence the console.
