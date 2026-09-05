# Forms Feature Specification

This document describes only the Forms feature that exists in this repository. It is derived from the current source. A statement marked `Unknown` could not be confirmed from the implementation.

## 1. Locate the Forms Feature

### Frontend editor and schema

| File | Responsibility |
| --- | --- |
| `web/frontend/src/components/PageBuilder/tabs/FormsTab.jsx` | Main form editor: form import, languages, form and field settings, sections, logic rules, form theme, save/publish controls. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.factories.js` | Authoritative constructors for forms, sections, fields, projects, and cloned IDs. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.constants.js` | Core nine-type field registry, `createId`, and `slugify`. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.formHandlers.js` | Add, update, move, duplicate, and delete handlers for forms, fields, and sections. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.formTemplates.js` | Built-in form templates and localized template data. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.starters.js` | Starter projects/forms; also proves runtime use of legacy types not present in the main picker. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.quiz.js` | Quiz defaults and quiz answer-key helpers. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.localization.js` | Form language normalization and localized text/option lookup and writes. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.theme.js` | Form-theme defaults and runtime CSS variables. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.editorState.js` | Removes editor-only state and defines the persistable project contract. |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.project.js` | Rehydrates project records and local editor defaults. |
| `web/frontend/src/components/PageBuilder/services/PageBuilder.api.js` | Builder response/draft APIs and public form, draft, submission, and quiz-attempt APIs. |

### Rendering, validation, and responses

| File | Responsibility |
| --- | --- |
| `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx` | Public embedded and standalone form renderer, input state, conditional visibility, page flow, drafts, normal submission, and quiz submission. |
| `web/frontend/src/components/PageBuilder/preview/BuilderFormPreviewPage.jsx` | Private builder preview route. |
| `web/frontend/src/components/PageBuilder/runtime/formValidation.js` | Client field validation. |
| `web/frontend/src/components/PageBuilder/runtime/formPageNavigation.js` | Enables current and previously completed pages; leaves unfinished future pages disabled. |
| `web/frontend/src/components/PageBuilder/runtime/formDraftStorage.js` | Device-local draft storage. |
| `web/frontend/src/components/PageBuilder/runtime/formSubmission.js` | Idempotency-key generation and submission request state helpers. |
| `web/frontend/src/components/PageBuilder/runtime/formSubmissionErrors.js` | Converts API errors into user-visible submission errors. |
| `web/frontend/src/components/PageBuilder/responses/BuilderResponsesPage.jsx` | Admin completed/incomplete response workspace. |
| `web/frontend/src/components/PageBuilder/responses/hooks/useBuilderResponsesData.js` | Loads and caches submissions/drafts. |
| `web/frontend/src/components/PageBuilder/responses/components/ResponseSettingsPanel.jsx` | Form response settings, including `resumeLaterEnabled`. |

### Backend and database

| File | Responsibility |
| --- | --- |
| `web/backend/routes/builder_routes.py` | Builder project CRUD/publish validation and authenticated submission/draft management. |
| `web/backend/routes/public_site_routes.py` | Resolves published standalone/embedded forms; public form read, draft, submit, and quiz endpoints; server validation. |
| `web/backend/services/public_quiz_service.py` | Public/private quiz serialization, attempt snapshots, scoring, deadlines, and results. |
| `web/supabase/migrations/024_create_builder_projects.sql` | Project JSON storage. |
| `web/supabase/migrations/027_create_builder_form_submissions.sql` and `028_update_builder_form_submission_statuses.sql` | Submission table and current statuses. |
| `web/supabase/migrations/045_add_platform_safety.sql`, `052_publish_validated_builder_schema.sql`, `072_harden_publication_isolation.sql` | Draft/published revisions and atomic validated publication. |
| `web/supabase/migrations/054_add_form_submission_idempotency.sql` | Idempotent submission columns and RPC. |
| `web/supabase/migrations/059_add_site_member_record_ownership.sql` | Optional site-user/membership ownership on submissions. |
| `web/supabase/migrations/084_create_builder_form_drafts.sql`, `091_add_named_user_form_drafts.sql` | Server draft records and draft names. |
| `web/supabase/migrations/089_create_public_quiz_attempts.sql` | Publication-pinned quiz attempts. |

Forms-related tests sit beside these modules and in `web/backend/tests/test_builder_form_submissions.py`, `test_builder_form_drafts.py`, and `test_public_quiz_security.py`.

## 2. Form Data Structure

Forms are objects in the project-level `forms` array. The current renderer and backend flatten `form.sections[].fields`; a legacy root `form.fields` can still be edited by some handlers but is not part of the current public field lookup.

`createForm()` generates this shape (IDs are illustrative):

