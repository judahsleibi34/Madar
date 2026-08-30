# Madar release-safety instructions

Before changing deployment, migrations, schema compatibility, Docker/Compose,
production runtime code, release-sensitive backend/frontend code, or opening a
PR targeting `main`, read [`docs/production-release-policy.md`](docs/production-release-policy.md).

The current implementation is authoritative. If deployment-gating code or
compatibility metadata changes, update the policy in the same change. Run every
applicable release-policy check before declaring work ready, and report gates
that cannot be tested locally.

Never bypass a failed release gate or directly modify production to compensate
for a source-code rejection.
