# Madar Page Builder Full Codebase Audit

Audit date: 2026-07-15
Repository: `/home/madar/saas/Madar-dev`
Branch: `builder-backend`
Scope: audit only; no application behavior, database row, migration, production container, or published site was changed.

## 1. Executive Summary

The Page Builder has a sound intended backbone: explicit project routes, tenant-scoped backend reads, full-draft optimistic updates, atomic publishing, published-only public reads, bounded three-way rebasing, and hardened public submission/reservation routes. The current backend mutation route is materially safer than the historical browser-first design.

The implementation is not yet one coherent system. It has three competing generations of state: the routed cloud project, V5 recovery/cross-tab state, and legacy V4 project state still used by Settings, Dashboard, Archive, and demo paths. The 5,774-line `PageBuilder.jsx` mirrors persistence state across React state and more than a dozen refs. Public rendering is a separate renderer with independent routing and site-chrome behavior. Database RLS still permits authenticated clients to bypass the backend's concurrency and publishing invariants.

The most likely explanation for the real-browser “saved in the database, failed in the UI, fixed by refresh/Incognito” symptom is order-sensitive snapshot identity. Autosave acknowledgement, recovery equality, publish divergence, and readiness use raw `JSON.stringify` in multiple places. PostgreSQL `jsonb` is not an object-key-order-preserving contract. A successful PUT whose returned schema is semantically equal but differently ordered can fail the exact-string acknowledgement check, enter the catch path, retain recovery, and show `Save failed`. Mocks preserve insertion order, so the existing 228 frontend tests do not exercise this boundary. Refresh adopts the server-returned order as both the editor and acknowledged baseline.

No P0 issue was proven. Eight P1 findings require priority attention: order-sensitive acknowledgement identity, destructive page-name cleanup, direct-database invariant bypass, ambiguous multi-project public-site binding, broken explicit preview routing, non-deterministic normalization, destructive recovery parsing, and server status embedded in the draft schema. There are 15 P2 and 3 P3 findings.

## 2. Scope and Method

The review covered all files under `frontend/src/components/PageBuilder`, related Dashboard/route/settings code, Page Builder styles/content/locales, builder/public/website/billing backend routes and services, builder-related models, both migration trees, and related tests. Source tracing was combined with targeted searches for every project mutation, recovery key, revision source, public lookup, form/reservation path, upload path, route builder, and normalizer.

Repository baseline:

- Branch: `builder-backend`.
- Divergence: `HEAD...origin/main = 0 0`; `HEAD...origin/builder-backend = 0 0`.
- Existing work preserved: 26 modified files and 59 untracked files before this report.
- Migration trees: 48 database and 48 Supabase migrations; zero errors; two known duplicate-content warnings for migrations 013/014.
- Inventory: 164 files under `frontend/src/components/PageBuilder`; 58 Page Builder style files; 49 backend test modules.
- Largest implementation units: `PageBuilder.jsx` 5,774 lines/212 KB, `DataAnalysisWorkspace.jsx` 101 KB, `FormsTab.jsx` 91 KB, and `TenantSiteRuntime.jsx` 73 KB.

No diagnostic instrumentation was required. No real project or database state was queried or mutated.

## 3. Architecture Map

| Stage | Entry point | Source of truth | Main state/refs | API/DB interaction | Failure behavior |
|---|---|---|---|---|---|
| Project creation | `BuilderProjectChooser.createProject` | New starter object | chooser state | `POST /builder/projects` | chooser error; no local attach |
| Project selection | legacy workspace route | backend list | chooser state | `GET /builder/projects` | chooser error |
| Explicit routing | `UserWorkspaceRoutes`, `workspaceRouting.js` | route project ID | React Router | none | chooser when no ID |
| Hydration | PageBuilder load effect | backend record | project, record/ref, revision/base/ack refs | exact-project GET | loading/error state |
| Normalization | `getDraftProjectFromRecordWithRepairs` | server draft input | normalized editor object | none | can silently repair/remove data |
| Editor-local state | PageBuilder | React memory | active IDs, selection, modal, viewport | none | reset on mount/adoption |
| Persistable state | `getPersistableProject` | editor project minus four active IDs | project/ref | PUT full `draft_schema` | recovery + failed/conflict state |
| Recovery | V5 hook/recovery helpers | localStorage emergency copy | dirty/revision/timestamp refs | localStorage/BroadcastChannel | notice/export/discard |
| Autosave | project effect -> coordinator | current project ref | timer, coordinator, mirrored refs | PUT exact project | retry/rebase/failure |
| Revision authority | PageBuilder ref | server GET/PUT | `currentDraftRevisionRef` | expected revision | 409 starts rebase |
| Automatic rebase | conflict/merge helpers | base/local/latest server | merge state | GET + one merged PUT | overlap becomes terminal conflict |
| Manual conflict | resolution dialog | latest server + selections | conflict state | GET + coordinated save | remains blocked on failure |
| Publish preparation | `prepareBuilderProjectForPublish` | acknowledged snapshot/revision | save/publish refs | optional save drain | structured blocking reason |
| Backend publish | builder route/RPC | locked backend draft | DB row | atomic RPC | 409/entitlement/validation error |
| Public lookup | public-site route | latest published project for tenant | runtime state | public GET | unavailable site |
| Public rendering | `TenantSiteRuntime` | `published_schema` | runtime page/auth/form state | public APIs | not-found/unavailable UI |
| Form submission | runtime form | published form/block | runtime answers | insert submission | validation/rate-limit error |
| Reservation | runtime block | published block + durable row | runtime status | hardened reservation RPC | collision/idempotency error |
| Asset upload | builder/settings | tenant filesystem path | URL in schema/settings | multipart upload | validation/rate-limit error |
| Website settings | Settings/backend | `website_settings` | Settings local project mirror | GET/PUT settings | local notification |
| Archive/delete | archive datasets/project archive route | IndexedDB / backend project | separate workspaces | local deletion / archive update | error status |

## 4. Source-of-Truth Analysis

The intended canonical editable source is `builder_projects.draft_schema`; the canonical live source is `published_schema`. That contract is correctly enforced by backend update and publish routes. The browser implementation nevertheless has competing inputs:

