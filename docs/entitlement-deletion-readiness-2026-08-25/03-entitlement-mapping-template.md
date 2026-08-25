# Entitlement mapping template

The machine-readable template is `tenant-entitlement-mapping-template.json`. It contains all 12 production tenant IDs and deliberately leaves every commercial decision null.

Required operator fields per tenant:

- `target_state`: `active`, `trial`, `grace`, `grandfathered`, or `inactive`;
- `plan_id`: required except for `inactive`;
- `grace_until`: required for `grace` and `grandfathered`;
- `grandfather_reason`: required for `grandfathered`;
- `approved_by`, `approved_at`, and unique `mapping_id`;
- explicit add-ons and quantities only when approved.

The operator must review all rows as one batch. Partial mapping documents are rejected because leaving an unreviewed tenant implicit recreates the ambiguity this remediation removes.
