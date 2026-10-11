# E-Learning Forms architecture boundary

User clarification, 2026-10-11: reuse Builder Forms methodology and UX while
keeping Builder definitions and responses independent of E-Learning Forms.

## Reuse

Reuse compatible field models, schema patterns, validation rules, conditional
logic, rendering patterns and editor/submission UX. Shared helpers must receive
schema/data through explicit inputs; persistence belongs to each module.

Useful existing patterns include Builder `PageBuilder.formHandlers`, field/form
factories and templates, `runtime/formValidation`, form page navigation, preview
and field rendering. Project-mutating handlers and Builder submission/draft
adapters are not automatically suitable as E-Learning persistence adapters.
Server validation must enforce field types, options, required/conditional fields
and tenant authorization independently of browser validation.

## Ownership

E-Learning Forms must own tenant-scoped definitions and responses where those
entities are required. Definitions, response versions, applicant identity,
permissions and response lifecycle must be resolved through E-Learning context.
A response must reference a definition/version from the same tenant. Rendering
an E-Learning form inside a Builder page does not change its storage owner.

Do not connect E-Learning Forms to `builder_form_submissions`, Builder response
management endpoints, Builder drafts or Builder form/collection IDs. Do not
expose E-Learning responses in Builder response administration. Sharing a schema
shape or UI component is not authorization to share records. A future proposal
for shared storage requires an explicit architectural investigation; none was
found or introduced in this pass.

## Implementation checked

- Builder form definitions live in Builder project schemas. Its response routes
  in `builder_routes.py` and `public_site_routes.py` use
  `builder_form_submissions`; those remain independent.
- Existing affiliate/support/exchange workflows own tenant-scoped responses in
  `academy_applications`, with terms snapshots and immutable workflow history.
  Private supporting documents reference those applications, not Builder responses.
- The fixed academy contact flow uses the existing platform `contacts` mechanism
  with tenant/project scope. It does not use Builder Forms or their submissions.
  This fixed contact adapter does not establish a storage design for general
  E-Learning Forms.
- The subsequent schema141 Forms pass implements independent
  `elearning_forms`, `elearning_form_versions`, `elearning_form_responses` and
  `elearning_form_files`. Academy Builder stores only a tenant-checked form UUID;
  public and owner APIs resolve learning-owned definitions and responses. Existing
  specialized programme workflows remain independent. See the
  [17-point implementation report](elearning-forms-implementation.md).

The ownership clarification itself required no reassignment. The new Forms
capability uses migration141; no historical responses were reassigned.