1. `project` React state and `projectRef` both hold the editor project.
2. `builderProjectRecord` and its ref hold server metadata plus draft/published schemas.
3. `baseSchemaRef`, `backendProjectSnapshotRef`, coordinator state, pending snapshot refs, and recovery state each represent overlapping persistence facts.
4. `SettingsPage`, Dashboard fallback statistics, and Archive workspace naming still read/write V4 localStorage.
5. Website settings and `draft_schema.siteChrome` contain overlapping branding/contact values with runtime merge precedence that is not obvious in the editor.
6. Public site identity is tenant/subdomain based, but project identity is selected as the tenant's most recently published project rather than an explicit binding.

The backend draft/publish boundary is clear; the frontend and site-binding boundaries are not.

## 5. State Ownership Findings

| State/ref | Owner | Writers | Readers | Persisted? | Risks |
|---|---|---|---|---|---|
| `project` / `projectRef` | PageBuilder | editor updates, hydration, rebase, conflict | renderer, save, publish | draft minus active IDs | mirrored values can lag |
| `builderProjectRecord` / ref | PageBuilder | GET/save/publish/unpublish | revision/publish UI | DB record | duplicate authority |
| active page/form/workflow/role | project object | selection handlers/hydration | tabs/inspector | excluded from draft | still present in editor object |
| selection/modal/viewport/drag | PageBuilder | UI | editor | no | correctly local |
| draft revision ref | PageBuilder | hydration/save/rebase | coordinator/publish | DB column | canonical but broadly reachable |
| base schema ref | PageBuilder | hydration/save/rebase | merge | no | can diverge from record schema |
| acknowledged snapshot ref | PageBuilder | adoption/save/rebase/unpublish | status/publish/coordinator | no | raw stringify order-sensitive |
| pending snapshot/ref | PageBuilder | autosave/save/adoption | scheduling | no | duplicates coordinator queue |
| coordinator active/queued state | save coordinator | save callers | publish/status | no | second queue authority |
| save state | PageBuilder React state | effects and async branches | status/publish UI | no | imperative + derived hybrid |
| recovery decision/envelope | PageBuilder/hook | load/failure/ack | notice/conflict | localStorage | normalized on read; stale classification |
| conflict state/ref/details | PageBuilder | 409/rebase/resolution | save/publish/dialog | recovery only | duplicated latch/details |
| website settings | Settings/PageBuilder/runtime | settings GET/PUT | builder/runtime/publish | separate table | overlaps siteChrome |
| runtime form/auth/reservation state | runtime | public interactions | runtime | submission/reservation tables | separate renderer semantics |

## 6. Routing and Project Identity

Explicit edit routes correctly require `/page-builder/projects/:projectId/...`; the project-less editor is not mounted. Builder responses/data routes preserve IDs through shared helpers. Project switches remount PageBuilder with a key and invalidate normal in-memory state.

Defects remain:

- Draft preview is routed at `/page-builder/projects/:projectId/preview/*`, but `TenantSiteRuntime` slices and navigates relative to hard-coded `/page-builder/preview`. Non-default preview pages resolve incorrectly and navigation drops the project ID.
- The chooser fetches the backend default page of 20 projects and ignores pagination metadata. Projects beyond the first 20 are not selectable through this surface.
- Dashboard primary links still go to project-less `/page-builder`; this is safe but adds an avoidable chooser round trip.
- Archive is not project-routed and displays a V4 localStorage project name, so its visible project identity can be unrelated to the active cloud project.
- Missing/archived project GETs are not recreated by recovery, which is correct.

## 7. Hydration and Normalization

Hydration shows loading state and does not mount the existing-project editor before the exact GET resolves. The server record ID is checked during adoption. Editor active selections are derived after normalization.

Normalizer audit:

| Normalizer | Pure/immutable | Idempotent | Deterministic | Unknown fields | Main risk |
|---|---:|---:|---:|---:|---|
| `stripEditorOnlyState` | yes | yes | yes | preserves | excludes only four fields |
| `normalizeProjectPageRouting` | yes | yes on valid IDs | yes | preserves | rewrites slugs/order/default flags |
| element/row/column/section factories | mostly | usually | no for missing IDs | mostly preserves | factory ID generation |
| `repairDuplicateProjectIds` | yes | output-idempotent | no without injected factory | preserves | random repair IDs |
| `cleanBuilderProjectWithRepairs` | yes | output-idempotent | no on malformed input | partly | removes named pages and records |
| recovery envelope parser | yes | output-idempotent | inherits cleaner | partly | transforms emergency copy |
| merge utility | yes | yes | yes | property-level | coarse arrays without stable IDs |

`cleanBuilderProjectWithRepairs` removes legitimate pages named Responses, Reports, Orders, Submit Request, Submit Report, or Place Order (except index zero), clears form `responses` and collection `records`, removes matching footer labels, converts layout, and repairs IDs. This is compatibility migration behavior applied during routine hydration/save, not a version-gated migration.

## 8. Persistence and Autosave

| Trigger | Path | Can dispatch PUT? | Revision source | Snapshot source | Protection |
|---|---|---:|---|---|---|
| debounced project edit | effect -> `saveProject` | through coordinator | ref at dispatch | latest cleaned project | single-flight |
| retry | `saveProject` | through coordinator | ref at dispatch | current project | single-flight |
| Go Live | publish preparation -> `saveProject` | only if not ready | ref at dispatch | current project | publish single-flight |
| auto rebase | coordinator dispatch -> rebase helper | internal merged retry | latest GET revision | merged schema | one bounded retry |
| conflict resolution | resolution -> `saveProject` | through coordinator | adopted revision | resolved project | generation guard |
| blur/pagehide/visibility | recovery hook | no cloud PUT | n/a | current project | localStorage only |

There are two low-level project PUT call sites: the normal coordinator dispatch and the merged retry inside the same logical rebase chain. Queue entries do not contain revisions; the coordinator reads the revision at dispatch. These are positive properties.

The serious remaining defect is snapshot identity. `getAutosaveSnapshot`, recovery hashing, and publication comparison all depend on raw `JSON.stringify`. The normal save then rejects a server acknowledgement when `JSON.stringify(savedRecord.draft_schema) !== JSON.stringify(nextProject)`. A semantically identical `jsonb` response with reordered keys can therefore turn a successful backend write into a visible failure. The error occurs after the backend commit, so retry/recovery UI is false. This matches the reported refresh behavior.

The coordinator also coexists with PageBuilder-owned pending/active/save-promise refs. That duplication increases race surface and makes the 5,774-line component the real coordinator of coordinator state.

## 9. Snapshot Contract

The current persistable contract is permissive: `getPersistableProject` shallow-copies the project and removes only `activePageId`, `activeFormId`, `activeWorkflowId`, and `activeRoleId`. It preserves pages, order/routing metadata, sections, blocks, responsive positions, forms, workflows, roles, users, collections, theme, site chrome, publish configuration, and unknown fields.