```json
{
  "id": "form_550e8400-e29b-41d4-a716-446655440000",
  "name": "Contact form",
  "title": "Contact form",
  "description": "Use this form to collect information.",
  "successMessage": "Thank you. Your response has been submitted.",
  "languageMode": "en",
  "defaultLanguage": "en",
  "connectedCollectionId": "",
  "mode": "form",
  "quiz": {
    "lockScreen": false,
    "totalTimeLimitSec": 0,
    "questionTimeLimitSec": 0,
    "showQuestionTimer": true,
    "showTotalTimer": true,
    "scoring": "automatic",
    "passingScore": 70,
    "showResults": true,
    "allowRetakes": true,
    "maxRetakes": 0
  },
  "pageMode": "paged",
  "sections": [
    {
      "id": "formSection_550e8400-e29b-41d4-a716-446655440001",
      "title": "Page 1",
      "description": "",
      "collapsed": false,
      "fields": [
        {
          "id": "field_550e8400-e29b-41d4-a716-446655440002",
          "label": "Email",
          "type": "email",
          "key": "email",
          "required": true,
          "helpText": "",
          "placeholder": "Email",
          "showDescriptionEditor": false,
          "showExampleEditor": false,
          "showDetailsEditor": false,
          "options": [],
          "defaultValue": "",
          "scaleMin": 1,
          "scaleMax": 5,
          "scaleMinLabel": "Low",
          "scaleMaxLabel": "High",
          "maxRating": 5,
          "width": "full",
          "quizCorrectAnswer": "",
          "quizPoints": 1
        }
      ]
    }
  ],
  "responses": []
}
```

Exact English default copy is supplied by `web/frontend/src/content/pageBuilder/factoryContent.js`; installations/locales use that source. Optional properties used elsewhere include:

- `localized`: localized maps such as `{ "title": {"ar": "..."}, "options": {"ar": ["..."]} }`. Legacy aliases such as `titleI18n` and `optionsI18n` are also read.
- `logicRules`: conditional visibility rules.
- `resumeLaterEnabled`: absent behaves as enabled; `false` disables it.
- Field `accept`, `maxFileSizeMb`, and `quizTimeLimitSec` are consumed by runtime code.
- Quiz `randomizeQuestions` or `randomizeQuestionOrder` is consumed by the quiz service but has no confirmed form-editor control.

## 3. Form Database / Storage Structure

### Project definition

There is no separate forms-definition table. The hierarchy is:

```json
{
  "builder_projects": {
    "id": "project UUID",
    "tenant_id": 1,
    "draft_schema": {
      "forms": ["form objects"],
      "pages": [
        {
          "sections": [
            {
              "rows": [
                {
                  "columns": [
                    {
                      "elements": [
                        {
                          "id": "block UUID-like ID",
                          "type": "formBlock",
                          "connectedFormId": "form ID"
                        }
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    "published_schema": { "forms": ["published snapshots"] }
  }
}
```

`builder_projects` stores `id`, `tenant_id`, optional `owner_user_id`, `name`, tenant-unique `slug`, `status`, `draft_schema`, nullable `published_schema`, `published_version`, `draft_revision`, nullable `published_revision`, `schema_version`, publication timestamps, and normal timestamps.

- Create: project creation stores the complete persistable project under `draft_schema`.
- Update: project save replaces `draft_schema` using optimistic `expected_revision`; the client strips active editor selection fields and server-only metadata first.
- Publish: backend revalidates and atomically copies the exact validated draft into `published_schema`, increments `published_version`, and records `published_revision`. Public form links never read the unpublished draft.
- Load: authenticated builder APIs return `draft_schema`; frontend re-adds local active selections. Public routes resolve a published project/form and return a redacted form.
- Delete form: removes it from `draft_schema.forms`, removes its workflows, and clears page-block references in the editor. Existing submission/draft rows are not individually deleted by this handler. Deleting the project cascades related records.
- Import: requires an object with `sections`; resets `responses` and `connectedCollectionId`, remaps every encountered string `id` and matching string reference, and supplies missing form/section/field IDs.

### Response records

`builder_form_submissions` stores `id`, `tenant_id`, `project_id`, textual `form_id`, `form_title`, `form_version`, status (`new`, `contacted`, `closed`, `spam`, or `archived`), `answers` JSON object, optional `quiz_result`, `field_snapshot` JSON array, timestamps/IP/user-agent, optional `site_user_id` and `site_membership_id`, and SHA-256 `idempotency_key_hash`/`request_hash`.

`builder_form_drafts` stores a similar project/form identity plus `answers`, `field_snapshot`, `form_element_id`, `page_index`, `language`, optional user/membership ownership, IP/user-agent, timestamps, and required `draft_name` of 1â€“120 trimmed characters.

`public_quiz_attempts` pins each attempt to `tenant_id`, `project_id`, `form_id`, `publication_version`, a publication hash, and anonymous subject hash. It stores state, deadline, question order, private form snapshot, submitted answers, result, and optional submission relationship.

