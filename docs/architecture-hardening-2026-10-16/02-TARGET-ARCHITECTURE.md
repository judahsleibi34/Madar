# Target and decisions

Retain the existing modular FastAPI monolith and React public/portal entries. Keep PostgreSQL as authority, Redis for disposable rate limiting/cache, and existing durable PostgreSQL queues. Preserve Supabase-compatible Auth/MFA/REST/Storage until actual native replacements pass compatibility and recovery drills. Use dedicated staging networks, synthetic data and no production secrets. Do not modify release controller, selected release metadata or migration history merely to simplify development.

## ADR 001 — Incremental hardening without provider replacement

Context: source already implements provider adapters, transactional RPCs and sophisticated protected release machinery; the live state differs from Git checkout.
Decision: fix evidenced request/configuration/cache/testing defects within current interfaces, and validate on the isolated VM. Keep current schema146 and immutable SQL unchanged unless a separately tested transition is indispensable.
Alternatives: wholesale ORM/Auth migration, new broker, microservices. These expand regression and operational risk without a measured justification.
Benefits: reviewable changes, preserved compatibility and existing release boundaries.
Costs/risks: privileged service-role queries still need application authorization; process-local caches cannot provide immediate cross-worker invalidation.
Migration impact: application-only changes require normal review and existing production admission gates; no automatic production actions.
Reversibility: isolated application commits can be reverted without database reversal. Configuration tightening needs a pre-deployment review of rejected unsafe settings.
