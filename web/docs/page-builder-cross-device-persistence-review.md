# Page Builder Cross-Device Persistence Review

## 1. Executive Summary

The primary cause is that browser storage currently overrides the backend whenever a local draft exists.

The editor starts from a full project cached under a key scoped only by user ID:

```text
madar_app_builder_frontend_v4:user:<user_id>
```

It does not include tenant ID or backend project ID. During backend hydration, the editor deliberately refuses to apply the server draft if that local key exists. It nevertheless associates the local project with the newest backend project record. This can cause stale or unrelated local data to be displayed and subsequently autosaved over the backend project.

The five most important findings are:

1. Critical: a user-scoped local draft silently wins over the backend draft.
2. Critical: the local key is not scoped by tenant or project, while the backend supports multiple projects.
3. High: the builder always selects `projects[0]`, ordered by most recently updated, instead of opening an explicit project ID.
4. High: autosave can skip the seven-second save while an input or drag is active, then wait up to two minutes or until blur; browser close only guarantees local persistence.
5. High: Settings writes builder-like header/footer data to an obsolete unscoped localStorage key, not to the backend `draft_schema`.

A secondary data-loss risk exists in normalization: pages with names such as “Reports”, “Orders”, or “Submit Request” can be removed by name, and all sections are rewritten into a single direct-layout canvas.

Git state was clean throughout the review:

- Branch: `builder-backend`
- Ahead/behind `origin/main`: `0 / 0`
- Preserved stash: `stash@{0}`
- No files modified

## 2. Canonical Storage Source

Intended canonical source:

- `public.builder_projects.draft_schema`

Actual editor precedence:

1. User-scoped browser draft
2. Browser backup if the primary browser draft is unreadable
3. Blank defaults
4. Backend draft only if no browser draft existed when loading started
5. Tenant website settings subsequently patch the subdomain

Therefore, browser storage is currently the practical canonical source on any device that has opened the builder before.

The critical decision appears in `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`:

- It records whether any local value exists.
- It fetches the most recently updated backend project.
- It assigns the backend record to `builderProjectRecord`.
- It applies the backend schema only when there was no local draft and no local edit during loading.

This policy is unsafe for cross-device use.

## 3. Storage Inventory

