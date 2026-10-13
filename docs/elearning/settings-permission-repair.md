# Local Settings save permission repair

The schema139 normalizer is an immutable, SECURITY INVOKER JSON function. Its
BEFORE INSERT/UPDATE trigger calls it while `save_elearning_settings` runs as
`service_role`. Migration139 revokes helper EXECUTE from that role, causing42501
and a safe Settings500 response even though Settings reads succeed.

`web/scripts/repair_local_learning_settings_permissions.py` adds only EXECUTE on
`public.normalize_academy_programme_settings(jsonb)` to `service_role`.
It does not grant the trigger function, anon/authenticated access, table rights,
or bypass owner authorization, tenant boundaries or programme validation.

The default invocation rehearses the grant and exact service-role Settings writer
in transactions that roll back. `--apply` commits only the ACL grant. The writer
rehearsal uses a rolled-back savepoint, preserving existing settings rows.

Targets are exclusively the existing local application141 and marked preview144.
The tool requires development configuration, the fixed local database names and
port54322, a local Unix Docker context, the workspace-labelled Supabase container,
and matching PostgreSQL system identifiers. A loopback SSH tunnel is not sufficient.
The function body must exactly match immutable migration139, remain immutable and
invoker-only, and have no anon/authenticated EXECUTE grants.

Both local targets were rehearsed and repaired. Existing migrations001–144,
release descriptors and schema versions remain unchanged. The new production
SSH tunnel on15433 is excluded. No production inspection credentials or API
forward were supplied, and no production writes were made.

This is an explicit local operational repair, not a production migration or
release acceptance artifact. A production fix requires read-only schema/ACL
inspection, a reviewed corrective release compatible with the installed schema,
and the governed release workflow. Do not manually apply this grant to production
or edit historical migration139 to compensate for the bug.
