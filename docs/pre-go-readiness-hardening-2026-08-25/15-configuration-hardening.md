# Configuration hardening

## Inventory

The complete observed runtime inventory contains 199 classified keys and zero unknown keys:

| Class | Count |
| --- | ---: |
| Required | 10 |
| Secret | 19 |
| Production-only | 23 |
| Development-only | 5 |
| Optional | 135 |
| Deprecated | 7 |

Values are never emitted by the inventory or validation errors. Optional roadmap providers are not made mandatory.

## Startup enforcement

Production-like startup rejects unsafe CORS/public URL combinations, absent required authentication/database configuration, permissive rate-limit failure policy, missing sensitive-credential encryption requirements, malformed release identity, and inconsistent worker/provider configuration.

The final staging configuration verifies strict origins, fail-closed rate limiting, loopback HTTP only under `APP_ENV=staging`, exact release SHA, slot-local Redis, disabled telemetry/external AI, isolated remote ingestion, and reviewed calendar encryption/worker state.

Configuration documentation is generated from the typed catalog, and deprecated keys are identified so they cannot silently become a second source of truth.
