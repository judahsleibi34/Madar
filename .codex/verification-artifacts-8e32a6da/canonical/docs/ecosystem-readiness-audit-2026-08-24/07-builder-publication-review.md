# Builder and publication review

## Strong controls retained

- Draft and published schemas are separate columns.
- Publishing validates tenant/project ownership, supported schema version, explicit homepage, unique page IDs/routes/form IDs and asset ownership.
- Migration 072 performs locking, revision comparison, snapshot copy, version increment and site binding in one database transaction.
- Public resolution requires exactly one website settings row and one bound published project with matching tenant.
- The public payload uses the bound `published_schema`, and body/chrome metadata are derived from that snapshot (`public_site_routes.py:678-690`).
- ETags include site identifier, project, publication version and schema hash. Responses require revalidation and set CDN no-store; unpublished/deleted/missing bindings return controlled 404s.
- Live database checks found no ambiguous mappings or ownership mismatches. Two public samples had distinct project identities.

## Snapshot regression

`GET /public/sites/{subdomain}/bootstrap` checks that a published binding exists but returns `website_settings.brand` and `logo_url` (`public_site_routes.py:2168-2183`). The full endpoint returns `published_schema.siteChrome`. Live aggregate comparison found one published site with a brand mismatch and one with a logo mismatch. This can show draft/new chrome on the loading screen while the body is an older publication.

Fix bootstrap by loading the bound published project and calling the same snapshot profile builder. Add a regression test that mutates draft/settings chrome after publish and asserts bootstrap, header, body and footer all remain on the same publication identity.

## Public assets

Assets are tenant-owned and publication validation rejects another tenant's asset ID. However `/public/assets/...` visibility is possession-of-random-URL, not publication reference. There are 60 active unreferenced builder assets; 52 are beyond retention. Treat draft asset URLs as shareable public URLs today. If draft confidentiality is required, issue short-lived authenticated preview URLs and expose a separate immutable published asset namespace.

## Builder UX/test evidence

Frontend save/recovery and revision-conflict mechanisms exist, but two deterministic collision-padding renderer failures affect saved layout fidelity. Full publish was not executed against production. Rollback semantics are publication-forward only; there is version metadata but no operator-facing transactional “restore publication N” workflow verified in this audit.
