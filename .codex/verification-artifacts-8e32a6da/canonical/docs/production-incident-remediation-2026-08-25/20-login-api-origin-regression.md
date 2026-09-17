# Login API-origin regression

## Observation

A live browser POST to `https://madarportal.com/api/auth/login` returned an HTML
405 response. The client then attempted JSON parsing and reported the leading
HTML token as invalid JSON.

## Confirmed root cause

The frontend source uses `import.meta.env.VITE_API_URL || "/api"`. Production's
protected environment correctly defined the canonical API origin, but the
immutable release builder did not pass `VITE_API_URL` as a Docker build
argument. Docker does not implicitly forward the host environment into a
declared build argument, so Vite compiled `/api` into the released browser
bundle. The backend auth router is `/auth`; there is no `/api/auth` prefix.

Before correction:

- compiled base: relative `/api`;
- browser login target: `https://madarportal.com/api/auth/login`;
- response: frontend-origin HTML, HTTP 405.

After correction:

- compiled base: `https://api.madarportal.com`;
- browser login target: `https://api.madarportal.com/auth/login`;
- preflight: HTTP 200 with exact-origin credentialed CORS;
- controlled empty POST: HTTP 422 JSON from the backend.

No real user password was submitted during verification.

## Remediation

- Production Docker builds now require the exact canonical API origin and fail
  before Vite runs if it is missing or wrong.
- The release controller passes the build argument explicitly and labels the
  image with the intended origin.
- Staging and production frontend artifacts use distinct immutable tags so an
  artifact built for one target cannot be reused for the other.
- Bundle auditing requires the canonical origin and rejects known unapproved
  third-party script origins.
- Candidate deep validation fetches the running Vite JavaScript and refuses
  promotion unless the expected target API origin is physically embedded.
- Non-JSON API errors now produce a controlled generic error without parsing or
  surfacing returned HTML.
- Critical post-switch gates now include the login API origin, API preflight,
  controlled invalid login response, and public bundle inspection.

## Promotion evidence

The corrected release `4faf63a67cbcfe884d3cbeeaa2f39ae9f0a37467`
validated on inactive green, switched at 19:18:36 UTC, completed its observation
window at 19:19:39 UTC, and is the durable known-good release. Blue
`ab6844683d89f652e10edc0bc7fefd22791db75f` is retained for rollback.

## Cloudflare CSP evidence

The Madar origin has zero executable inline scripts and no Cloudflare analytics
source. A Chrome-like public response contains an edge-added Cloudflare inline
block and `static.cloudflareinsights.com` source. Madar's unchanged
`script-src 'self'` policy blocks these. No `unsafe-inline`, jsDelivr, or
third-party script allowance was added. An authorized Cloudflare operator
should disable optional Browser Insights/Web Analytics injection unless it is
explicitly required; otherwise any minimal CSP change requires approval.