| Configuration/state | Browser storage | React-only | Backend/API field | Database column | Cross-device expected? |
|---|---|---:|---|---|---:|
| Project name | Full local draft | No | `draft_schema.name`, request `name` | `name`, `draft_schema` | Yes |
| Project slug | Full local draft | No | Request `slug`, schema slug | `slug`, `draft_schema` | Yes |
| Pages and order | Full local draft | No | `draft_schema.pages` | `draft_schema` | Yes |
| Page IDs/names/slugs | Full local draft | No | `draft_schema.pages[]` | `draft_schema` | Yes |
| Default page | Full local draft | No | `draft_schema.defaultPageId`, `isDefault` | `draft_schema` | Yes |
| Header navigation visibility | Full local draft | No | `showInNavigation` | `draft_schema` | Yes |
| Sections/rows/columns | Full local draft | No | Nested page schema | `draft_schema` | Yes |
| Free blocks and content | Full local draft | No | `freeElements` | `draft_schema` | Yes |
| Block styles/actions | Full local draft | No | Nested element fields | `draft_schema` | Yes |
| Desktop/tablet/mobile positions | Full local draft | Preview viewport only | `element.position` | `draft_schema` | Yes |
| Per-viewport canvas heights | Full local draft | No | `minHeightByViewport` | `draft_schema` | Yes |
| Theme, colors, fonts, radius | Full local draft | No | `draft_schema.theme` | `draft_schema` | Yes |
| Header/footer configuration | Full local draft plus obsolete Settings key | No | `draft_schema.siteChrome` | `draft_schema` | Yes |
| Subdomain | Full draft copy | No | Website settings API | `website_settings.subdomain` | Yes |
| Brand/logo/contact details | Obsolete Settings local key | No | Website settings API and `siteChrome` | `website_settings` and `draft_schema` | Yes |
| Forms and fields | Full local draft | Form editing UI state | `draft_schema.forms` | `draft_schema` | Yes |
| Form connections | Full local draft | No | `connectedFormId` | `draft_schema` | Yes |
| Form responses | Removed from saved schema | Runtime answers | Submission API | `builder_form_submissions` | Yes, as operational data |
| Reservation configuration | Full local draft | Temporary form state | Reservation block fields | `draft_schema` | Yes |
| Reservation records | No | Submission state | Reservation API | `builder_reservations` | Yes |
| Workflows | Full local draft | Active selection | `draft_schema.workflows` | `draft_schema` | Yes |
| Roles/users configured in builder | Full local draft | Active selection | `draft_schema.roles/users` | `draft_schema` | Yes |
| Collections definitions | Full local draft | No | `draft_schema.collections` | `draft_schema` | Yes |
| Collection records | Removed during cleaning | Possibly UI state | No durable builder record API found | Not in project after cleaning | Depends on intended product model |
| Uploaded asset URL | Full local draft | Upload progress | URL in element/site chrome | `draft_schema`; asset on server storage | Yes |
| Draft status | Full local draft | No | Project response | `status` | Yes |
| Draft revision | Not included in local recovery envelope | Record state/ref | `draft_revision` | `draft_revision` | Yes |
| Published snapshot | Not used for editing | No | Publish API | `published_schema` | Yes |
| Published revision/version | No | Record state | Publish API | `published_revision`, `published_version` | Yes |
| Active page/form/workflow/role IDs | Full local draft | Also drives editor selection | Nested schema | `draft_schema` | No; should be user/device preference |
| Selected block/section | No | Yes | None | None | No |
| Active tab/design panel | URL/React | Yes | None | None | No |
| Viewport preview | No | Yes, defaults to desktop | None | None | No |
| Preview mode | No | Yes | None | None | No |
| Modal/open inspector state | No | Yes | None | None | No |
| Drag/resize transient state | No | Yes | None | None | No |
| Undo/redo/form toolbar state | No durable project history | Yes/browser history | None | None | No |
| Runtime form answers/errors | No | Yes | Submission API after submit | Submission tables | No before submission |
| Full browser recovery copy | Primary plus `:backup` | No | None | None | Recovery only |
| Starter-template dismissed state | Global localStorage key | No | None | None | No |
| Data workspace metadata cache | User/project localStorage key | Memory cache | Backend dataset APIs separately | Dataset metadata tables | Cache only |
| Local encrypted datasets/archive | IndexedDB | No | Not synchronized by this mechanism | None | Intentionally device-local |

## 4. Save Pipeline

### Normal builder save

1. Controls call `updateProject`, updating the full React project object.
2. The browser-storage hook observes the new object.
3. After seven seconds, it writes the full project to localStorage and rotates the previous value into `:backup`.
4. Independently, backend autosave schedules after seven seconds.
5. Before sending, `cleanBuilderProjectWithRepairs()` normalizes and rewrites the schema.
6. `createBuilderProjectPayload()` sends:

```json
{
  "name": "...",
  "slug": "...",
  "draft_schema": {},
  "expected_revision": 12
}
```

7. The API client serializes updates per backend project ID.
8. Backend validation accepts a generic nested dictionary, validates size and URLs, then replaces the complete `draft_schema`.
9. The update includes `WHERE draft_revision = expected_revision`.
10. The backend increments `draft_revision`.
11. The frontend stores the returned record and updates its backend snapshot marker.

### What is done correctly

- The entire project object is sent, not only the active page.
- Inactive pages, forms, theme, header/footer, responsive positions, and actions are included.
- Pydantic does not whitelist away nested configuration fields.
- Authenticated project GET returns the complete row.
- API reads use `cache: "no-store"`.
- Optimistic concurrency prevents silent last-write-wins overwrites.
- In-flight saves are serialized and a later pending save is queued.

