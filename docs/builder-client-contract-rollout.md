# Builder client contract rollout

Builder draft writes carry `X-Madar-Builder-Contract: cloud-draft-v1`. The API rejects any non-empty unsupported value with `builder_client_upgrade_required` before authentication, project lookup, or database mutation.

Missing headers are temporarily accepted while `ENFORCE_BUILDER_CLIENT_CONTRACT=false` (the default). This is a deployment bridge only; it is not the final production policy.

## Safe deployment order

1. Deploy the backend with `cloud-draft-v1` support and enforcement disabled.
2. Deploy the frontend that sends the header on create, update, publish, and unpublish requests.
3. Verify successful current-client writes and confirm legacy project-less routes redirect to the chooser or an explicit project URL.
4. Set `ENFORCE_BUILDER_CLIENT_CONTRACT=true` on the backend and restart only through the normal production deployment process.
5. Verify a missing or obsolete contract receives HTTP 409 with code `builder_client_upgrade_required`, while reads and published public sites remain available.

Do not enable enforcement before the compatible frontend is deployed. Do not leave enforcement disabled after the rollout window, because headerless browser-first clients could otherwise continue writing stale drafts.
