# Multi-tenancy review

## Conclusion

No cross-tenant disclosure was reproduced. The principal boundary is **PASS WITH CONDITIONS**, not an unconditional proof.

## Evidence

- PostgreSQL 17; schema contract 81; 64/64 public tables have RLS enabled; no invalid indexes.
- Zero duplicate subdomains, zero duplicate standard path slugs, zero tenants with multiple website settings, and zero website-settings/project tenant mismatches.
- Key database constraints include unique `website_settings.subdomain`, unique `website_settings.tenant_id`, unique tenant project slug, tenant foreign keys and publication integrity checks.
- Two safely sampled live public sites returned HTTP 200, nonempty publication project identities, and distinct identities.
- `build_authorized_public_schema` preserves explicit homepage identity and filters pages/forms by permissions (`public_site_routes.py:535-565`).
- Publication validation rejects duplicate IDs/routes/forms and cross-tenant assets; migration 072 locks the project/settings boundary and atomically binds a versioned snapshot.
- Form and reservation RPCs check `(tenant_id, project_id)` against a published project before insert.
- Private dataset/chart path resolution requires both tenant and user scope (`services/upload_config.py:98-121`).
- Cache/rate keys examined include tenant/user identifiers. In-process workspace caches key by tenant/user and have bounds/TTLs.

## Residual risks

The application uses a service-role Supabase client. RLS is therefore defense for exposed roles, not the primary boundary inside backend code. A missed `.eq("tenant_id", ...)` can still be consequential. The test suite has broad tenant-focused unit coverage, but no full browser/API adversarial run using two real isolated tenant identities was performed.

The bootstrap endpoint uses a route identifier to resolve the correct tenant but returns mutable branding, not the bound snapshot. This is same-tenant draft/public leakage rather than a demonstrated cross-tenant leak. Public builder assets are tenant-owned and randomly named, but an uploaded/unpublished asset is accessible if its URL is known; publication is not the visibility gate.

Notification workers carry explicit tenant IDs and revalidate membership/subscription ownership before delivery. Calendar sync operations begin from tenant-scoped connection/event records; several downstream updates use globally unique UUIDs alone, which is acceptable with current provenance but should be hardened with tenant predicates for defense in depth.

## Required verification

Before GO, run disposable tests for tenant A IDs against tenant B builder, member, form, reservation, analytics, notification, calendar, asset, export and admin-support endpoints; include job payload substitution and hostname/path swapping. Assert both denial and absence of side effects.
