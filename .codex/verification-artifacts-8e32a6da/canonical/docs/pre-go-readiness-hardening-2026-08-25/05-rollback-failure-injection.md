# Rollback and failure injection

## Definitive post-switch rollback proof

A candidate at SHA `a2a5b968824a2478085d92b29eb348cc568cce66` was deployed to green. A watcher stopped the green backend immediately after the target switch. Observation failed. The first rollback switch correctly refused blue while its retained workers were not ready; the retry restored those workers, passed readiness, and switched traffic to retained blue.

The durable release record ended with:

- candidate status `failed`;
- failure phase `observation`;
- rollback action `traffic_switch_to_retained_known_good`;
- schema 83 retained;
- failed SHA suppression enabled.

Reoffering the failed SHA without explicit manual retry returned `known_bad_release_suppressed` before build. The rollback used retained immutable artifacts and did not rebuild historical source.

## Exercised failure classes

- invalid/dirty candidate and missing build input;
- build and image-provenance failure;
- held deployment or migration lock;
- absent/wrong-schema database;
- Redis, storage, and required-worker unavailability;
- false-positive liveness rejected by deeper readiness;
- migration checksum/state/interruption failure;
- candidate death before and after switch;
- switch failure and retryable rollback;
- overlapping invocation and repeated bad SHA;
- process interruption with durable phase recovery.

A whole physical-node reboot was not performed because production shares Node 1. Equivalent controller/slot process interruption demonstrated recovery of the durable state without risking production.