### Problematic behavior

- Local storage is updated before backend success.
- Local “dirty” state measures browser persistence, not cloud persistence.
- A silent backend failure can leave local storage marked clean while the server remains stale.
- Silent non-revision failures do not show a lasting error.
- The seven-second backend timer returns without rescheduling when dragging or editing an input.
- There is a two-minute retry interval, but a user may switch devices before it runs.
- Blur/visibility save also refuses to run while an input remains focused.
- There is no durable `beforeunload`/send-beacon backend save.
- The UI has “Saving…” during a request, but no persistent cloud state such as “Saved to cloud”, “Unsaved”, or “Save failed”.
- Revision conflicts preserve local work, but there is no reload/compare/recover workflow.

## 5. Load Pipeline

### Actual automatic load precedence

1. `loadInitialProject()` reads the user-scoped localStorage primary value.
2. If unreadable, it reads the user-scoped `:backup`.
3. If neither is usable, it creates a blank project.
4. The backend lists projects ordered by `updated_at DESC`.
5. The frontend selects `projects[0]`.
6. The full project record is fetched.
7. The server draft is normalized.
8. If any local draft existed at startup, the server draft is not applied.
9. The backend record is still assigned to the editor.
10. Website settings are fetched and only the project’s copied subdomain is synchronized.

This means the displayed local schema and the selected backend record can represent different projects.

### Explicit “Load project” behavior

The manual load action is safer:

1. Fetch backend project list.
2. Select the first project.
3. Load its backend draft.
4. Fall back to localStorage only if the backend has no project or fails.

However, automatic initialization is the normal path and uses the opposite effective precedence.

### Other load transformations

`cleanBuilderProject()`:

- Defaults a missing/empty page collection.
- Normalizes IDs and actions.
- Converts layouts to direct mode.
- Merges all page sections into one page canvas.
- Removes certain response-oriented elements.
- Removes pages with reserved legacy names when they are not first.
- Clears embedded form responses.
- Clears collection records.
- Removes selected footer links.
- Repairs duplicate IDs.

Unknown project, page, section, element, form, theme, and site-chrome fields are generally retained through object spreading.

## 6. Browser Storage Findings

### Full builder draft

Defined in `frontend/src/components/PageBuilder/core/PageBuilder.constants.js`:

```text
madar_app_builder_frontend_v4:user:<user_id>
```

Problems:

- No tenant ID
- No backend project ID
- No backend `draft_revision`
- No timestamp envelope
- No expiry
- No server hash
- Anonymous data uses one global anonymous key

### Backup

Stored as:

```text
madar_app_builder_frontend_v4:user:<user_id>:backup
```

Problems:

- Raw project JSON only
- No user/tenant/project metadata beyond the key
- No revision comparison
- No expiry
- Not cleared after a successful backend save
- Manual restore can load an older draft and allow autosave to overwrite the current backend draft

The restore code only asks for confirmation; it does not compare with the server revision.

### Obsolete unscoped builder key

Settings and dashboard code use:

```text
madar_app_builder_frontend_v4
```

`SettingsPage.jsx` reads this unscoped key and writes site configuration back to it.

The main builder does not use that key for an authenticated user. Consequently:

- Settings and Builder can display different project copies.
- Header/footer changes made through Settings are not saved into `builder_projects.draft_schema`.
- They cannot reliably travel to another device through the builder project.
- Public runtime precedence may allow stale `draft_schema.siteChrome` to override newer `website_settings`.

### Cross-tab synchronization

`BroadcastChannel` and the `storage` event synchronize browser tabs only.

They do not synchronize devices, and their revisions are in-memory local revision counters—not backend `draft_revision` values.

### IndexedDB