Boundary mismatches:

- Record `status` is injected into the editor draft during GET, so server lifecycle metadata becomes draft JSON.
- Publish timestamps are special-cased out of autosave snapshots but remain representable in the project.
- Form responses and collection records are removed by cleaner rather than by the canonical persistable helper.
- Recovery stores the persistable project but normalizes it again when read.
- Public runtime receives only `published_schema`, while website settings are merged separately.
- Backend publish validation is stricter than draft save validation, so an autosaved draft can remain unpublishable.

## 10. Revision and Conflict Handling

The revision ref is updated from exact GET, successful normal save, merged rebase, and adoption. Expected revision is read at dispatch. The merge helper is recursive, immutable, key-order independent, and ID-aware for arrays where all items have stable IDs. It correctly detects same-field conflicts, delete-versus-edit, and incompatible ordering.

Risks:

- Section, row, column, form-field, workflow, role, collection, and footer-link IDs are not globally repaired/validated like page/form/block IDs. Missing IDs cause entire arrays to be treated as positional values; duplicate IDs produce coarse whole-array conflicts.
- Rebase/adoption/save acknowledgement logic is implemented directly in PageBuilder rather than one canonical acknowledgement function.
- Post-commit client-side validation or local state adoption errors are caught as save failures even though the server may already have committed.
- The terminal conflict latch is appropriate, but conflict and recovery classifications still use similar “stale” language.

## 11. Browser Recovery

| Key format | Writer | Reader | Payload | Cleanup | Risk |
|---|---|---|---|---|---|
| `madar_app_builder_frontend_v5:user:{u}:tenant:{t}:project:{p}` | recovery hook | hydration/recovery UI | full envelope/schema/base revision/hash/time | acknowledgement/discard | read-time normalization, string hash |
| same key `:backup` | legacy persistence only | V4 storage reader | full old project | clear helper | no active V5 writer; legacy debt |
| `madar_app_builder_frontend_v4[:user:{u}]` | Settings/demo/legacy | Settings/demo/export | full browser project | explicit discard | competing visible state |
| `madar-builder-draft-sync` | recovery hook | PageBuilder | schema string + local counters | channel close | advisory message complexity |

Recovery is scoped by user/tenant/project and is not automatically applied, which is correct. It does not set the backend revision. However, parsing runs the full destructive cleaner, so an emergency export can differ from the exact bytes that were stored. Equality uses an order-sensitive FNV hash. The hook maintains a local revision counter and broadcasts full serialized schemas although cross-tab behavior is meant to be advisory. Equivalent server content with a different key order can remain as “stale recovery.”

## 12. Go Live and Publishing

Backend publishing is strong: it tenant-scopes the project, requires the client contract, checks expected draft revision, validates the stored draft, invokes a service-role-only RPC that locks/checks/copies the backend draft, and updates publish metadata atomically. The browser cannot submit an alternate published schema.

Frontend readiness correctly returns ready without saving when current and acknowledged snapshot strings match. A clean Go Live therefore performs zero draft PUTs in the code path. The weakness is that “match” is order-sensitive and derives from mirrored refs. A semantically clean project can be classified unsaved and flushed unnecessarily.

After publish, PageBuilder updates the record but does not adopt `project.status = published`; unpublish checks `project.status`. Refresh injects record status into the project, changing behavior. Unpublish then changes the local status and acknowledged hash even though the backend leaves `draft_schema` unchanged. Lifecycle metadata should not be in the content schema.

## 13. Public Runtime

Public GET uses `published_schema` only and the frontend requests it with `cache: no-store`, preserving draft/live separation. It has no explicit project binding: the server chooses the latest published project in the tenant. The response omits project ID and published version, limiting cache/version diagnostics.

| Feature | Builder preview | Public runtime | Match? | Risk |
|---|---|---|---:|---|
| exact project | routed ID | latest tenant publish | no | wrong project can be served |
| preview route base | explicit project path | hard-coded legacy base | no | preview navigation breaks |
| header/footer visibility | honors `showHeader/showFooter` | always renders both | no | published output contradicts editor |
| navigation pages | shared helper | shared helper | mostly | CTA exclusion consistent |
| footer link resolution | site-chrome renderer | duplicated runtime logic | partial | drift/fallback differences |
| button actions | shared validation/action helper | shared helper | yes | safe HTTPS/page/message behavior |
| layout/block renderer | builder renderer | independent runtime renderer | partial | feature drift risk |
| forms | editor preview handlers | independent runtime form | partial | fallback/type drift |
| reservations | builder configuration | dedicated runtime block | partial | config/runtime drift |
| cache | in-memory editor | public no-store fetch | acceptable | response lacks version metadata |

## 14. Pages and Navigation

Page IDs, default page, slugs, ordering, navigation labels, and visibility are represented on the page object. Shared navigation helpers are a positive consolidation. Publish validation catches duplicate/reserved slugs and invalid defaults.

The destructive internal-name filter is the largest page risk. Slug normalization also silently rewrites duplicates by suffix during normal cleaning, which can alter URLs without an explicit migration. Empty page arrays are replaced with starter pages. Footer navigation remains a newline-delimited string rather than stable page references, so labels can become stale and localization/rename behavior is heuristic.

## 15. Sections, Layout, and Blocks

The builder supports rows/columns and direct/free layout, responsive positions, measured frames, drag/resize, and shared block actions. Block IDs are globally repaired and publish-validated. Valid direct-mode empty rows are preserved by current branch logic.

Risks include random repair IDs, incomplete ID validation below block level, conversion of all loaded layouts to direct layout version 4, duplicated builder/runtime renderers, and repeated whole-project transformations during interaction. Selection is local, but active IDs are still embedded in the editor project. A compatibility effect can call `cleanBuilderProject` whenever it detects old layout, making migration implicit.

## 16. Forms and Workflows

Form IDs and `connectedFormId` are normalized to strings. Backend publish validates referenced forms and public submission verifies both the published form and a published form block. Public validation enforces required/known fields and payload limits; submissions are tenant/project/form scoped.

Weaknesses:

- Form responses embedded in old schemas are always cleared; durable submissions live separately, but UI code still contains response-based assumptions.
- Form field IDs are not repaired/validated globally, weakening merge/UI identity.
- Builder form preview is a separate implementation from public runtime.
- Workflows, roles, users, and collections are persisted largely as trusted JSON; backend publish has little semantic validation for their internal references.
- Collection records are unconditionally removed by routine cleaner, which is destructive if they are legitimate content.

