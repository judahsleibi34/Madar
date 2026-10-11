# Academy owner / shared Builder audit

Audit performed before changing runtime code, 2026-10-11. Current schema139.

A. Shared Projects already provide multi-page schemas, custom public slugs,
   shared site chrome/header/footer/navigation, draft revisions, previews,
   publish validation and atomic publication. No additional CMS is needed.
B. Academy uses `builder_projects.usage_profile=academy` and tenant-scoped
   `website_settings.academy_editor_project_id` / `academy_project_id`.
C. Home and arbitrary About/FAQ/Contact/Terms/Privacy/support/exchange/affiliate
   presentation pages can be built now. Courses/plans/auth/learning are reserved
   system routes. Registry includes dynamic courses, plans, instructors and
   continue-learning blocks; other informational pages use shared text/cards.
D. `publish_validated_builder_project_atomic` locks tenant/project/settings,
   checks revision, validates schema, snapshots published state and binds the
   academy independently of the main website. Draft schema is preserved.
E. `ensure_academy_builder_project` locks website settings, selects durable editor,
   published or existing academy project, and creates only when none remains.
   Deleted editor binding clears; published binding restricts deletion. Existing
   integration database tests exercise reuse/recovery, ten owners and publication.
F. Academy initialization requires learning manage, Builder write and page_builder;
   Builder endpoints derive active tenant and check project ownership/permissions
   and commercial entitlements. Composite tenant/profile FKs protect bindings.
   Public runtime resolves tenant from trusted website/host context, reads only
   bound published schema and published learning content, and uses shared renderer.
G. Missing: consolidated owner metrics, applicant-private support documents,
   exchange opportunity lifecycle, configurable verified institution classification,
   and academy contact submission ownership/admin access. Payment adapter interface
   exists and verified events reuse commerce; reconciliation needs an explicit
   adapter contract/readiness documentation. No live adapter/credentials exist.
H. No duplicate page/project/header/footer engine found. Existing Reports and
   Academy & Access hub are reused rather than replacing those screens.
I. No PAU identity, domains, prices or academy syllabus are seeded. Programme
   names/rules remain tenant settings with existing commercial module gates.
J. General Forms/collections/workflows/roles/users and connected forms are explicitly
   excluded by Academy schema validators (132/133 and Python profile). Platform
   `/public/contact` already stores `contacts`, but has no tenant/project context;
   extend that mechanism for Academy contact, not the excluded Forms subsystem.
   Builder upload URLs are publicly mounted: private support documents must use
   the existing private Supabase storage bucket through authenticated access,
   never the public asset URL/mount. All new storage metadata needs composite
   tenant/application ownership and explicit applicant/admin access.

Relevant sources: migrations132/133; services `academy_builder_service.py`,
`elearning_academy_service.py`; routes `builder_routes.py`,
`elearning_academy_routes.py`, `public_contact_routes.py`; Builder
`PageBuilder.constants.js`, `PageBuilder.academyProfile.js`,
`PageBuilder.elementRenderer`, `PageBuilder.siteRenderer`,
`PageBuilder.siteChrome`, `PageBuilder.routing`; AcademyManagementHub,
AcademyLandingPageEntry, AcademyBuilderLanding and AcademyDataBlock.

Additional migrations will extend139 without editing applied history. Release
metadata remains an unselected candidate; production schema115 stays non-migrating.

## Form ownership clarification

Builder Forms methodology/schema/validation/conditional logic/rendering/UX may be
reused, but Builder form definitions and responses remain independent. Existing
programme responses use tenant-owned `academy_applications`; fixed academy
contacts use scoped platform `contacts`, never `builder_form_submissions`.
General E-Learning Forms must own tenant-scoped definitions/responses where
needed. See [elearning-forms-boundary.md](elearning-forms-boundary.md).