`madar-sensitive-data` stores datasets and archive items locally, optionally encrypted. This is separate from the builder schema and is inherently device-local.

No Page Builder project configuration was found in `sessionStorage`.

## 7. Project State vs Device State

### A. Must persist across devices

- Project identity and display name
- Pages, order, IDs, slugs, homepage selection
- Navigation visibility
- Sections and all block instances
- Content, styles, actions, media URLs
- Desktop/tablet/mobile positions and sizes
- Theme and form theme
- Header/footer and site chrome
- Forms, fields, pages, validation, localization
- Form connections
- Reservation block configuration
- Workflows
- Roles and configured builder users
- Collection definitions
- Published configuration
- Schema version

These are currently included in `draft_schema`, which is correct.

### B. Device/user preferences

- Active editor tab
- Design panel
- Selected block/section/page
- Preview on/off
- Preview viewport
- Open modal
- Inspector state
- Drag state
- Text selection and toolbar location
- Temporary validation messages
- Runtime preview answers
- Undo/redo stack
- Zoom/sidebar dimensions if added later

Current problem: `activePageId`, `activeFormId`, `activeWorkflowId`, and `activeRoleId` are stored inside the shared project schema. They should be moved to device/user preference state.

### C. Temporary recovery state

- Latest unsaved project snapshot
- Previous local snapshot
- Failed save payload
- Base server revision
- Save error and retry metadata

Current recovery state is an unversioned raw project copy. It needs a structured envelope and explicit recovery UI.

## 8. Autosave and Revision Findings

Autosave timing:

- LocalStorage debounce: 7 seconds
- Backend debounce: 7 seconds
- Backend safety interval: 120 seconds
- Local persistence: blur, pagehide, visibility hidden
- Backend save: blur and visibility hidden, but not while an input/drag is active

The proposed sequence can occur:

1. User edits a field.
2. React state updates.
3. Local and backend saves are scheduled.
4. Backend timer fires while the input is focused and exits.
5. User closes or moves to another device.
6. Browser copy is current, backend remains old.
7. Device B loads the old backend state.

This is likely to be perceived as missing cross-device configuration.

Revision handling is secure but incomplete:

- Backend conflicts return `project_revision_conflict`.
- Local work is retained.
- There is no automatic overwrite.
- There is no rebase/merge or server comparison.
- The stale `builderProjectRecord.draft_revision` remains until reload, so retries continue failing.
- The UI does not clearly separate “saved in this browser” from “saved to Madar”.

## 9. Configuration-Specific Findings

### Pages and page order

Persisted in `draft_schema.pages`.

Risk: the editor always loads the newest backend project rather than a route-selected project.

### Page names, slugs, and default page

Persisted and normalized.

Risk: `withDefaultLandingPage()` resets editor selection to the first page. This changes device-local selection, not site configuration.

### Sections

Persisted, but cleaning merges all sections into one direct canvas. Structural section boundaries are not stable across round trips.

### Blocks

All block properties are sent in the full schema.

Duplicate/missing IDs are repaired. Unknown fields are generally retained.

### Responsive configuration

Desktop/tablet/mobile positions and `minHeightByViewport` are persisted.

The current device chooses which persisted layout to display; it does not normally regenerate layout solely from screen width. This is unlikely to be the principal cross-device cause.

Legacy layout conversion can generate new responsive positions and merge sections during normalization.

### Theme

Persisted in `draft_schema.theme` and covered by generic preservation tests.

### Header/footer

Persisted in `draft_schema.siteChrome`.

Also partially duplicated in `website_settings`, and Settings writes a third copy to obsolete localStorage. This needs a single authority or an explicit synchronization contract.

### Forms

Form definitions and multi-page fields are included in the backend payload.

Form response arrays are intentionally cleared from the schema; durable submissions live in backend tables.

### Reservations

Reservation configuration lives on page blocks inside the project schema.

Reservation records are separate durable backend rows.