## 17. Reservations

Reservations have the strongest domain persistence: service-role-only table access, tenant/project/block scoping, collision checks, idempotency hashes, cancellation token hashes, time validation, rate limits, field snapshots, and management-route tenant checks. Public events resolve blocks from published schema, so draft-only configuration cannot accept bookings.

The main architectural risk is inherited from public project selection: forms and reservation events target the tenant's latest published project, not a project explicitly bound to the subdomain. Reservation block configuration also remains arbitrary JSON with limited publish-time semantic validation. Project hard deletion cascades durable reservations.

## 18. Assets and Uploads

Uploads require builder write access, are tenant-directory scoped, rate limited, limited to 5 MB PNG/JPEG/WebP, validate declared type and magic bytes, reject SVG/path traversal, generate UUID filenames, and record audit events. URL validators accept only managed upload paths or safe remote URLs.

There is no durable asset registry or project association. Assets are not reference-counted, archived, or cleaned when projects change, so orphaned public files accumulate. The upload API does not send/validate the builder client-contract header used for other builder mutations. Settings duplicates upload validation/client code rather than sharing the builder API end-to-end.

## 19. Backend and Database

The canonical update route checks authenticated tenant membership/write access, archived status, expected revision, size and URL safety, then conditionally replaces the full draft and increments revision. Published schema is not updated. The publish RPC is service-role only and atomic. Form/reservation tables have useful tenant/project indexes and cascade FKs.

Database weaknesses:

- `builder_projects` grants authenticated users direct insert/update/delete under broad tenant-member RLS. These policies allow direct column updates that bypass backend expected-revision, client-contract, schema validation, entitlement, audit, and archive semantics.
- No composite index matches public lookup `(tenant_id, status, last_published_at desc)` or builder list `(tenant_id, status, updated_at desc)`.
- Direct owner/admin delete cascades submissions and reservations, while the product route uses archive.
- Draft JSON has only size/URL checks on save; most schema integrity is deferred to publish.

## 20. Security

Positive controls include tenant-scoped backend queries, non-distinguishing cross-tenant 404s, CSRF-aware authenticated writes, client-contract gating, upload hardening, public rate limits/honeypots/body limits, action URL scheme checks, service-role-only reservation storage, hashed audit identifiers, and no raw HTML/script/iframe publishing.

Highest-risk issue: authenticated direct table access can bypass the backend control plane. A tenant member with a valid Supabase access token and project ID can update protected columns inside their tenant. This is not a cross-tenant break, but it is a concrete integrity, publishing, and audit bypass. The remediation must preserve required read access while revoking direct mutations or moving them behind constrained RPCs.

No concrete stored-XSS route was proven: React escapes text, unsafe URL schemes are rejected, and unsafe element types are blocked at publish.

## 21. Performance and Lifecycle

- `PageBuilder.jsx` is 212 KB/5,774 lines and owns editing, persistence, recovery, conflict, publish, forms, reservations, assets, and most inspector UI.
- Every project change can invoke whole-schema cleaning and multiple `JSON.stringify` traversals; large drafts make keystroke/render effects O(schema size).
- Recovery maintains a 7-second timer, 120-second interval, blur/pagehide/visibility listeners, BroadcastChannel, and storage listener in addition to autosave scheduling.
- Public runtime and builder renderers duplicate substantial logic.
- Lint reports three missing hook dependencies in `TenantSiteRuntime` (`activePage`, `isPublicRuntime`, `goToPage`), indicating stale-closure risk.
- Production build warns of chunks over 500 KB; CSS output includes a 533 KB Page Builder chunk and 980 KB global chunk, with a 523 KB Three.js vendor chunk.
- The initial-project request map deduplicates StrictMode GETs but is module-global and keyed only by user ID/project ID; completed/error entries are removed.

## 22. Dead and Legacy Code

| Symbol/path | Used? | Safe to remove? | Evidence |
|---|---:|---:|---|
| V4 Page Builder storage | yes, outside normal editor | no, not yet | Settings/Dashboard/Archive/demo still read/write it |
| `persistBuilderProject` browser `:backup` path | effectively unreachable in normal PageBuilder | likely after tests/migration | caller passes `writeBrowserDraft: demoMode`, while write requires `!demoMode` |
| V5 `:backup` cleanup | cleanup only | yes after legacy policy | no active V5 writer |
| local browser revision counters | advisory only | likely | not backend authority but included in messages |
| user-scoped compatibility builder routes | used by compatibility/tests | staged removal only | aliases remain in backend |
| legacy field type maps | used | no | runtime/forms/selectors compatibility |
| `SettingsPage.readBuilderProject` | used | must replace, not simply delete | visible site form initializes from V4 |
| Archive V4 workspace label | used | replaceable | not tied to routed/backend project |

## 23. Test Coverage and Test-Quality Gaps

The suite is broad at helper and backend-route level, but shallow at the real mounted lifecycle boundary.

- There is no permanent test mounting the complete PageBuilder, performing one real edit through the UI, allowing the actual autosave effect to run, and asserting network requests/status/recovery.
- Coordinator tests call the coordinator directly; they do not include PageBuilder effects, normalization, refs, and hooks together.
- API/backend mocks return the exact submitted object, preserving key order. They do not emulate PostgreSQL `jsonb` key reordering.
- Runtime flow tests exercise exported pure helpers, not the explicit preview route or full header/footer rendering.
- Public-site tests explicitly assert “latest published project,” cementing the ambiguous behavior instead of testing a project-site binding.
- Route tests mock PageBuilder and do not test preview navigation.
- No browser E2E covers clean load -> edit -> autosave -> refresh -> Go Live -> public render.
- No multi-project public-site test proves the intended project for a subdomain.
- Recovery tests do not assert byte/semantic preservation across destructive page names or missing IDs.
- No test asserts legitimate pages named Reports/Orders/Responses survive normalization.
- StrictMode coverage exists for recovery hook stability, not the entire mounted editor/save/publish chain.

This explains why 228 green frontend tests coexist with real-browser failures.

## 24. Findings Register

### [PB-001] Order-sensitive snapshot identity can reject a successful cloud acknowledgement

