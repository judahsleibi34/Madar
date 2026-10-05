# Fixed learner Academy

Madar owns the responsive Academy layout. Tenant presentation content lives in
`elearning_settings.settings`; courses, offerings, enrollments, progress and
credentials retain their existing sources of truth. This feature has no page
blocks, custom HTML/CSS/JavaScript, layout positions or page-builder records.

Owners configure **E-Learning → Settings → Academy**, save, and choose
**Open Academy**. Enabling Academy also enables the existing E-Learning flag.
A tenant needs its existing Madar public address in `website_settings`; no second
address or branding system is created.

The existing tenant-host router mounts `/academy/*`. The same fixed experience
is available at `/academy/:subdomain/*` for local/shared-host browsing. Home,
`courses`, `courses/:courseId`, `plans` and tenant `login` share one shell.
Hosted `/my-learning/*` mounts the existing learner player rather than the
website page builder. Workspace My Learning also uses Academy navigation when
the tenant has enabled Academy. Main navigation labels remain normalized.

## Read and access boundaries

`GET /public/academies/:identifier` and its scoped
`/courses/:courseId` endpoint reuse the existing website identity resolver,
including canonical host/path validation and active-tenant checks. Responses
are private/no-store and vary on Cookie. A validated active member of that exact
tenant can receive personalized state; a foreign session receives only the
public projection. Client tenant/user query parameters are not an authority.

Migration 130 adds only a service-role RPC, `get_elearning_academy`. It consumes
`elearning_catalog_eligible`, `elearning_course_cta` and the existing learner
runtime. Anonymous/authenticated SQL roles cannot execute it. Before schema 130,
Academy endpoints fail closed. No applied migration through 129 was changed.

The public projection includes published catalog-visible free/paid courses,
active relevant Commerce offerings, active instructor names, published section
names and published lesson counts. It never contains lesson bodies, assessment
questions/answers, learner records or credentials for guests. Private courses,
drafts, archives and hidden catalog entries are excluded. Owned progress and
credential summaries come from the same runtime used by the learner player.

The personalized Continue feed consumes the bounded existing My Learning RPC,
including authorized private enrollments, and returns up to three courses whose
existing progress status is active. Those private courses do not enter Catalog.
No complete lesson content is requested to build cards. Resume lesson/assessment
IDs come from the existing stored-order runtime. React dispatches the supplied
CTA; it does not resolve entitlements or calculate completion percentages.

## Presentation and commerce

Hero text, image, CTA text, benefits and featured course IDs are bounded typed
settings. Featured selection is validated against published, eligible courses
in the current tenant. Featured cards read current course records. Courses and
plans use one reusable card/action architecture. Empty sections disappear;
Catalog supports search across existing titles/descriptions/instructor names
and the existing free/paid access metadata. Saved learning labels remain content
labels.

Brand/logo and validated theme colors reuse existing learning/website branding.
Public metadata uses the Commerce `StorefrontSeo` head lifecycle, with an
optional safe public-page title/path override. There is no separate SEO system.
The global E-Learning skeleton, logical RTL layout, keyboard focus, mobile menu
and reduced-motion styles are reused.

Existing managed tenant images can be selected/uploaded using the same upload
pipeline. Only enabled Academy logo/hero images and eligible public course covers
become public image references. Draft/private/hidden course covers and learning
attachments retain private rules. Upload commercial-review gates remain intact.

Checkout uses the existing offering/immutable checkout/payment-event APIs and
existing Checkout UI. The local adapter remains gated to explicit development
configuration and loopback Docker PostgreSQL. Unconfigured live payments remain
disabled. Entitlements remain separate from actual enrollment. Sign-in reuses
existing tenant authentication and resumes a bounded same-Academy path with a
full reload; mutations still require an explicit user action and backend access.

See [local verification](verification/elearning-academy/README.md). Production
was not modified or deployed. Local schema is 130; release metadata, mirrored
migration, checksums and policy documentation include this expansion.

## Academy management and visual authoring (schema 131)

`E-Learning → Academy` is a management hub with distinct Edit Landing Page,
Open Academy and Open Student Platform actions. Platform enablement and learner
registration remain configuration; landing copy and course selection belong in
the existing visual Builder. Saved legacy presentation fields are preserved for
one-time initial composition and are not reseeded on subsequent visits.

Academy editing opens the restricted single-page Builder directly on its native
component library/canvas/Inspector. The profile excludes page management,
Forms, Reservations, booking and unrelated Users/Header & Footer workspaces;
existing server/database allowlists remain authoritative. Section composition
supports addition, removal, selection and persistent ordering through normal
Builder state/history/save/publish. Course and plan widgets retain live data.

Open Student Platform opens `/my-learning` with the current Madar identity and
actual enrollments, fixed learner navigation and an authorized Back to Admin.
It creates no preview account or progress. See the [UX verification report](verification/academy-ux/README.md).