### Button actions

Persisted in element actions and normalized to the canonical action shape.

### Images/assets

Uploaded asset URLs persist in the project. The asset binary is server-backed, so it should be available cross-device if the URL was saved successfully.

A local `File` object is not part of the project schema.

### Website settings/subdomain

The subdomain’s durable authority is `website_settings`.

A copy is inserted into `project.publish.subdomain`, creating possible divergence.

### Plans/entitlements

Billing state is backend-owned and not part of builder persistence.

### Builder roles/users/collections

Definitions are persisted in the project JSON. Embedded collection records are deliberately removed during cleaning.

## 10. Cross-Device Root Causes

### 1. Local draft silently overrides backend

- Severity: Critical
- Confidence: High
- Evidence: `PageBuilder.jsx`, backend hydration logic
- Reproduction:
  1. Open a project on Device A to create local storage.
  2. Update the project from Device B/backend.
  3. Reopen Device A.
  4. Device A retains its local copy instead of applying the newer server revision.
- Fix: backend-first loading with explicit revision-aware recovery.

### 2. Storage key omits tenant and project

- Severity: Critical
- Confidence: High
- Evidence: `PageBuilder.constants.js`
- Reproduction:
  1. Use the same account across two tenants or projects.
  2. Open different projects.
  3. Observe both use the same browser key.
- Fix: key by tenant ID and backend project UUID.

### 3. Local schema can be paired with the wrong backend record

- Severity: Critical
- Confidence: High
- Evidence: local state is retained while `builderProjectRecord` is set.
- Impact: later autosave can write the local schema into the backend’s newest project.
- Fix: never attach a local snapshot to a backend record unless project identity and base revision match.

### 4. Backend project selection is implicit

- Severity: High
- Confidence: High
- Evidence: frontend selects `projects[0]`; backend orders by `updated_at DESC`.
- Reproduction: create two projects and change which one was updated most recently.
- Fix: route and load by explicit backend project ID.

### 5. Backend autosave can be deferred or canceled

- Severity: High
- Confidence: High
- Evidence: backend autosave timer in `PageBuilder.jsx`.
- Reproduction: edit while retaining input focus, close before two-minute retry, then open another device.
- Fix: reschedule skipped saves and expose cloud-save state.

### 6. Settings writes to a different browser project

- Severity: High
- Confidence: High
- Evidence: `SettingsPage.jsx`.
- Reproduction: edit branding in Settings, then open Builder on another device.
- Fix: Settings must update the selected backend builder project or only update one canonical website-settings record.

### 7. Normalization deletes configuration by name/type

- Severity: High
- Confidence: High
- Evidence: `PageBuilder.project.js`.
- Affected pages include names such as “Reports”, “Orders”, and “Submit Request”.
- Fix: replace name-based deletion with an explicit schema migration keyed by legacy IDs/version markers.

### 8. Recovery backup can overwrite newer backend work

- Severity: High
- Confidence: High
- Evidence: browser draft restore in `PageBuilder.jsx`.
- Fix: compare backup base revision with current backend revision and require explicit conflict recovery.

### 9. Normalization changes section structure

- Severity: Medium
- Confidence: High
- Effect: sections are converted and merged even when merely loading.
- Fix: migrate once by schema version; avoid destructive normalization on every load/save.

### 10. API caching

- Severity: Low
- Confidence: High that it is not the cause
- Builder project reads explicitly use `cache: "no-store"`.

## 11. Data-Loss Risks

- A stale user-level local draft can overwrite the newest backend project.
- A draft from one tenant can be written into another tenant’s selected project for the same user.
- A second backend project may be overwritten because the editor always chooses the newest record.
- Pages with reserved legacy names can disappear during cleaning.
- Response-related elements and footer links are removed during routine normalization.
- An old browser backup can be restored over a newer server revision.
- A silent autosave failure may be indistinguishable from successful cloud persistence.
- Revision conflicts can leave the editor indefinitely unable to save without a reload.
- Settings and Builder can maintain conflicting header/footer copies.
- Closing while editing can preserve work only on Device A.

