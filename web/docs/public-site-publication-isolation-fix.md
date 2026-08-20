# Madar public-site publication isolation fix

Date: 2026-07-31 (UTC)

Development checkout: `/home/madar/saas/Madar-dev`

Branch inspected: `builder-backend`

Commit inspected: `92b90bcceda9405441f50f68ae69bbab8331373a`

## Executive conclusion

The audited code contained several independent fail-open behaviors capable of producing the reported hybrid rendering:

1. Public hostname/settings and bound-project queries used `LIMIT 1` and selected the first row, concealing duplicate or ambiguous routing data.
2. `GET /public/sites/{identifier}` caught a missing bound-project 404 and returned a successful settings-only response. This allowed a tenant-looking shell without a valid publication.
3. The browser and publish normalizer resolved a missing/stale homepage through progressively weaker guesses and ultimately `pages[0]`. A page such as “Level One” could therefore become the body despite not being the configured homepage.
4. The runtime constructed brand/header/footer fallback fields from `website_settings` while the body came from `builder_projects.published_schema`. A wrong/stale `published_project_id` could therefore produce the exact “correct PalCode shell, wrong body” shape.
5. Page-reference resolution used the first matching page ID or slug. Duplicate IDs/slugs were not rejected at this public boundary.
6. The browser loading-brand cache was keyed only by the path identifier. It did not include hostname, site ID, project ID, or publication version.
7. Publishing the JSON snapshot was transactional, but the first-site binding was performed by a later application write. That left publication activation outside the snapshot transaction.
8. A legacy snapshot without `siteChrome` could acquire the frontend's Madar factory header/footer defaults. The public runtime now suppresses chrome when the resolved snapshot has none; it never manufactures a tenant shell from factory content.

These are verified code defects. The repository does not contain production row data, so it is not possible to truthfully name the exact production row that contains “Level One” or prove whether it belongs to another tenant without running the supplied read-only diagnostic against production. Cross-tenant exposure was technically possible if an incorrect/ambiguous hostname binding or project binding existed; the public query now verifies the settings tenant, exact bound project, page, forms, reservations, and managed assets as one boundary and fails closed.

The generic “Untitled Site / Build your business app without code” strings exist in builder starter/editor content, not in the hardened public runtime. Their appearance in a purported public rendering therefore requires production verification of the requested URL, deployed frontend version, browser/service-worker state, and edge cache. The current public runtime now renders an unavailable/not-found state rather than factory content when resolution fails.

## Root-cause evidence

| Boundary | Previous behavior | Risk | Corrected behavior |
|---|---|---|---|
| Host/site settings | `resolve_website_settings` queried `website_settings` with `LIMIT 1` and used row 0 | Duplicate/colliding mappings silently chose a record | Fetches up to two and returns 409 on ambiguity; 404 on no match |
| Site/project | `get_bound_published_project` used `LIMIT 1`; root endpoint suppressed project 404 | Settings shell could be returned without a publication | Exact tenant + project + published status + snapshot required; no suppressed 404 |
| Homepage | Publish/runtime fell back through name and ultimately first page | Deleted/stale homepage could render unrelated page | Public runtime requires `defaultPageId`, exactly one matching ID, exactly one `/` route, and consistent optional flag |
| Page lookup | First ID-or-slug match won | Duplicate page references were hidden | Zero matches = 404; multiple matches = 409 |
| Shell/body | `website_settings` fields supplied shell fallback while project supplied body | Hybrid shell/body from separate records | Public profile is derived from the same immutable project snapshot |
| Assets | Managed upload URLs were not checked against publication tenant at public resolution | A schema could reference another tenant’s managed path | Publish and runtime reject `/uploads/tenant_N/` paths for another tenant |
| Browser cache | `madar:tenant-brand:{subdomain}` | Stale/cross-publication loading identity | Key requires hostname + identifier + site ID + project ID + version; no pre-resolution reuse |
| HTTP/CDN cache | ETag omitted site/hostname identity | Reuse risk under a mis-keyed intermediary | ETag/publication key includes site, identifier, project, version, schema hash; `Vary` added; CDN cache disabled |
| Publish activation | Snapshot RPC and first binding update were separate | First activation was not one transaction | Migration 072 locks project/settings, validates snapshot, publishes, and binds an unambiguous first site in one transaction |
| Missing legacy chrome | Public renderer could use `defaultSiteChrome` | Madar factory identity could appear around tenant content | Missing snapshot chrome renders no header/footer; no settings or factory shell is substituted |