`connectedCollectionId` is form metadata used in the editor/responses UI. The public submission path does not write a connected collection.

## 4. Supported Form Components

The feature has several creation channels. The main new-field picker exposes nine types; import accepts thirteen; starter data and runtime support four more. All seventeen below have explicit public rendering and validation behavior.

| Type | Purpose | Main Settings | Creation source | Runtime/validation source |
| --- | --- | --- | --- | --- |
| `shortText` | One-line text | common text settings | picker/import | `TenantSiteRuntime.jsx`, `formValidation.js` |
| `paragraph` | Multiline text | common text settings | picker/import | same |
| `email` | Email address | common text settings | picker/import | same |
| `phone` | Telephone value | common text settings | picker/import | same |
| `url` | HTTP(S) URL | common text settings | starter | same |
| `number` | Numeric value | common text settings | picker/import | same |
| `money` | Numeric monetary text, commas accepted | common text settings | import | same |
| `date` | Calendar date | common text settings | picker/import | same |
| `time` | 24-hour time | common text settings | starter | same |
| `dropdown` | Single select | `options` | import/template/current legacy field | same |
| `status` | Single select status | `options` | import | same |
| `yesNo` | Yes/No select | localized built-in choices | import | same |
| `radio` | Single radio choice | `options` | picker/import | same |
| `checkboxes` | Multiple choices | `options` | picker/import | same |
| `linearScale` | Integer scale | scale min/max and labels | starter | same |
| `rating` | Integer rating | `maxRating` | starter | same |
| `file` | File metadata selection | `accept`, `maxFileSizeMb` | picker/import | same |

`website` is accepted as a URL alias by client/server validation, but no form factory, picker, import guide, or starter creates it; it is therefore not a currently addable component type.

## 5. Document Each Form Component

### Common field contract

Factory-created fields share the JSON object shown in section 2. The consistently necessary runtime properties are string `id`, string `type`, and displayable `label`; fields without IDs cannot be submitted. Factory fields additionally always contain string `key`, boolean `required`, string `helpText`, string `placeholder`, three boolean editor flags, array `options`, `defaultValue`, numeric scale/rating/quiz defaults, string `width`, and `quizCorrectAnswer` (array only for `checkboxes`).

The editor configures localized `label`; `required`; and, when `showDetailsEditor` is enabled, localized `helpText` and `placeholder`. Quiz mode also configures `quizCorrectAnswer` and non-negative `quizTimeLimitSec`. `key`, `defaultValue`, `width`, `accept`, `maxFileSizeMb`, and `quizPoints` have no confirmed control in the current Forms editor. The runtime uses `defaultValue`, `accept`, and `maxFileSizeMb` when present. Help/placeholder render only when `showDetailsEditor === true`.

For compactness, each component JSON below shows its type-specific result on top of the common factory properties.

### `shortText`

- **Purpose/internal type:** one-line free text; `shortText`.
- **JSON:** `{ "id":"field_...", "type":"shortText", "label":"Name", "key":"name", "required":false, "options":[], "defaultValue":"", "placeholder":"Short answer", "quizCorrectAnswer":"" }` plus common properties.
- **Required/optional:** runtime requires usable `id`, `type`, and label; common/type-specific properties above are factory defaults. Localized text and quiz settings are optional.
- **Settings/defaults:** common settings; factory `required:false`, empty help/default, full width.
- **Validation:** nonempty when required; supplied value must be a string on server. Client rejects object values.
- **Special behavior/files:** normal text input. `PageBuilder.factories.js`, `TenantSiteRuntime.jsx`, `formValidation.js`, `public_site_routes.py`.

### `paragraph`

- **Purpose/internal type:** multiline free text; `paragraph`.
- **JSON:** `{ "id":"field_...", "type":"paragraph", "label":"Details", "key":"details", "required":false, "options":[], "defaultValue":"", "placeholder":"Long answer", "quizCorrectAnswer":"" }` plus common properties.
- **Required/optional/settings/defaults:** common contract.
- **Validation:** same as `shortText`.
- **Special behavior/files:** renders `textarea`. Same relevant files as `shortText`.

### `email`