- Severity: P1
- Confidence: High
- Area: Persistence/recovery/publish
- Files/functions: `PageBuilder.jsx` `getAutosaveSnapshot`, normal/merged acknowledgement checks; `PageBuilder.recovery.js`; `PageBuilder.publishState.js`
- Evidence: raw `JSON.stringify` is used as identity, and save throws when returned `draft_schema` string differs from submitted object.
- Reproduction: return a semantically equal acknowledgement with reordered object keys after a successful PUT.
- User impact: false `Save failed`, stale recovery, unnecessary rebase/flush, refresh/Incognito appears to repair it.
- Data/security impact: backend data is saved, but retries can create conflicts and user distrust.
- Root cause: serialization order is treated as schema identity across a `jsonb` boundary.
- Minimal fix direction: one canonical semantic hash/stable serialization; use it for acknowledgement, dirty, recovery, publish, and queue equality.
- Required tests: mounted save with reordered response; equivalent recovery; clean publish after reordered acknowledgement.
- Dependencies: canonical persistable contract.

### [PB-002] Routine cleanup deletes legitimate pages by display name

- Severity: P1
- Confidence: High
- Area: Hydration/normalization
- Files/functions: `PageBuilder.project.js::cleanBuilderProjectWithRepairs`; `PageBuilder.copy.js::internalPageNames`
- Evidence: all non-first pages named Responses, Reports, Orders, Submit Request, Submit Report, or Place Order are filtered out.
- Reproduction: load a valid three-page schema with a second page named Reports.
- User impact: page disappears and a later save makes loss durable.
- Data/security impact: direct content loss.
- Root cause: legacy template cleanup is applied by name during every routine clean.
- Minimal fix direction: version-gated explicit migration using stable legacy IDs/markers.
- Required tests: round trips for every listed legitimate page name and footer label.
- Dependencies: schema migration policy.

### [PB-003] Authenticated RLS mutations bypass backend concurrency and publish controls

- Severity: P1
- Confidence: High
- Area: Database/security
- Files/functions: migration 024 builder project grants and RLS policies
- Evidence: authenticated tenant members have table insert/update/delete, with no column/revision constraint.
- Reproduction: use a valid tenant member Supabase token to update `draft_revision`, `published_schema`, `status`, or delete a project directly.
- User impact: corrupted drafts/live state outside normal UI.
- Data/security impact: integrity, audit, entitlement, and cascade-delete bypass within tenant.
- Root cause: broad CRUD RLS predates the backend-only mutation contract.
- Minimal fix direction: revoke direct mutations; expose narrow RPCs only if direct client writes are required.
- Required tests: authenticated REST mutation denied; backend service mutation succeeds.
- Dependencies: deployment/client audit.

### [PB-004] Subdomain resolves the tenant's latest published project, not a bound project

- Severity: P1
- Confidence: High
- Area: Publishing/public runtime/forms/reservations
- Files/functions: `public_site_routes.py::get_latest_published_project_for_tenant`
- Evidence: query filters tenant/status and orders by `last_published_at desc`; no project binding exists in website settings.
- Reproduction: publish project A, then project B in one tenant; the same subdomain, form, and reservation endpoints switch to B.
- User impact: wrong site or form can appear after publishing another project.
- Data/security impact: same-tenant content exposure/misdirected submissions.
- Root cause: multi-project editing was added without a site-to-project relation.
- Minimal fix direction: explicit active/published project ID on site settings with transactional publish binding.
- Required tests: two projects/one tenant; subdomain remains bound; form/reservation target bound project.
- Dependencies: schema decision/migration.

### [PB-005] Explicit-project draft preview uses a legacy project-less base path

- Severity: P1
- Confidence: High
- Area: Routing/preview
- Files/functions: `TenantSiteRuntime.jsx` preview base/path; `UserWorkspaceRoutes.jsx`
- Evidence: route is `/page-builder/projects/:projectId/preview/*`, runtime slices/navigates `/page-builder/preview`.
- Reproduction: preview a non-default page or click preview navigation.
- User impact: wrong page resolution or project ID lost.
- Data/security impact: no direct DB impact; misleading pre-publish verification.
- Root cause: route refactor did not update runtime base-path construction.
- Minimal fix direction: derive preview base from params and shared workspace routing helper.
- Required tests: mounted explicit preview default/non-default navigation/refresh.
- Dependencies: none.

### [PB-006] Normalization generates random IDs and time-based slugs during routine processing

- Severity: P1
- Confidence: High
- Area: Schema integrity/conflict
- Files/functions: project normalizers/factories, `repairDuplicateProjectIds`, `normalizeProjectSlug`
- Evidence: missing/duplicate IDs call `createId`; empty slug fallback uses `Date.now()`.
- Reproduction: clean the same malformed source twice and compare outputs.
- User impact: hash drift, false dirty/conflict, unstable references.
- Data/security impact: references can break or duplicate content during repairs.
- Root cause: migration/repair and routine normalization share factories with random defaults.
- Minimal fix direction: deterministic versioned repair with persisted repair action; no ID generation in comparison paths.
- Required tests: same input twice, same output; reference preservation.
- Dependencies: canonical normalization contract.

### [PB-007] Reading emergency recovery can transform or delete its contents

- Severity: P1
- Confidence: High
- Area: Recovery
- Files/functions: `PageBuilder.recovery.js::parseBuilderRecoveryEnvelope`
- Evidence: parser runs `cleanBuilderProject`, inheriting page filtering, layout migration, record clearing, and ID repair.
- Reproduction: store recovery containing a Reports page or malformed ID, then read/export it.
- User impact: recovery download is not the original unsaved work.
- Data/security impact: last-resort local data loss.
- Root cause: validation and migration are conflated.
- Minimal fix direction: validate envelope without mutation; export exact schema; offer explicit migration separately.
- Required tests: recovery preservation for names, unknown fields, missing IDs, and ordering.
- Dependencies: PB-002/PB-006.

### [PB-008] Project lifecycle status is embedded in content schema and drifts after publish/unpublish

- Severity: P1
- Confidence: High
- Area: Snapshot/publish lifecycle
- Files/functions: `getDraftProjectFromRecord*`, `publishProject`, `unpublishProject`
- Evidence: GET injects record `status` into draft; publish updates record but not project; unpublish gates on project status and sets acknowledged snapshot without changing backend draft.
- Reproduction: publish a draft without refresh, attempt unpublish, then compare local/backend draft hashes.
- User impact: action availability and save readiness differ before/after refresh.
- Data/security impact: redundant metadata contaminates draft identity.
- Root cause: server row lifecycle and content schema are not separated.
- Minimal fix direction: exclude all server metadata from persistable schema; derive lifecycle only from record.
- Required tests: publish/unpublish immediately without refresh and stable draft hash.
- Dependencies: snapshot contract.