## Affected routes, services, tables, and cache keys

### Routes

- `GET /public/sites/{subdomain}`
- `GET /public/sites/{subdomain}/pages/{page_reference}`
- `GET /public/sites/{subdomain}/forms/{form_id}`
- `POST /public/sites/{subdomain}/forms/{form_id}/submissions`
- `POST /public/sites/{subdomain}/events` (including reservations)
- Public catalog routes, which now also require the strict bound publication before catalog access
- `POST /builder/projects/{project_id}/publish`
- `PUT /builder/site-binding`

### Tables and records

- `website_settings.id, tenant_id, subdomain, standard_path_slug, published_project_id`
- `builder_projects.id, tenant_id, status, published_schema, published_version, published_revision, last_published_at`
- Forms and reservation blocks remain embedded inside the same `published_schema`
- New `publication_integrity_reviews` records ambiguous historical snapshots without selecting or repairing them automatically

There is no separate production “active publications” table. The active boundary is the single `website_settings.published_project_id` pointer to one immutable `builder_projects.published_schema` version. Other projects may retain published snapshots, but they are not active for that site.

No customer-owned custom-domain mapping table or resolver was found in the active public-site path. The implemented resolver supports the central path identifier and Madar wildcard subdomain model. An unknown/custom Host does not cause a search for a default project; customer-owned custom domains remain unsupported pending a separately designed, unique verified-domain mapping.

### Cache boundaries

- Server public-site content has no Redis object cache. The ecommerce catalog cache is tenant-scoped and is not used to render builder pages.
- Public responses now use a publication key of:
  `site_id:site_identifier:project_id:published_version:schema_hash`
- Response headers include `Vary: Host, X-Forwarded-Host, Origin` and `CDN-Cache-Control: no-store`.
- Frontend requests already use `cache: no-store`.
- The loading-brand localStorage key now includes hostname, site identifier, site ID, project ID, and publication version. Since those values are unavailable before successful resolution, stale branding is not shown during initial resolution.
- No general service worker caches builder pages. The registered worker is for Web Push; production verification should still inspect browser registrations/caches to rule out an obsolete deployment artifact.

## Enforced publication invariants

The backend now verifies before returning any public website/page/block:

- exactly one hostname/path settings row;
- a non-null site binding;
- exact project ID and tenant ownership;
- published state and non-null snapshot;
- nonempty website pages (standalone forms are the deliberate exception);
- unique, nonempty page IDs;
- unique normalized routes inside the project snapshot;
- one explicit homepage ID;
- exactly one root page and agreement with the homepage ID;
- no conflicting homepage flags;
- tenant ownership of managed asset paths;
- forms and reservation blocks found only inside the bound snapshot;
- duplicate form IDs and duplicate/missing reservation block references rejected rather than selecting the first match;
- protected direct-page responses matching the same site/project/version as the root response.

Missing data returns 404. Ambiguous/inconsistent data returns 409. Backend/dependency failures remain controlled failures and are not replaced by a default project.

## Database migration 072

Files:

- `database/migrations/072_harden_publication_isolation.sql`
- `supabase/migrations/072_harden_publication_isolation.sql`

The mirrored migration:

- creates service-role-only `publication_integrity_reviews`;
- creates `builder_publication_integrity_error(jsonb)`;
- repairs only an unambiguous legacy snapshot with no `defaultPageId` and exactly one existing root page;
- increments `published_version` for that repair so cache identity changes;
- records all remaining ambiguous snapshots for manual review;
- adds `builder_projects_publication_integrity_check NOT VALID`, so new/updated snapshots are constrained while ambiguous historical snapshots are not silently altered;
- replaces the existing publish RPC with the same signature, adds a settings-row lock, validates the complete snapshot, writes the whole snapshot/version, and activates an unambiguous first binding before commit;
- preserves existing bound sites and does not switch a site to another published project automatically.

The constraint intentionally remains not validated until all review rows are resolved. This is a production rollout blocker for claiming full historical consistency, but it does not weaken new writes or runtime fail-closed validation.

## Production records

The owner later authorized applying migrations 071 and 072 to Madar's single
shared live database after a verified backup. Structural post-migration checks
found six website settings, five published bindings, valid tenant/project
ownership on the inspected bindings, and zero
`publication_integrity_reviews`. The PalCode public API and frontend route both
continued returning HTTP 200 after migration. No production application code
was deployed or restarted.

The validation intentionally did not print full page bodies. Therefore:

- exact live structural review issues detected by migration 072: **none**;
- ownership/source of the historically observed “Level One” body: **still
  unknown without the targeted body-hash diagnostic**;
- Cloudflare/browser cache contribution to the historical symptom: **unknown
  pending uncached edge/browser comparison**.

The diagnostic intentionally returns IDs, counts, structural hashes, and limited labels—not full private page content.

## Read-only diagnostic

Use `database/verification/072_publication_isolation_diagnostic.sql` with a read-only role. Determine the actual site identifier from the public URL first.

```bash
cd /path/to/deployed/repository
psql "$READ_ONLY_DATABASE_URL" \
  -v ON_ERROR_STOP=1 \
  -v site_identifier='REPLACE_WITH_PALCODE_IDENTIFIER' \
  -v project_id='22ca8aa2-a2f5-4ad0-97b5-a1709714f74c' \
  -f database/verification/072_publication_isolation_diagnostic.sql
```

Review:

1. whether the identifier matches more than one settings row;
2. whether `published_project_id` equals the intended project UUID;
3. tenant IDs on both rows;
4. project status/version/revision and schema hash;
5. configured homepage ID versus the one root page;
6. duplicate IDs/slugs/homepage candidates;
7. hashes for `siteChrome` and the homepage body;
8. orphaned/cross-tenant bindings;
9. pending `publication_integrity_reviews`.

To identify the “Level One” page without broadly displaying content, an authorized operator may run a targeted query for page IDs/names/slugs and hashes in only the two suspected projects. Do not export entire schemas into tickets.

## One-time safe production repair procedure

This is a procedure for an authorized maintenance window; it was **not** executed.

1. Back up the affected `website_settings`, intended `builder_projects`, and any currently bound project row using the established encrypted backup process.
2. Apply migrations in order, including 071 then 072, before deploying backend code.
3. Run the diagnostic above. Stop if tenant ownership is ambiguous or multiple settings rows map the host.
4. Resolve every relevant `publication_integrity_reviews` item manually:
   - confirm the intended tenant and project with the owner;
   - choose the homepage explicitly in the builder;
   - normalize/uniquify page slugs in that project;
   - remove cross-tenant managed asset references;
   - do not copy content from another project as a repair.
5. Deploy the compatible backend.
6. Authenticated tenant owner/admin republishes project `22ca8aa2-a2f5-4ad0-97b5-a1709714f74c` with its current `draft_revision`:
   ```bash
   curl --fail-with-body -X POST \
     'https://madarportal.com/api/builder/projects/22ca8aa2-a2f5-4ad0-97b5-a1709714f74c/publish' \
     -H 'Content-Type: application/json' \
     -H 'X-Madar-Builder-Contract: cloud-draft-v1' \
     -H 'X-CSRF-Token: REDACTED' \
     -H 'Cookie: REDACTED' \
     --data '{"expected_revision":REPLACE_WITH_VERIFIED_REVISION}'
   ```