- **Purpose/internal type:** email address; `email`.
- **JSON:** `{ "id":"field_...", "type":"email", "label":"Email", "key":"email", "required":false, "options":[], "placeholder":"Email", "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract.
- **Validation:** required if configured; otherwise supplied text must match `[non-space/non-@]+@[non-space/non-@]+.[non-space/non-@]+` client and server.
- **Special behavior/files:** renders `input[type=email]`. Factory/runtime/validation/public-route files above.

### `phone`

- **Purpose/internal type:** telephone value; `phone`.
- **JSON:** `{ "id":"field_...", "type":"phone", "label":"Phone", "key":"phone", "required":false, "options":[], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract; available through the visible picker and import/legacy data.
- **Validation:** characters limited to `+ ( ) digits spaces . -`; 7â€“15 digits after stripping punctuation.
- **Special behavior/files:** renders `input[type=tel]`. `FormsTab.jsx`, starter/template sources, runtime and both validators.

### `url`

- **Purpose/internal type:** web URL; `url`.
- **JSON:** `{ "id":"field_...", "type":"url", "label":"Website", "key":"website", "required":false, "options":[], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract; confirmed in starter data, not the picker/import allow-list.
- **Validation:** a supplied string must parse as an HTTP or HTTPS URL with a host.
- **Special behavior/files:** renders `input[type=url]`. Starter, runtime, client validator, public route.

### `number`

- **Purpose/internal type:** finite numeric answer; `number`.
- **JSON:** `{ "id":"field_...", "type":"number", "label":"Quantity", "key":"quantity", "required":false, "options":[], "placeholder":"Numeric answer", "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract; no implemented field min/max setting.
- **Validation:** must coerce to a finite number; booleans rejected server-side.
- **Special behavior/files:** renders `input[type=number]`. Factory, picker/import, runtime, validators.

### `money`

- **Purpose/internal type:** finite monetary number; `money`.
- **JSON:** `{ "id":"field_...", "type":"money", "label":"Amount", "key":"amount", "required":false, "options":[], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract; import/legacy type, no currency setting.
- **Validation:** finite number after removing commas; booleans rejected server-side.
- **Special behavior/files:** input-type mapper falls back to text, not `number`. `FormsTab.jsx`, runtime, validators.

### `date`

- **Purpose/internal type:** calendar date; `date`.
- **JSON:** `{ "id":"field_...", "type":"date", "label":"Date", "key":"date", "required":false, "options":[], "placeholder":"Date", "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract; no min/max date setting.
- **Validation:** exact, real calendar date in `YYYY-MM-DD`.
- **Special behavior/files:** renders `input[type=date]`. Factory, picker/import, runtime, validators.

### `time`

- **Purpose/internal type:** time of day; `time`.
- **JSON:** `{ "id":"field_...", "type":"time", "label":"Time", "key":"time", "required":false, "options":[], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common contract; starter-only creation confirmed.
- **Validation:** 24-hour `HH:MM`, `00:00` through `23:59`.
- **Special behavior/files:** renders `input[type=time]`. Starter, runtime, validators.

### `dropdown`

- **Purpose/internal type:** one choice in a select; `dropdown`.
- **JSON:** `{ "id":"field_...", "type":"dropdown", "label":"Department", "key":"department", "required":false, "options":["Sales","Support"], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common plus editable localized `options`; factory choice defaults come from copy data. Deleting the last option leaves one empty option.
- **Validation:** client requires the answer to be one configured option when nonempty options exist. Server requires a scalar but does not check membership.
- **Special behavior/files:** imported/templates/current legacy fields can use it; omitted from the visible new-field list. FormsTab, runtime, localization, validators.

### `status`

- **Purpose/internal type:** status-like single select; `status`.
- **JSON:** `{ "id":"field_...", "type":"status", "label":"Status", "key":"status", "required":false, "options":["Open","Closed"], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults/validation:** same option editor and validation split as `dropdown`.
- **Special behavior/files:** import/legacy type rendered as select. FormsTab, runtime, localization, validators.

### `yesNo`

- **Purpose/internal type:** binary Yes/No select; `yesNo`.
- **JSON:** `{ "id":"field_...", "type":"yesNo", "label":"Agree?", "key":"agree", "required":false, "options":[], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common; the editor does not expose an options editor for this type.
- **Validation:** server accepts a scalar. Client has no explicit `yesNo` type branch beyond common required/default scalar handling.
- **Special behavior/files:** runtime supplies localized built-in Yes/No options. FormsTab import list, runtime, localization, public route.

### `radio`

- **Purpose/internal type:** one visible radio choice; `radio`.
- **JSON:** `{ "id":"field_...", "type":"radio", "label":"Priority", "key":"priority", "required":false, "options":["Low","High"], "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common plus localized options.
- **Validation:** client checks option membership; server accepts a scalar without membership check.
- **Special behavior/files:** UI state temporarily stores `{value, optionIndex}`; submission normalization sends the scalar value. Factory, FormsTab, runtime, validators.

### `checkboxes`

- **Purpose/internal type:** zero or more choices; `checkboxes`.
- **JSON:** `{ "id":"field_...", "type":"checkboxes", "label":"Topics", "key":"topics", "required":false, "options":["A","B"], "quizCorrectAnswer":[] }` plus common properties.
- **Settings/defaults:** common plus localized options; answer key is an array.
- **Validation:** required means nonempty array. Client checks every answer against options; server requires an array of JSON scalar/null values but does not check membership.
- **Special behavior/files:** UI state holds `{value, optionIndex}` objects; payload normalization sends an array of values. Factory, FormsTab, runtime, validators.

### `linearScale`

- **Purpose/internal type:** one integer on a bounded scale; `linearScale`.
- **JSON:** `{ "id":"field_...", "type":"linearScale", "label":"Likelihood", "key":"likelihood", "required":false, "scaleMin":1, "scaleMax":5, "scaleMinLabel":"Low", "scaleMaxLabel":"High", "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** editor exposes `scaleMin` (input constrained 0â€“10), `scaleMax` (2â€“10), and localized endpoint labels; factory defaults 1, 5, and copy-provided labels.
- **Validation:** integer in configured range; runtime renders numeric radio choices.
- **Special behavior/files:** confirmed by starter/runtime, not picker/import guide. FormsTab, factories, starter, runtime, validators.

### `rating`

- **Purpose/internal type:** integer rating; `rating`.
- **JSON:** `{ "id":"field_...", "type":"rating", "label":"Rating", "key":"rating", "required":false, "maxRating":5, "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** editor exposes `maxRating` constrained 2â€“10; factory default 5.
- **Validation:** integer from 1 through `maxRating`.
- **Special behavior/files:** rendered as numeric radio choices; starter/runtime type, not picker/import guide. FormsTab, factories, starter, runtime, validators.

### `file`

- **Purpose/internal type:** select a file and submit its metadata; `file`.
- **JSON:** `{ "id":"field_...", "type":"file", "label":"Attachment", "key":"attachment", "required":false, "options":[], "accept":".pdf,image/*", "maxFileSizeMb":10, "quizCorrectAnswer":"" }` plus common properties.
- **Settings/defaults:** common; `accept` and `maxFileSizeMb` are runtime-supported optional properties but have no confirmed current Forms-editor control or factory default.
- **Validation:** value must be an object with nonblank `name`, numeric nonnegative `size`, and optional `type`; size must not exceed configured positive MB limit.
- **Special behavior/files:** the public runtime stores `{name,size,type}` only; actual binary upload/storage is not implemented in this flow. Factory/picker/import, runtime, validators.

## 6. Form-Level Settings

| Key | Type | Default | Allowed values/purpose |
| --- | --- | --- | --- |
| `id` | string | `form_` plus UUID/fallback | Stable form identity and API/reference key. |
| `name`, `title` | string/localizable | constructor title | Library/display title; editor keeps both concepts in the form object. |
| `description` | string/localizable | copy-provided text | Public introduction. |
| `successMessage` | string/localizable | copy-provided text | Post-submit message. |
| `languageMode` | string | `en` | `en`, `ar`, or `bilingual`. |
| `defaultLanguage` | string | `en` | Primary language, `en` or `ar`. |
| `connectedCollectionId` | string | `""` | Optional collection metadata; not a public submission write target. |
| `mode` | string | `form` | `form` or `quiz`. |
| `pageMode` | string | `paged` | Stored by factory/editor; runtime paging is based on sections. Other allowed values are `Unknown`. |
| `sections` | array | one section | Ordered pages and their ordered fields. |
| `responses` | array | `[]` | Legacy form property; persisted definitions contain it, but real responses use tables. |
| `logicRules` | array | absent/`[]` | Conditional visibility rules. |
| `resumeLaterEnabled` | boolean | enabled unless exactly `false` | Allows named server/device drafts. |
| `quiz.lockScreen` | boolean | `false` | Quiz lock-screen behavior. |
| `quiz.totalTimeLimitSec` | number | `0` | Overall seconds; zero means no configured limit. UI edits minutes. Server clamps attempt duration to at most 86,400 seconds. |
| `quiz.questionTimeLimitSec` | number | `0` | Default per-question seconds. |
| `quiz.showQuestionTimer`, `quiz.showTotalTimer` | boolean | `true` | Runtime timer visibility; no current editor control confirmed. |
| `quiz.scoring` | string | `automatic` | `automatic`, `manual`, or `completion`. |
| `quiz.passingScore` | number | `70` | Clamped by editor to 0â€“100. |
| `quiz.showResults` | boolean | `true` | Whether public results are shown. |
| `quiz.allowRetakes` | boolean | `true` | Enables additional attempts. |
| `quiz.maxRetakes` | number | `0` | Nonnegative; when retakes are allowed, zero means up to 100 total attempts, otherwise total is `1 + maxRetakes` capped by backend input handling. |

Form visual settings are stored once at `project.theme.form`, not on each form: `background`, `surface`, `inputBackground`, `text`, `muted`, `border`, `accent`, `buttonText`, `radius` (8), and `fieldRadius` (14), with defaults in `PageBuilder.theme.js`.

## 7. Field Ordering and Structure

- Section array order is page order; field array order is display/submission snapshot order.
- `createField` appends a new field to the selected section. A legacy no-sections branch appends to root `fields`.
- Add Page creates a `formSection` with title `Page N`, empty description, `collapsed:false`, and no fields.
- Update shallow-merges a patch into the matching ID in root and section fields.
- Move up/down reorders within a section. Crossing a boundary moves the field to the previous/next section.
- Duplicate recursively assigns new `copy_...` IDs, adds ` Copy` to the field label, and inserts after the source.
- Delete filters the field or section from its array. Form deletion also removes form workflows and clears page placements.
- Sections are the only implemented nesting/grouping unit. Arbitrary nested field groups are not implemented.
- `createId(prefix)` returns `${prefix}_${crypto.randomUUID()}` when available, otherwise `${prefix}_${Date.now()}_${randomHex}`. Form, section, field, block, and rule references must remain unique and stable.
- `key` is initially the lowercase ASCII slug of the label with hyphens replaced by underscores. Non-ASCII-only input falls back to `page`. Runtime answer objects use field `id`, not `key`.

## 8. Conditional Logic

Rules are stored at `form.logicRules`:

```json
{
  "id": "logic_1720000000000",
  "sourceFieldId": "field_source",
  "operator": "equals",
  "value": "Yes",
  "action": "show",
  "targetFieldId": "field_target"
}
```

The editor creates only `operator:"equals"`, offers source field, free-text comparison value, action (`show` or `hide`), and target field. Runtime comparison is case-sensitive exact equality after converting both values to strings and trimming. It does not read `operator`; `equals` is therefore the only meaningful stored operator.

For a target, rules are reduced in array order from visible. A `show` rule sets visibility to its match result. A matching `hide` rule sets visibility false; a nonmatching hide rule leaves the current state unchanged. Hidden fields are omitted from client validation and the outgoing answer payload.

Deleting a referenced field does not automatically remove dangling logic rules. The backend required-field validator does not evaluate conditional visibility, so a required field hidden and omitted by the client can still be rejected as missing by the server.

## 9. Validation

### Client

`formValidation.js` enforces required values and the component rules in section 5. It validates visible fields on the current page before Next, and all visible fields before final submission. On failure, the runtime navigates to the first invalid page and focuses the field.

There are no implemented custom regex rules, text-length rules, numeric min/max settings, or arbitrary validation-rule objects. Range configuration exists only for scale/rating and file size.

### Server

`public_site_routes.py` revalidates normal submissions against every field in the published form:

- rejects unknown field IDs;
- enforces every published `required` field;
- validates types/ranges described above;
- limits answers to 100 fields, each nested string to 5,000 characters, and compact UTF-8 JSON to 64 KiB;
- normalizes JSON answers before storage;
- uses the published field snapshot, not the current draft.

Server choice validation checks scalar/array shape but not membership in configured options. Draft saves enforce IDs and payload limits but intentionally do not enforce required/type completion. Public routes also enforce rate limits, a honeypot, and a configurable minimum elapsed time (default comes from server configuration; the exact deployed value is `Unknown`).

Quiz scoring is server-authoritative. Automatic scoring normalizes case/whitespace and checkbox order; completion scoring measures answered fields; manual scoring returns no automatic score/pass result. Private answer keys are removed from the public form response.

## 10. Form Submission

```text
Published rendered form
â†’ answers keyed by field ID
â†’ page/all-visible client validation
â†’ answer normalization and POST
â†’ published-schema server validation
â†’ idempotent builder_form_submissions insert
```

Standalone form load is `GET /public/sites/{subdomain}/forms/{formId}`. Normal submit is `POST /public/sites/{subdomain}/forms/{formId}/submissions` with an `Idempotency-Key` header and body:

```json
{
  "answers": {
    "field_name": "Ada Lovelace",
    "field_topics": ["Support"],
    "field_file": {"name":"brief.pdf","size":12345,"type":"application/pdf"}
  },
  "form_element_id": "optional placement/block ID",
  "resume_token": null,
  "honeypot": "",
  "submission_elapsed_ms": 42000,
  "idempotency_key": "madar-form-generated-unique-value"
}
```

The server stores tenant/project/form identity, published version/title, normalized answers, field snapshot, optional quiz result and user ownership, and request metadata. The current normal-submission record payload does not persist `form_element_id`. A successful resumed submission deletes the matching server draft. The runtime resets answers, errors, page/completion state, and local draft, then shows `successMessage` or quiz results.

Resume Later upserts to `POST /public/sites/{subdomain}/forms/{formId}/drafts` with answers, `form_element_id`, page, language, optional resume token/name, and bot fields. Local fallback/storage key is `madar:runtime-form-drafts:v1:{lowercase-site-id}` with `{version:1,drafts:{[instanceKey]:{formId,draftName,answers,pageIndex,language,savedAt,draftId?,resumeToken?}}}`.

Quiz flow first posts to `/attempts`, receiving a publication-pinned private-server attempt and public-redacted form, then posts `{ "answers": {...} }` to `/attempts/{attemptId}/finalize`. Finalization creates/links a normal submission record.

## 11. Rules and Constraints

An automated agent modifying form definitions MUST:

1. Store forms only in `project.forms` inside the project schema; do not create a separate form-definition store.
2. Put current fields under ordered `form.sections[].fields`; do not rely on legacy root `form.fields` for public rendering/submission.
3. Give every form, section, and field a unique nonempty string `id`; preserve all ID references in placements and logic rules.
4. Use one of the seventeen documented runtime types. Use the narrower thirteen-type import allow-list when generating an import file.
5. Preserve field IDs when editing existing fields because responses are keyed by them.
6. Preserve `formBlock.connectedFormId` references. Publish rejects missing/orphaned form blocks and duplicate page/form/block IDs.
7. Use localized data under `localized.<property>.<language>` and `localized.options.<language>`; keep base values as fallbacks.
8. Keep `languageMode` to `en`, `ar`, or `bilingual`, and `defaultLanguage` to `en` or `ar`.
9. Keep option answers as configured strings; checkboxes submit arrays, while all other choices submit a scalar.
10. Keep scale/rating limits valid and quiz times/retakes nonnegative; keep passing score within 0â€“100.
11. Do not make a conditionally hidden target required if the client may omit it; server validation does not evaluate logic rules.
12. Remove or repair logic rules when deleting referenced fields; the existing delete handler does not do this automatically.
13. Treat file values as metadata only; this submission flow does not upload binary content.
14. Publish before expecting public/production links to reflect a form. Public form resolution uses `published_schema`, never `draft_schema`.
15. Submit answers by field ID and obey 100-field, 5,000-character-per-string, and 64-KiB limits.
16. Keep private quiz answer keys in the stored form; rely on server public serialization to redact them.
17. Do not treat `connectedCollectionId` as submission persistence; responses belong in the Forms response tables.

## 12. Canonical Examples

IDs below use the valid application prefix pattern but shortened illustrative UUID text.

### Minimal Form

```json
{
  "id":"form_minimal-uuid",
  "name":"Contact",
  "title":"Contact",
  "description":"",
  "successMessage":"Thank you.",
  "languageMode":"en",
  "defaultLanguage":"en",
  "connectedCollectionId":"",
  "mode":"form",
  "quiz":{"lockScreen":false,"totalTimeLimitSec":0,"questionTimeLimitSec":0,"showQuestionTimer":true,"showTotalTimer":true,"scoring":"automatic","passingScore":70,"showResults":true,"allowRetakes":true,"maxRetakes":0},
  "pageMode":"paged",
  "sections":[{"id":"formSection_minimal-uuid","title":"Page 1","description":"","collapsed":false,"fields":[{"id":"field_email-uuid","label":"Email","type":"email","key":"email","required":true,"helpText":"","placeholder":"Email","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":[],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"","quizPoints":1}]}],
  "responses":[]
}
```

### Typical Form

```json
{
  "id":"form_request-uuid","name":"Service request","title":"Service request","description":"Tell us what you need.","successMessage":"Request received.","languageMode":"en","defaultLanguage":"en","connectedCollectionId":"","mode":"form","pageMode":"paged","resumeLaterEnabled":true,
  "quiz":{"lockScreen":false,"totalTimeLimitSec":0,"questionTimeLimitSec":0,"showQuestionTimer":true,"showTotalTimer":true,"scoring":"automatic","passingScore":70,"showResults":true,"allowRetakes":true,"maxRetakes":0},
  "sections":[
    {"id":"formSection_contact-uuid","title":"Contact","description":"","collapsed":false,"fields":[
      {"id":"field_name-uuid","label":"Name","type":"shortText","key":"name","required":true,"helpText":"","placeholder":"Short answer","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":[],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"","quizPoints":1},
      {"id":"field_email-uuid","label":"Email","type":"email","key":"email","required":true,"helpText":"","placeholder":"Email","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":[],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"","quizPoints":1}
    ]},
    {"id":"formSection_request-uuid","title":"Request","description":"","collapsed":false,"fields":[
      {"id":"field_department-uuid","label":"Department","type":"dropdown","key":"department","required":true,"helpText":"","placeholder":"Dropdown menu","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":["Sales","Support"],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"","quizPoints":1},
      {"id":"field_details-uuid","label":"Details","type":"paragraph","key":"details","required":false,"helpText":"","placeholder":"Long answer","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":[],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"","quizPoints":1}
    ]}
  ],"responses":[]
}
```

### Advanced Form

```json
{
  "id":"form_quiz-uuid","name":"Safety quiz","title":"Safety quiz","description":"Complete both pages.","successMessage":"Quiz submitted.","languageMode":"bilingual","defaultLanguage":"en","connectedCollectionId":"","mode":"quiz","pageMode":"paged","resumeLaterEnabled":true,
  "localized":{"title":{"ar":"ط§ط®طھط¨ط§ط± ط§ظ„ط³ظ„ط§ظ…ط©"},"description":{"ar":"ط£ظƒظ…ظ„ ط§ظ„طµظپط­طھظٹظ†."},"successMessage":{"ar":"طھظ… ط¥ط±ط³ط§ظ„ ط§ظ„ط§ط®طھط¨ط§ط±."}},
  "quiz":{"lockScreen":true,"totalTimeLimitSec":900,"questionTimeLimitSec":60,"showQuestionTimer":true,"showTotalTimer":true,"scoring":"automatic","passingScore":80,"showResults":true,"allowRetakes":true,"maxRetakes":2},
  "sections":[
    {"id":"formSection_gate-uuid","title":"Eligibility","description":"","collapsed":false,"fields":[
      {"id":"field_trained-uuid","label":"Have you trained?","type":"yesNo","key":"have_you_trained","required":true,"helpText":"","placeholder":"","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":[],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"Yes","quizPoints":1,"quizTimeLimitSec":30}
    ]},
    {"id":"formSection_questions-uuid","title":"Questions","description":"","collapsed":false,"fields":[
      {"id":"field_ppe-uuid","label":"Select required PPE","type":"checkboxes","key":"select_required_ppe","required":false,"helpText":"Choose all that apply.","placeholder":"","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":true,"options":["Helmet","Gloves","Sandals"],"localized":{"options":{"ar":["ط®ظˆط°ط©","ظ‚ظپط§ط²ط§طھ","طµظ†ط§ط¯ظ„"]}},"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":["Helmet","Gloves"],"quizPoints":1,"quizTimeLimitSec":60},
      {"id":"field_confidence-uuid","label":"Confidence","type":"linearScale","key":"confidence","required":false,"helpText":"","placeholder":"","showDescriptionEditor":false,"showExampleEditor":false,"showDetailsEditor":false,"options":[],"defaultValue":"","scaleMin":1,"scaleMax":5,"scaleMinLabel":"Low","scaleMaxLabel":"High","maxRating":5,"width":"full","quizCorrectAnswer":"","quizPoints":1}
    ]}
  ],
  "logicRules":[{"id":"logic_1720000000000","sourceFieldId":"field_trained-uuid","operator":"equals","value":"Yes","action":"show","targetFieldId":"field_ppe-uuid"}],
  "responses":[]
}
```

## 13. Agent-Critical Summary

## Agent-Critical Contract

- **Authoritative definitions:** `PageBuilder.factories.js`, `FormsTab.jsx`, `TenantSiteRuntime.jsx`, `formValidation.js`, `public_site_routes.py`, and the Forms migrations listed in section 1.
- **Types:** `shortText`, `paragraph`, `email`, `phone`, `url`, `number`, `money`, `date`, `time`, `dropdown`, `status`, `yesNo`, `radio`, `checkboxes`, `linearScale`, `rating`, `file`. Import accepts only `shortText`, `paragraph`, `email`, `number`, `date`, `dropdown`, `radio`, `checkboxes`, `file`, `money`, `phone`, `yesNo`, `status`.
- **Shape:** `project.forms[] â†’ form.sections[] â†’ section.fields[]`. Array order is runtime order. Answers are keyed by field `id`.
- **Identity:** all form/section/field IDs must be unique, nonempty strings and stable across edits. Preserve `formBlock.connectedFormId`, logic source/target IDs, and response compatibility.
- **Minimum safe form:** unique `id`, usable `name`/`title`, `sections` array, and section/field IDs and types. Factory-generated forms should retain all defaults shown in section 2.
- **Settings:** use only documented form, quiz, localization, theme, common-field, option, scale/rating, file, and quiz-answer properties. Unconfirmed settings are `Unknown` and must not be invented.
- **Validation:** enforce required and documented type rules client and server; stay within 100 answers, 5,000 characters per nested string, and 64 KiB JSON. Do not rely on server option-membership or conditional-visibility evaluation.
- **Persistence:** definitions remain nested in `builder_projects.draft_schema.forms`; production uses `published_schema.forms` after atomic publish. Submissions, drafts, and quiz attempts use their dedicated tables.
- **Critical invariants:** do not use legacy root fields for new forms; do not leave orphaned placements or logic references; do not require conditionally omitted fields; do not expose quiz keys in public responses; do not assume files upload binary data or collections receive submissions.

