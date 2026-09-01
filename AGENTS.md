# Madar release-safety instructions

Before changing deployment, migrations, schema compatibility, Docker/Compose,
production runtime code, release-sensitive backend/frontend code, or opening a
PR targeting `main`, read [`docs/production-release-policy.md`](docs/production-release-policy.md).
Before changing automatic migration orchestration, also read
[`docs/automated-database-migration-architecture.md`](docs/automated-database-migration-architecture.md).
Before changing privileged control-plane installation or upgrade orchestration,
also read
[`docs/control-plane-upgrade-architecture.md`](docs/control-plane-upgrade-architecture.md).

The current implementation is authoritative. If deployment-gating code,
automatic migration orchestration, or compatibility metadata changes, update
the applicable policy and architecture documents in the same change. Run every
applicable release-policy check before declaring work ready, and report gates
that cannot be tested locally.

Never bypass a failed release gate or directly modify production to compensate
for a source-code rejection.
