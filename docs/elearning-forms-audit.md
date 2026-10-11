# E-Learning Forms implementation audit

Inspected before implementation, 2026-10-11, schema140.

Builder definitions are embedded in project schemas with string form/field IDs,
ordered sections/fields, options/default values and equality show/hide logic rules.
Pure `createField`, field option helpers, runtime field validation and form page
navigation are reusable. Its runtime omits hidden answers. Conditional logic is
ordered show/hide equality rules; it is not a general expression engine.

`PageBuilder.formHandlers`, templates that mutate projects, connected collections,
form duplication/deletion, draft local storage and public draft endpoints are
Builder-specific. Public submission validates fields, snapshots field/version
metadata, rate-limits and writes `builder_form_submissions`. Builder response
management scopes tenant/project and requires `response_management`. These
adapters and records will not be reused. File rendering accepts File objects;
Builder runtime stores file metadata only (name/size/type), not uploaded bytes.
Private E-Learning attachment ownership must be implemented independently using
existing private storage/quota helpers. Preview uses inert rendering.

Implement independent tenant-owned definitions, immutable schema versions and
permanent responses, with private attachments owned by responses. Reuse existing
Forms module capabilities (`forms`, `public_form_links`, `response_management`,
`data_exports`) and existing learning notification infrastructure. No specialized
application transitions or workflow automation will be introduced.
