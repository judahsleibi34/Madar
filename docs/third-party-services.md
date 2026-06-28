# Third-party services, cookies, and scripts

This inventory reflects the current app-side implementation in this repository.

## First-party cookies

- `madar_access_token`: first-party authentication cookie set by the backend. It is configured as `HttpOnly` and uses the app cookie security settings.
- `madar_refresh_token`: first-party authentication refresh cookie set by the backend. It is configured as `HttpOnly` and uses the app cookie security settings.
- `madar_csrf_token`: first-party CSRF token cookie used by the frontend API client for unsafe requests.

## Third-party services

- Supabase is used by the backend for authentication and application data storage.
- Instagram is linked from the public footer as an external social profile.
- External Unsplash image URLs may appear in page-builder starter/template content until a workspace replaces them with its own content.

## Scripts and SDKs

- The public frontend currently loads the Vite-built application bundle from `frontend/index.html`.
- No analytics SDK is currently integrated in the frontend.
- No payment SDK is currently integrated in the frontend.
- No Stripe, PayPal, Google Analytics, or tag manager script is currently listed as a frontend dependency or script include.

## Payment data

- Current billing routes save plan/checkout selections and support a backend webhook secret, but payment provider checkout is not configured in this repository.
- The app should continue to avoid storing raw card data. Any future payment integration should use a PCI-compliant hosted checkout/provider flow.