7. If the diagnostic proves the site binding points elsewhere, select the intended already-published project using the authenticated binding API:
   ```bash
   curl --fail-with-body -X PUT \
     'https://madarportal.com/api/builder/site-binding' \
     -H 'Content-Type: application/json' \
     -H 'X-Madar-Builder-Contract: cloud-draft-v1' \
     -H 'X-CSRF-Token: REDACTED' \
     -H 'Cookie: REDACTED' \
     --data '{"project_id":"22ca8aa2-a2f5-4ad0-97b5-a1709714f74c"}'
   ```
8. Re-run the read-only diagnostic and confirm one settings row, one intended bound project, no integrity error, and a matching homepage.
9. Purge only the affected hostname/URLs at Cloudflare if an edge cache rule outside the repository overrides `CDN-Cache-Control`. Do not purge unrelated sites.
10. Clear the affected browser’s site data/service-worker registration only as a client verification step; this is not the server repair.

Do not directly rewrite `published_schema` in production. The supported repair is to fix the draft, explicitly choose the homepage, republish through the transaction, and explicitly change the site binding only after ownership is proven.

## Before-and-after verification

Resolve the production origin IP through the approved operations inventory. These requests bypass browser state and add cache busters. If Cloudflare is the intended hop, use its IP/resolution and inspect `CF-Cache-Status`; for origin-only verification use the internal loopback/upstream endpoint with the explicit Host header.

```bash
SITE_HOST='REPLACE_WITH_PALCODE_HOSTNAME'
SITE_ID='REPLACE_WITH_PALCODE_IDENTIFIER'
ORIGIN_IP='REPLACE_WITH_APPROVED_IP'

curl --fail-with-body --resolve "$SITE_HOST:443:$ORIGIN_IP" \
  -H 'Cache-Control: no-cache, no-store' -H 'Pragma: no-cache' \
  -D /tmp/palcode-before.headers \
  "https://$SITE_HOST/site/$SITE_ID/?verify=before-$(date +%s)" \
  -o /tmp/palcode-before.html

curl --fail-with-body --resolve "$SITE_HOST:443:$ORIGIN_IP" \
  -H 'Cache-Control: no-cache, no-store' -H 'Pragma: no-cache' \
  -D /tmp/palcode-after.headers \
  "https://$SITE_HOST/site/$SITE_ID/?verify=after-$(date +%s)" \
  -o /tmp/palcode-after.html

grep -F 'Bridging Heritage and Future Code' /tmp/palcode-after.html
! grep -F 'Level One' /tmp/palcode-after.html
! grep -F 'Build your business app without code' /tmp/palcode-after.html
```

Because the React shell may not include fetched page text in initial HTML, also verify the authoritative API:

```bash
curl --fail-with-body --resolve "$SITE_HOST:443:$ORIGIN_IP" \
  -H 'Cache-Control: no-cache, no-store' -H 'Pragma: no-cache' \
  -H "Host: $SITE_HOST" \
  "https://$SITE_HOST/api/public/sites/$SITE_ID?verify=$(date +%s)" |
  jq '{
    site: .site.subdomain,
    site_id: .project.site_id,
    project_id: .project.project_id,
    published_version: .project.published_version,
    schema_hash: .project.schema_hash,
    homepage_id: .project.published_schema.defaultPageId,
    page_ids: [.project.published_schema.pages[] | {id, slug, isDefault}]
  }'
```

Expected after repair:

- HTTP 200 for the intended host and site;
- unknown host/identifier: 404, never another site;
- one project ID: `22ca8aa2-a2f5-4ad0-97b5-a1709714f74c`;
- one homepage ID, one `/` page, matching IDs;
- a new published version and schema hash after republish;
- `CDN-Cache-Control: no-store`;
- no “Level One” or generic builder factory body.

## Files changed for this fix

