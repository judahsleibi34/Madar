# Custom ecommerce delivery locations

The Delivery areas page offers **Add custom location**. Country is required;
state/province/region, city/town, and up to three additional levels are optional.
Each hierarchy field has an optional Arabic counterpart. Adding or removing an
extra level also adds or removes its Arabic field. The Arabic display path is
assembled from those fields, falling back to the matching primary-language name
where a translation is blank. A country-only entry
represents delivery coverage for that country, not a street address.

Locations are persisted immediately as inactive coverage candidates, selected
locally, and only enabled for checkout when **Save delivery areas** succeeds.
Existing unsaved selections are preserved while adding a location. Reloading
before saving retains the location but discards its unsaved enabled selection.

## Storage and ownership

This implementation reuses the schema-095 service-area catalog and coverage RPC;
there is no schema migration or release metadata change. Hierarchy input is
stored as a readable full path in `name_en`, with the Arabic name or the same
path in `name_ar`. Hierarchy components are not separate database fields, and
there is currently no location-editing or location-deletion UI.

Custom ownership is encoded in the reserved, server-generated catalog code
`custom-{tenant_id}-{random_uuid_hex}`. The authenticated tenant comes from the
existing ecommerce access control, never the request body. Clients cannot set
codes or IDs. Creation requires the existing write role. Shared seeded area
codes do not use this reserved namespace.

Admin catalog reads return shared areas plus only that tenant's custom codes.
Coverage updates verify each requested active area and its ownership before
calling the existing transactional coverage RPC. Public checkout continues to
use enabled tenant mappings, area IDs, and immutable order display snapshots.
Custom entries are not inserted into tenant coverage mappings during creation.

Country and level names are trimmed and bounded; blank country, blank submitted
levels, more than five levels, and same-store duplicate display paths are
rejected. The UI omits empty optional levels. The existing coverage-selection
limit remains 100; creation caps each tenant at 100 custom catalog entries.

Ownership filtering is an application contract because catalog access uses the
service-role client. Do not roll back to code that lists the global catalog
without this filtering after custom locations have been created; that older
admin endpoint would expose other tenants' custom names.

## Verification

Backend tests cover hierarchy validation, ownership prefixes, private catalog
reads, cross-store selection rejection, duplicate creation, and disabled initial
coverage. Frontend tests cover creation, optional hierarchy levels, explicit
coverage saving, reload display, and creation failures.
