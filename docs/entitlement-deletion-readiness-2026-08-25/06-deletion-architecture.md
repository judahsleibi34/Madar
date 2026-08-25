# Durable deletion architecture

## Request types and freeze

The system models user account closure and tenant/workspace closure separately. Membership removal remains a distinct existing operation. `create_data_deletion_request` atomically locks the target, validates last-owner/last-admin safety, creates one durable request, captures auth subjects and storage resources, creates the fixed step plan, and sets `account_status` or `lifecycle_state` to `deletion_pending`.

The local account check blocks existing access/refresh sessions on their next application request. The tenant lifecycle gate blocks authenticated tenant routes and public hostname resolution, preventing uploads, publication, forms, reservations, notifications, and other new tenant writes from racing the workflow.

## Durable states

`pending`, `waiting_retention`, `in_progress`, `waiting_retry`, `completed`, `completed_with_retained_records`, `failed_manual_intervention`, and `cancelled_before_execution` are persistent states. A future `retention_until` remains frozen and unclaimable until due; no arbitrary delay was invented.

## Step sequence

1. reassert freeze;
2. establish local session revocation authority;
3. revoke integrations and remove encrypted local tokens;
4. stop notification and calendar work;
5. delete provider bucket objects;
6. delete validated host files;
7. delete application-owned user or tenant state;
8. delete captured Auth identities late;
9. independently verify database, public bindings, integrations, storage, and Auth absence;
10. finalize only from a verified state.

Each completed step is durable and skipped on replay. Missing objects/identities are success. The worker uses `FOR UPDATE SKIP LOCKED`, a bounded lease, attempt counters, exponential backoff, and expired-lease recovery. A second worker cannot claim the same live request.

## Components

- migration: `083_create_entitlement_mapping_and_deletion_lifecycle.sql` in both migration mirrors;
- service: `services/data_deletion_service.py`;
- worker: `workers/data_deletion_worker.py` with protected internal health/metrics;
- protected routes: `routes/data_deletion_routes.py` plus the existing AAL2 admin user route;
- lifecycle enforcement: account, tenant, and public-site resolvers;
- Compose: opt-in production worker profile and enabled development worker definition;
- observability: readiness worker state and redacted deletion backlog metrics.

The candidate is a deliberate schema-81/82/83 compatibility bridge. On schema 81/82 the lifecycle column is provably absent and no deletion request can exist; the deletion RPC/worker remain unavailable. A narrowly recognized missing-column response is allowed only after `application_schema_state` confirms 81/82. Every other lifecycle lookup error fails closed. Deploy the bridge first, then apply 083, then activate the worker.