## 12. Recommended Fix

Use this architecture:

1. Backend `draft_schema` is always the cross-device authority.
2. Every editor route contains an explicit backend project UUID.
3. Initial loading waits for the selected backend record before enabling normal editing.
4. Local recovery keys include:
   - authenticated user ID
   - tenant ID
   - backend project UUID
5. Recovery values use an envelope:

```json
{
  "user_id": "...",
  "tenant_id": "...",
  "project_id": "...",
  "base_draft_revision": 12,
  "saved_at": "...",
  "schema": {}
}
```

6. A recovery copy never silently replaces the backend.
7. Recovery is offered only when its base/current revision relationship is understood.
8. The user chooses whether to recover, discard, or export.
9. Successful backend save updates or clears the recovery entry.
10. Editor UI distinguishes:
    - Unsaved
    - Saving locally
    - Saving to Madar
    - Saved to Madar
    - Save failed
    - Conflict detected
11. Shared project content and device preferences use separate models.
12. Settings and Builder share one site-configuration service or an explicit synchronization process.
13. Schema migrations are versioned and idempotent; routine loading does not delete pages by their display names.

### Read-only project metadata SQL

```sql
select
  id,
  tenant_id,
  owner_user_id,
  name,
  slug,
  status,
  draft_revision,
  published_revision,
  published_version,
  schema_version,
  updated_at,
  last_published_at,
  jsonb_typeof(draft_schema) as draft_schema_type,
  case
    when jsonb_typeof(draft_schema -> 'pages') = 'array'
    then jsonb_array_length(draft_schema -> 'pages')
    else 0
  end as page_count,
  case
    when jsonb_typeof(draft_schema -> 'forms') = 'array'
    then jsonb_array_length(draft_schema -> 'forms')
    else 0
  end as form_count,
  (
    select array_agg(key order by key)
    from jsonb_object_keys(draft_schema) as key
  ) as draft_top_level_keys,
  pg_column_size(draft_schema) as draft_schema_bytes,
  md5(draft_schema::text) as draft_schema_hash
from public.builder_projects
where id = :project_id
  and tenant_id = :tenant_id;
```

This reports structure and revision information without dumping block or form content.

## 13. Implementation Plan

### P0 — Correctness

1. Add explicit project-ID routing and selection.
2. Scope recovery storage by user, tenant, and backend project ID.
3. Make backend hydration authoritative.
4. Introduce recovery envelopes with base revision and timestamps.
5. Prevent local/server project identity mismatches before saving.
6. Add an explicit cloud-save state machine.
7. Reschedule saves skipped because of active editing/dragging.
8. Remove Settings’ unscoped builder storage path.
9. Define one canonical source for site chrome and website settings.
10. Replace destructive name-based normalization with versioned migrations.
11. Move active page/form/workflow/role selection out of shared project schema.

### P1 — UX and recovery

1. Add a recovery comparison dialog.
2. Show local and server revision/timestamp safely.
3. Add Export local copy before discard/reload.
4. Add Reload server, Keep local, and Resolve conflict actions.
5. Show persistent Saved/Unsaved/Failed status.
6. Store and restore the last opened project per user and tenant.
7. Expire obsolete recovery copies.
8. Clear/update backups after confirmed backend saves.

### P2 — Collaboration and offline support

1. Add server-side draft history/snapshots.
2. Add field- or operation-level collaboration semantics.
3. Support offline queues with base revisions.
4. Add conflict diffs and controlled merges.
5. Consider WebSocket/server events for cross-device updates.
6. Add durable recovery snapshots rather than relying exclusively on localStorage.

## 14. Tests Required

### Frontend