### [PB-009] Public runtime ignores header/footer visibility flags

- Severity: P2
- Confidence: High
- Area: Builder/runtime parity
- Files/functions: `PageBuilder.siteChrome.jsx`; `TenantSiteRuntime.jsx::renderHeader/renderFooter`
- Evidence: builder renderer checks `showHeader/showFooter`; runtime has no checks and renders both.
- Reproduction: disable header/footer, publish, open public site.
- User impact: live site differs from preview/configuration.
- Data/security impact: possible unintended contact/navigation exposure.
- Root cause: duplicated renderers.
- Minimal fix direction: shared site-chrome renderer/contract.
- Required tests: all visibility combinations in mounted public runtime.
- Dependencies: runtime consolidation.

### [PB-010] Project chooser silently omits projects after the first 20

- Severity: P2
- Confidence: High
- Area: Routing/project selection
- Files/functions: `listBuilderProjects`, backend pagination, `BuilderProjectChooser`
- Evidence: frontend sends no limit/offset and ignores pagination; backend default is 20.
- Reproduction: tenant with 21 active projects.
- User impact: older projects cannot be opened from chooser.
- Data/security impact: none.
- Root cause: pagination contract not consumed.
- Minimal fix direction: paginated chooser/search or explicit project links.
- Required tests: 21+ projects and auto-open logic.
- Dependencies: none.

### [PB-011] Settings, Dashboard, and Archive retain V4 browser-project authority

- Severity: P2
- Confidence: High
- Area: Legacy/state ownership
- Files/functions: `SettingsPage.readBuilderProject/saveSiteSettings`, `UserDashboard.getLocalProject`, `ArchivePage.getArchiveWorkspaceName`
- Evidence: all read V4 localStorage; Settings writes a full local project after website-settings PUT.
- Reproduction: edit cloud project on another device, open Settings/Dashboard/Archive in stale browser.
- User impact: stale branding/statistics/workspace name and Incognito differences.
- Data/security impact: local copy is not cloud-saved but appears authoritative.
- Root cause: partial server-first migration.
- Minimal fix direction: load website settings/backend project explicitly; remove V4 from non-demo product surfaces.
- Required tests: clean browser/cross-device settings/dashboard.
- Dependencies: site/project authority decision.

### [PB-012] Website branding has two overlapping authorities with different precedence

- Severity: P2
- Confidence: High
- Area: Website settings/site chrome
- Files/functions: SettingsPage, PageBuilder site chrome, TenantSiteRuntime merge
- Evidence: runtime merges website settings then lets `draft_schema.siteChrome` override; Settings updates website table and V4 project, not routed cloud draft.
- Reproduction: set different brand/logo in builder and Settings.
- User impact: editor, preview, and public site can show different values.
- Data/security impact: stale contact/logo can be published or displayed.
- Root cause: shared fields lack one ownership/read model.
- Minimal fix direction: define field-level authority and use one explicit adapter.
- Required tests: precedence matrix and settings hydration with zero draft writes.
- Dependencies: product decision.

### [PB-013] Save coordinator is not the sole owner of save lifecycle state

- Severity: P2
- Confidence: High
- Area: Persistence architecture
- Files/functions: `PageBuilder.jsx`, `PageBuilder.saveCoordinator.js`
- Evidence: coordinator state is mirrored by active/pending snapshot, promise, in-flight, operation, record, revision, base, conflict, and save-state refs in PageBuilder.
- Reproduction: save/rebase/adoption while project effects and publish preparation rerender.
- User impact: stale status/queue symptoms are difficult to reason about.
- Data/security impact: increased duplicate/conflict risk.
- Root cause: coordinator added beneath existing orchestration rather than owning it.
- Minimal fix direction: coordinator-owned immutable status snapshot and canonical acknowledgement API.
- Required tests: full mounted editor races, not direct helper calls.
- Dependencies: PB-001/PB-008.

### [PB-014] Recovery cross-tab channel sends full schemas and maintains obsolete local revision counters

- Severity: P2
- Confidence: High
- Area: Recovery/cross-tab/performance
- Files/functions: `useDebouncedProjectStorage`
- Evidence: messages contain `serializedProject`, browser `revision`, base revision, and timestamp; backend 409 is the actual concurrency authority.
- Reproduction: open same project in two tabs and inspect messages/listeners.
- User impact: confusing “newer draft” notices and extra serialization.
- Data/security impact: content is copied to every same-origin listening tab.
- Root cause: browser synchronization predates advisory-only policy.
- Minimal fix direction: advisory presence/version metadata only; recovery stays scoped localStorage.
- Required tests: messages cannot affect content/revision/conflict.
- Dependencies: recovery redesign.

### [PB-015] ID integrity stops at page/form/block level

- Severity: P2
- Confidence: High
- Area: Schema/merge/layout/forms
- Files/functions: `repairDuplicateProjectIds`, backend publish ID validation, merge ID arrays
- Evidence: section/row/column/field/workflow/role/collection IDs are not globally repaired/validated.
- Reproduction: duplicate field or row IDs across a project and perform merge/render.
- User impact: unstable React keys, coarse conflicts, ambiguous inspector references.
- Data/security impact: wrong entity may be selected/resolved.
- Root cause: incomplete stable-identity contract.
- Minimal fix direction: define scope/uniqueness for every identifiable entity and validate versionedly.
- Required tests: duplicates/missing IDs at every level.
- Dependencies: schema contract.

### [PB-016] Explicit empty page collections are replaced by starter content

- Severity: P2
- Confidence: High
- Area: Normalization
- Files/functions: `normalizeBuilderProjectShape`
- Evidence: empty `pages` uses `fallback.pages`.
- Reproduction: hydrate `{pages: []}`.
- User impact: deleted/empty site appears repopulated and can later be saved.
- Data/security impact: content resurrection.
- Root cause: missing versus intentionally empty is not distinguished.
- Minimal fix direction: fallback only for explicit new-project creation or absent legacy field.
- Required tests: absent vs empty pages.
- Dependencies: schema versioning.

### [PB-017] Public response lacks project/version identity and explicit cache contract

