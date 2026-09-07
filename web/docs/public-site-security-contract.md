# Public Site Security Contract

## Live project identity

Each tenant subdomain resolves through
`website_settings.published_project_id`. A first publish may establish the
binding only when no other published project exists. Publishing another project
does not replace a valid binding. Owners and admins must explicitly select a
different published project through `PUT /builder/site-binding`.

The bound project cannot be archived or unpublished until another published
project is selected. Reservation configuration and public page lookup use that
bound project. Standalone form links may use another uniquely matching
published project within the same authoritative site tenant.

## Published content access

Anonymous site responses contain public pages only. Member/private pages and
pages configured as login destinations are omitted, including their blocks and
page metadata. An active tenant-site member can request one protected page from
`GET /public/sites/{subdomain}/pages/{page_reference}`.

The currently supported protected-page rule is deliberately narrow:

- `public` pages are anonymous;
- `private`, `authenticated`, and `members` pages require any active member;
- unknown role-specific visibility values fail closed.

Granular page-role permissions remain a separate authorization project. Until
that contract exists, the backend must not treat display-only role metadata as
authorization.

## Publish identity and caching

Publish validation produces the exact schema passed to the locking publish RPC.
The RPC verifies tenant, project, archive state, expected draft revision, and
entitlement before writing that exact schema to `published_schema`.

Public responses expose only safe publication identity:

- project ID;
- published version and timestamp;
- schema version;
- deterministic schema hash and ETag.

Anonymous responses use revalidation caching and support `If-None-Match`.
Authenticated protected-page responses are private and `no-store`. Draft schema
and draft revision are never returned by public runtime routes. Form submission
provenance records the resolved project's published version, not its draft
revision.

Standalone published-form links resolve within the authoritative site tenant,
using published snapshots only. The bound homepage project does not override
a duplicate form ID in another published project. More than 100 published
projects makes the bounded lookup incomplete and fails closed with 409, as does
multiple matching projects. This preserves unambiguous project identity for
form reads, drafts, submissions, and quiz attempts.
