# Production promotion

The promotion used a stable Docker-nginx proxy and two isolated Compose projects.

1. Green candidate was built from exact SHA, validated inactive, and given the initial worker role.
2. Stable ports were atomically switched to green; green was adopted as known-good at schema 81.
3. Verified backup prerequisite passed; migrations 82/83 advanced production to schema 83.
4. Blue creation initially encountered exhausted Docker default address pools. The attempt failed before switch and green stayed available. Deterministic 10.252.x/24 slot networks fixed the host-specific collision.
5. The next blue attempt found a missing deletion-worker health URL during worker readiness. Green workers were restored; traffic stayed green. The controller now supplies the explicit internal URL and bounded readiness diagnostics.
6. The final retry activated all blue workers, passed readiness/version/frontend validation, switched traffic at 16:24:19, observed health for 60 seconds, and recorded success at 16:25:22.

Production checkout was then fast-forwarded from `0eaa9edd...` to the exact running application SHA `ab684468...`; no container was rebuilt or restarted by that Git operation.

## Corrective login promotion

Live browser verification revealed that `ab684468...` had compiled the
frontend's relative `/api` fallback. The correction was committed as
`ea2ae575...`; a production-shaped inactive-slot attempt then exposed a stale
retained-container network reference. That attempt failed before worker or
traffic cutover and blue remained healthy. Commit `4faf63a6...` added mandatory
inactive-service recreation.

The exact `4faf63a67cbcfe884d3cbeeaa2f39ae9f0a37467` artifacts were built with
the canonical frontend API origin, validated on inactive green, and checked
with credential-free login preflight/invalid-payload requests. The controller
then attested blue schema compatibility, activated green workers, switched the
Docker-nginx proxy to green at 19:18:36 UTC, observed the release for 60
seconds, and marked it known-good at 19:19:39 UTC. Production checkout was
fast-forwarded only after successful post-switch validation. No migration or
database change was required.