- Severity: P2
- Confidence: Medium
- Area: Runtime/cache/diagnostics
- Files/functions: public site route and `fetchPublicSite`
- Evidence: response exposes only `published_schema`; frontend sets request `no-store`, backend does not expose published version in response.
- Reproduction: inspect successful publish/public GET contracts.
- User impact: difficult stale-cache diagnosis and cache-safe open-live behavior.
- Data/security impact: low.
- Root cause: minimal initial public contract.
- Minimal fix direction: return safe project/version/last-published metadata and explicit cache headers/ETag.
- Required tests: republish/refetch/version transition.
- Dependencies: PB-004.

### [PB-018] Asset lifecycle has no registry, ownership reference, or cleanup

- Severity: P2
- Confidence: High
- Area: Assets/storage
- Files/functions: builder asset upload route/filesystem paths
- Evidence: generated files are returned as URLs but no asset row/project reference is persisted.
- Reproduction: upload assets, replace/delete blocks/projects, inspect files.
- User impact: orphan accumulation and no asset management.
- Data/security impact: public stale assets remain accessible by URL.
- Root cause: uploads are filesystem-only.
- Minimal fix direction: tenant asset registry, reference tracking, retention policy.
- Required tests: reference lifecycle/archive/delete and unauthorized lookup.
- Dependencies: storage design.

### [PB-019] Builder client contract is inconsistent across builder mutations

- Severity: P2
- Confidence: High
- Area: API compatibility
- Files/functions: `uploadBuilderAsset`; submission status APIs/routes
- Evidence: project create/update/publish use `cloud-draft-v1`; asset multipart and other builder mutations omit it.
- Reproduction: enable enforcement and inspect mutation headers/routes.
- User impact: rollout assumptions are incomplete.
- Data/security impact: obsolete clients retain some mutation capability.
- Root cause: contract enforcement is route-specific.
- Minimal fix direction: explicitly scope/document contract or enforce across all intended builder mutations.
- Required tests: mutation matrix under enforcement.
- Dependencies: rollout policy.

### [PB-020] Whole-schema cleaning/stringification runs on high-frequency editor changes

- Severity: P2
- Confidence: High
- Area: Performance
- Files/functions: PageBuilder project effect, `saveProject`, coordinator `getLatestEntry`, recovery hook
- Evidence: repeated full clean and JSON serialization from a large project object on project changes.
- Reproduction: type/drag in a large schema and profile main thread.
- User impact: input latency and poor large-site scaling.
- Data/security impact: none.
- Root cause: monolithic schema and snapshot comparison.
- Minimal fix direction: stable canonical snapshots at mutation boundaries, incremental dirty versions, worker hashing if needed.
- Required tests: performance budget with large fixture.
- Dependencies: snapshot contract.

### [PB-021] PageBuilder and public runtime are independent, oversized render systems

- Severity: P2
- Confidence: High
- Area: Maintainability/runtime parity
- Files/functions: `PageBuilder.jsx`, `TenantSiteRuntime.jsx`, runtime/siteChrome renderers
- Evidence: separate element/header/footer/form/layout implementations and 285 KB of primary source.
- Reproduction: compare feature flags/props between renderers; header/footer mismatch is one result.
- User impact: preview/live drift and slower fixes.
- Data/security impact: configuration may be exposed/hidden differently.
- Root cause: no shared render contract/component layer.
- Minimal fix direction: shared pure view models and block/site-chrome renderers.
- Required tests: parity fixtures per block and viewport.
- Dependencies: phased architecture work.

### [PB-022] Runtime hooks have known stale-dependency risks

- Severity: P2
- Confidence: High
- Area: Runtime lifecycle
- Files/functions: `TenantSiteRuntime.jsx` lines reported by ESLint
- Evidence: missing `activePage`, `isPublicRuntime`, and `goToPage` dependencies.
- Reproduction: change auth/page/runtime mode without remount.
- User impact: stale redirects/action behavior in edge transitions.
- Data/security impact: authentication navigation can be stale.
- Root cause: large component with unstable inline callbacks.
- Minimal fix direction: stable callbacks/complete dependency lists after behavior tests.
- Required tests: auth transitions and page changes without remount.
- Dependencies: runtime consolidation.

### [PB-023] Backend query indexes do not match primary list/public lookup patterns

- Severity: P2
- Confidence: Medium
- Area: Database performance
- Files/functions: migration 024 indexes; builder/public queries
- Evidence: separate tenant/status/slug indexes, but ordered compound filters lack compound indexes.
- Reproduction: explain analyze with many projects per tenant.
- User impact: slower chooser/public site as data grows.
- Data/security impact: none.
- Root cause: initial small-scale indexes.
- Minimal fix direction: measure and add matching composite indexes if proven.
- Required tests: query plans/benchmarks.
- Dependencies: production metrics; migration only after proof.

### [PB-024] V5 backup cleanup and browser persistence branch are legacy dead weight

- Severity: P3
- Confidence: High
- Area: Dead code
- Files/functions: `persistBuilderProject`, `clearBuilderRecovery`, V4 storage helpers
- Evidence: normal PageBuilder cannot satisfy `!demoMode && writeBrowserDraft` with current caller; V5 never writes `:backup`.
- Reproduction: trace all callers/writers.
- User impact: maintainability/confusion.
- Data/security impact: low.
- Root cause: partial browser-first removal.
- Minimal fix direction: remove only after V4 consumers are migrated.
- Required tests: demo and recovery export/discard.
- Dependencies: PB-011.

### [PB-025] Build size and CSS duplication are uncontrolled

- Severity: P3
- Confidence: High
- Area: Performance/build
- Files/functions: Page Builder styles/import graph, Three.js dependency
- Evidence: build warning; 533 KB Page Builder CSS, 980 KB global CSS, 523 KB Three vendor chunk.
- Reproduction: production Docker build.
- User impact: slower initial/editor loads.
- Data/security impact: none.
- Root cause: broad imports and monolithic style bundles.
- Minimal fix direction: route-scoped styles, feature lazy loading, dependency budget.
- Required tests: bundle budget.
- Dependencies: architecture split.

### [PB-026] Current tests overuse helper mocks and miss the real lifecycle boundary

- Severity: P3
- Confidence: High
- Area: Test quality
- Files/functions: frontend Page Builder test suite
- Evidence: 228 tests pass without a full mounted edit/autosave/publish/public scenario; response mocks preserve submitted ordering.
- Reproduction: inventory tests and compare to reported browser sequence.
- User impact: regressions reach manual testing despite green CI.
- Data/security impact: indirect reliability risk.
- Root cause: unit coverage grew faster than end-to-end integration coverage.
- Minimal fix direction: a small number of high-fidelity mounted/browser scenarios.
- Required tests: see Section 23 and manual matrix.
- Dependencies: stable test API fixture.

