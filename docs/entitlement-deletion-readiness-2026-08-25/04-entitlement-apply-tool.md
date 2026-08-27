# Entitlement apply tool

Implementation: `web/backend/scripts/apply_entitlement_mapping.py`; transaction RPC and invariants: migration 083.

## Safety properties

- dry-run is the default; mutation requires explicit `--apply`;
- reads the current tenant set and requires complete one-to-one coverage;
- rejects unknown/duplicate tenants, unknown plans/add-ons/states, missing approval evidence, invalid quantities, and incomplete grace/grandfather data;
- submits one batch to a transaction-scoped, service-role-only RPC;
- validates the entire document before its first write;
- cancels superseded entitlement-bearing rows and never restores compatibility fallback;
- uses unique mapping and add-on idempotency keys;
- records the explicit decision separately from the authorization row;
- database partial uniqueness prevents multiple entitlement-bearing subscriptions.

## Future operator procedure

1. Install schema 083 through the controlled release migration stage.
2. Regenerate and compare the read-only inventory; stop if the tenant set changed.
3. Obtain named authorization for every template row.
4. Run `python scripts/apply_entitlement_mapping.py <approved.json>` from the backend operator environment. Preserve the dry-run output.
5. Peer-review the complete diff and approvals.
6. Run the same command with `--apply` once.
7. Regenerate the inventory and verify each capability, quota, add-on, public-site continuity rule, and absence of ambiguous rows.
8. Preserve mapping IDs and redacted before/after evidence in the operational audit record.

`--apply` was not run against production in this task.