- `backend/routes/public_site_routes.py`
- `backend/routes/builder_routes.py`
- `backend/tests/test_builder_form_submissions.py` (fixture isolation/homepage metadata)
- `backend/tests/test_builder_archived_projects.py` (fail-closed contract and valid publication fixtures)
- `backend/tests/test_builder_backend_hardening.py` (atomic first-binding response contract)
- `backend/tests/test_publication_isolation.py`
- `backend/tests/test_website_routes.py` (same-snapshot shell fixture)
- `frontend/src/components/PageBuilder/core/PageBuilder.routing.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.routing.test.js`
- `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx`
- `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.flow.test.js`
- `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.routing.test.jsx`
- `database/migrations/072_harden_publication_isolation.sql`
- `supabase/migrations/072_harden_publication_isolation.sql`
- `database/verification/072_publication_isolation_diagnostic.sql`
- `scripts/rehearse_migration_072.sh`
- `docs/public-site-publication-isolation-fix.md`

The other modified/untracked files in the checkout predated this task and belong to the preserved commercial-entitlement implementation.

## Validation results

Completed on 2026-07-31 UTC:

| Validation | Result |
|---|---|
| Publication/website focused backend suite | **51/51 passed** |
| Builder publish hardening module | **25/25 passed** |
| Full backend no-external-network harness | **799/800 passed; 1 unrelated existing error** |
| Frontend test suite | **476 passed, 1 skipped; 80/80 files passed** |
| Frontend production build and theme audit | **Passed** |
| Migration 001–072 disposable rehearsal | **Passed** |
| Migration mirror/checksum validation | **Passed; 72/72 mirrored** |
| Compose configuration | **Passed** |
| `git diff --check` | **Passed** |
| Targeted secret scan of isolation changes | **Passed; no matches** |
| Frontend lint | **Passed: 0 errors and 0 warnings on the final worktree** |

The one full-backend error is
`test_app_middleware.AppMiddlewareTests.test_unhandled_exception_returns_sanitized_json_with_cors_and_request_id`:
the synthetic unhandled-error response lacks its expected localhost CORS header in the
current combined test process. No application middleware or CORS file was changed by this
fix, and all 798 other tests pass. This existing failure is reported rather than suppressed.

The earlier intermediate lint run reported 9 errors and 4 warnings, but those
findings did not reproduce once all preserved implementation changes were
assembled. The final lint run is clean and no lint rule was weakened.

The disposable rehearsal applies 001–071, seeds valid, unambiguously repairable, ambiguous,
archived, and draft publication cases, verifies a deliberately failed 072 transaction leaves
no partial schema, applies 072, checks repair/review creation and access grants, reapplies 072,
confirms valid bindings and existing data remain intact, and executes the read-only production
diagnostic against the resulting schema.

The two migration 072 mirrors are byte-identical with SHA-256
`54b7e653a4d8e78290a79e906e9a5599b0f6427c4f8fe7ab98f067f35e702953`.
Final worktree status contains 70 paths (48 tracked modifications and 22
untracked paths); most are the explicitly preserved commercial-entitlement
work that predated this incident fix. No commit was created.

## Deployment order

1. Take the normal production backup and verify it. **Completed.**
2. Apply migration 071. **Completed.**
3. Review the 071 reconciliation output. **Completed for migration safety; six commercial route reviews remain.**
4. Apply migration 072. **Completed.**
5. Run the 072 structural review. **Completed; zero live review issues.** Do not validate the historical constraint yet.
6. Deploy the backend with strict resolver compatibility. **Not yet performed.**
7. Republish the intended project(s) through the authenticated API.
8. Correct explicit site bindings only after tenant/project ownership is verified.
9. Deploy the frontend.
10. Verify API and browser rendering with explicit hostname and no-cache requests.
11. Purge only affected edge URLs if an external cache rule overrode response headers.
12. After all `publication_integrity_reviews` rows are resolved, validate `builder_projects_publication_integrity_check` in a later controlled migration.

Rollback must roll back application binaries together. Do not reverse migration 072 by dropping its review history; if application rollback is required, preserve the review table and restore the prior compatible backend while investigating.