1. Device A full schema → backend payload → clean Device B load.
2. Existing local draft does not silently override a newer server revision.
3. Recovery applies only to the same user, tenant, and project.
4. Local key differs across two projects.
5. Local key differs across two tenants.
6. Correct project route fetches that exact project.
7. Two backend projects never depend on `updated_at` ordering.
8. Failed backend save leaves cloud state dirty.
9. Silent save failure becomes visible.
10. A skipped focused-input save is rescheduled.
11. Successful backend save updates/clears recovery.
12. Old backup cannot overwrite a newer backend revision without confirmation.
13. Responsive layout survives different Device A/Device B widths.
14. Theme, site chrome, forms, reservations, workflows, and actions survive a backend round trip.
15. Pages named “Reports” or “Orders” are not deleted.
16. Device-local selection does not alter shared project content.
17. Settings updates are visible in Builder on a clean device.
18. Unknown supported schema fields survive save/load.
19. Revision conflict supports reload/export/recovery.
20. Browser close after a failed cloud save preserves a recoverable snapshot.

### Backend

1. GET returns the complete draft schema and revision.
2. PUT preserves arbitrary supported nested keys.
3. PUT replaces the full schema only for the requested tenant/project.
4. Missing/wrong expected revision returns structured conflict context.
5. Two projects in one tenant remain isolated.
6. The same user across tenants cannot cross-write projects.
7. Project metadata endpoint can support recovery comparison without exposing private content.
8. Optional server-side snapshot/history tests if added.

### Integration

1. Create on Device A, save, then load with empty browser storage on Device B.
2. Update on Device B, then reopen Device A with an older recovery copy.
3. Concurrent edits produce a conflict, not silent data loss.
4. Settings → Builder → publish → public runtime retains consistent branding.
5. Multi-page forms, reservations, responsive positions, header/footer, and button actions survive the complete database round trip.

## 15. Suggested Implementation Commits

1. `Add explicit builder project selection and routes`
2. `Scope builder recovery storage by tenant and project`
3. `Make backend drafts authoritative during builder hydration`
4. `Add revision-aware builder recovery and save status`
5. `Unify website settings and builder site chrome persistence`
6. `Replace destructive builder cleanup with versioned migrations`
7. `Separate editor preferences from shared project schema`
8. `Add cross-device persistence integration coverage`

## 16. Files Reviewed

Key frontend files:

- `frontend/src/components/PageBuilder/workspace/PageBuilder.jsx`
- `frontend/src/components/PageBuilder/workspace/hooks/useDebouncedProjectStorage.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.storage.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.persistence.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.project.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.constants.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.factories.js`
- `frontend/src/components/PageBuilder/core/PageBuilder.layout.js`
- `frontend/src/components/PageBuilder/services/PageBuilder.api.js`
- `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx`
- `frontend/src/components/PageBuilder/preview/BuilderFormPreviewPage.jsx`
- `frontend/src/components/DashboardBuilder/SettingsPage.jsx`
- `frontend/src/components/DashboardBuilder/UserDashboard.jsx`
- `frontend/src/components/DashboardBuilder/ArchivePage.jsx`
- `frontend/src/components/PageBuilder/tabs/FormsTab.jsx`
- `frontend/src/components/PageBuilder/tabs/PageBuilderThemeTab.jsx`
- `frontend/src/components/PageBuilder/tabs/PageBuilderUsers.jsx`
- Data-analysis cache and IndexedDB helpers
- Persistence, data-safety, routing, form, and autosave tests

Key backend/database files:

- `backend/routes/builder_routes.py`
- `backend/routes/public_site_routes.py`
- `backend/routes/website_routes.py`
- `backend/services/website_settings_service.py`
- `database/migrations/024_create_builder_projects.sql`
- `database/migrations/045_add_platform_safety.sql`
- Builder publish, revision, archive, form, reservation, and public-site tests

No files were modified during the review, no commits were created, and `stash@{0}` remained intact.