## 25. Cross-Cutting Root Causes

1. Compatibility migrations run as routine normalization rather than explicit, versioned operations.
2. Object serialization is used as identity without a canonical serialization contract.
3. Multi-project editing was added without an explicit site-to-project data model.
4. Server-first persistence was added while V4 consumers and mirrored lifecycle refs remained.
5. Builder preview and public runtime are separate implementations.
6. Tests target helpers/routes but not the complete browser lifecycle and real `jsonb` boundary.

## 26. Prioritized Remediation Plan

### Phase A: data integrity and save correctness

1. Introduce one stable semantic snapshot/hash and canonical acknowledgement operation.
2. Add reordered-`jsonb` mounted regression tests.
3. Remove server lifecycle metadata from draft content.
4. Version-gate normalization; immediately stop page-name deletion and random routine repairs.
5. Make recovery parsing non-mutating.
6. Revoke direct authenticated builder-project mutations or constrain them with RPCs.

### Phase B: publish/runtime correctness

1. Define and persist explicit subdomain-to-project binding.
2. Fix explicit preview base path.
3. Share header/footer visibility and navigation view models.
4. Return published version metadata and define cache headers.
5. Add publish/unpublish without-refresh tests.

### Phase C: forms/reservations/assets

1. Extend stable ID validation to fields/layout/workflows/roles/collections.
2. Validate internal workflow/role/collection references.
3. Ensure public forms/reservations use bound project.
4. Add asset registry/retention and clarify client-contract scope.

### Phase D: architecture simplification

1. Migrate Settings/Dashboard/Archive off V4 storage.
2. Make the save coordinator own a single immutable status/acknowledgement snapshot.
3. Separate editor-local state from the persisted project object.
4. Split PageBuilder by domain and share runtime render components.

### Phase E: performance and cleanup

1. Profile large schemas and reduce whole-schema work.
2. Fix runtime hook dependencies.
3. Add pagination to chooser.
4. Remove proven V4/backup/dead helpers.
5. Add bundle budgets and route-scoped CSS/code splitting.

## 27. Suggested Commit Breakdown

No commits were created. Suggested future sequence:

1. Tests: semantic snapshot/jsonb-order regressions.
2. Persistence: canonical hash and acknowledgement adoption.
3. Integrity: versioned normalizer and recovery preservation.
4. Database security: revoke direct mutation/RPC policy.
5. Data model: site-to-project binding plus backend/public tests.
6. Runtime: explicit preview routing and site-chrome parity.
7. Legacy: Settings/Dashboard/Archive server-first migration.
8. Architecture/performance cleanup.

## 28. Manual Browser Test Matrix

| Scenario | Assertions |
|---|---|
| Clean explicit load | skeleton, one GET, zero PUT, no V4/recovery influence |
| Normal edit | one PUT, Saved, recovery clears, stable after 60 seconds |
| JSON key reorder | server returns reordered equal schema; still Saved, no retry |
| Edit during save | latest content serialized once after first acknowledgement |
| Non-overlap concurrency | one 409, GET, merged PUT, Saved, both changes |
| Overlap concurrency | no overwrite; review UI; newest revision on resolution |
| Clean Go Live | zero draft PUT; one publish; published version returned |
| Dirty Go Live | one needed save then one publish |
| Publish/unpublish | works immediately without refresh; draft hash unchanged |
| Two projects/tenant | subdomain remains explicitly bound; forms/bookings follow binding |
| Preview routes | default/non-default refresh/navigation preserve project ID |
| Header/footer | all four visibility combinations match live output |
| Destructive names | Reports/Orders/Responses pages survive load/save/publish |
| Recovery | exact unsaved schema downloads; never auto-applies; equal copy clears |
| Cross-device settings | builder/settings/dashboard show same backend-authoritative values |
| Assets | upload/replace/archive lifecycle and old URL policy |
| Forms/reservations | published-only config, correct project, validation/idempotency |

## 29. Open Questions

1. Is one website/subdomain intended to bind to exactly one builder project, or should each project have its own site address?
2. Are `collections.records` and embedded form responses intentionally local-only, or are they legitimate schema content?
3. Which `siteChrome` fields should website settings own versus the project draft?
4. Must authenticated clients ever write `builder_projects` directly through Supabase?
5. Is a truly empty site/pages list valid?
6. What is the supported compatibility lifetime for V4 browser projects and user-scoped backend aliases?
7. Should unpublish preserve public availability of the last snapshot or take the site offline (current status filter takes it offline while retaining snapshot)?

## 30. Final Recommendation

Do not expand Page Builder features until Phase A is complete. The backend revision/publish primitives are adequate; the urgent work is to make frontend schema identity semantic, stop destructive routine normalization, close the direct database mutation bypass, and define explicit public project binding. Then fix preview/runtime parity and migrate the remaining V4 consumers. A small high-fidelity browser suite should gate each phase. The current green unit/backend suite is necessary but not sufficient evidence of cross-device save or publish correctness.

Validation results:

- Frontend: 39 files, 228 tests passed.
- Lint: 0 errors, 3 retained `TenantSiteRuntime` hook dependency warnings.
- Backend image build: passed.
- Backend: 535 tests passed.
- Hard outbound socket guard: `EXTERNAL_ATTEMPTS []`; no SSL `ResourceWarning` observed.
- Frontend Docker build: passed; retained chunk-size warning.
- Migrations: 48/48, 0 errors, 2 known historical duplicate warnings.
- `git diff --check`: passed before report creation.

## Post-audit button color contract (2026-07-31)

The later button-color follow-up adds five optional, explicit button fields:
`backgroundColor`, `textColor`, `hoverBackgroundColor`, `hoverTextColor`, and
`borderColor`. Each accepts only a normalized six-digit hexadecimal value.
Empty values are removed; shorthand, alpha, CSS variables/functions,
declarations, HTML, and arbitrary `style`/`buttonColors` objects are rejected by
the backend draft and publish validators. Existing `styles.color` and
`styles.backgroundColor` theme defaults remain unchanged for old buttons.

`ButtonColorControls` provides a native color picker, text entry, and clear
action with programmatic labels and a non-blocking WCAG-style 4.5:1 contrast
warning for normal and hover pairs. The shared presentation helper is consumed
by both the editor renderer and `TenantSiteRuntime`, so draft preview, responsive
preview, standard-path publication, and branded-host publication use the same
validated fields. Hover overrides exclude disabled controls, and the existing
`:focus-visible` outline remains authoritative.
