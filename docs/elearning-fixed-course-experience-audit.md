# Fixed tenant product experience: Commerce and Learning

Audit completed before implementation, 2026-10-11. Current source is authoritative;
the proposed conceptual hierarchy does not replace the existing model.

## E-Commerce methodology

| Question | Current implementation and boundary |
| --- | --- |
| Fixed platform structure | `EcommerceStorefront.jsx` owns StoreHeader, StoreCart, StoreCheckout, StoreConfirmation, StoreCategories, StoreContact, StoreProductDetail, ProductGallery, ProductCard, landing sections and footer. Product galleries/options/purchase actions and catalog filters are application components. |
| Merchant configuration | API site/catalog/product payloads supply identity/logo, localized descriptions, product/media/options/variants, categories/brands/tags, pricing/inventory, promotions, delivery, loyalty and contact/social information. Configured landing slides and featured collections fill predetermined sections. |
| Theme | `normalizeStoreTheme` maps saved colors to scoped `--store-*` variables. Draft previews use the same renderer. Identity and locale change presentation; CSS owns responsive structure. |
| Non-rearrangeable structure | Product detail, catalog, checkout, cart and confirmation placement/navigation are fixed React components, not merchant-authored Builder layouts. Landing content configuration is not permission to replace checkout or product shells. |
| Standard routes/components | `TenantSiteRoutes` selects the tenant from the branded host; canonical `/shop`, `/shop/catalog`, `/shop/categories`, `/shop/product/:slug`, `/shop/contact`, `/shop/checkout`, `/shop/confirmation/:token` share one storefront. Categories use catalog query filters, not a separate category-detail renderer. Legacy tenant paths redirect; admin preview supplies a separate base path. |
| Tenant data injection | `ecommerceApi` fetches public profile/catalog/detail and action endpoints using the resolved tenant. The storefront selects the request from the route and query filters, fences stale results with request keys and cancellation, and injects returned data into its fixed components. Cart storage is tenant-keyed. Server publication, commerce availability and action checks remain authoritative; frontend buttons are not entitlement enforcement. |
| Reusable methodology | Separate tenant resolution, domain data and fixed presentation; route-specific loading skeletons; explicit error/empty states; localized labels, prices and RTL; scoped theme variables; responsive drawers with keyboard handling; stable item identity; private/authenticated authority for account actions. Core storefront requests/rendering do not load Builder projects to construct product pages. |

Commerce CSS contains desktop/mobile layouts, logical properties and explicit RTL
rules; the root supplies language/direction. Storefront request keys suppress old
detail results during route changes. This is a methodology reference, not a reason
to import Commerce services/components into Learning. Existing generic legacy
`ecommerce-*` dashboard style names in Learning are shared styling history, not
commerce data dependencies.

## Current E-Learning map and classification

| Part | Current source / behavior | Classification / decision |
| --- | --- | --- |
| Public course route/overview | Academy `/courses/:courseId` uses `Details`, public description/cover/instructors/outline/access offerings and `PrimaryAction` | Good: keep public presentation and enrollment boundary. |
| Marketing website | `AcademyPresentation` renders published Academy Builder content; promotion actions lead to enrollment or the fixed learner route | Good: keep Builder separate from private course rendering. |
| Authenticated routes | `/my-learning`; `/courses/:courseId`; `/courses/:courseId/lessons/:lessonId`; `/courses/:courseId/assessments/:placementId`; certificates/catalog/plans/account under the same base | Good: standardized platform-owned routes across tenants. |
| Learner shell | `ELearningLearnerShell`, academy appearance/theme tokens, fixed account/navigation and mobile drawer | Duplicated/confusing: without an academy, Home and My Learning target the same route. My Learning loses active context on nested course routes. Fix navigation matching, not tenant permissions. |
| Course overview | `CoursePlayer` renders heading/progress then curriculum; on mobile the entire curriculum and its only Continue action are hidden in a drawer | Genuine UX defect: retain curriculum drawer, provide a visible course overview action and summary outside it. Desktop remains the existing outline. |
| Curriculum / sections / lessons | Ordered `data.sections[].lessons`, server names and configured terminology; server section progress and completion | Structurally correct, visually improve section separation, selected lesson, readable hierarchy and touch targets. Keep sections/lessons; do not invent levels/topics as new models. |
| Content renderer/blocks | Shared `ContentBlockRenderer`: structured text, audio, video, assessment; archived blocks excluded | Good: keep shared author-preview/learner renderer. This is course content, not Builder page rendering. |
| Progress | `Progress` uses server eligible lesson counts and percentages; `progress.completion` independently represents formal completion | Good, visually improve: retain distinction between lesson progress and required assessment completion. Never infer formal completion from 100%. |
| Resume | Server `continue_lesson_id`, then `continue_assessment_id`; public catalog provides server `resume`/CTA | Good: keep server ordering/rules. Confusing assessment view currently repeats a Continue link to itself in the curriculum. Show resume at course overview and after assessment only when its destination differs from the current assessment. |
| Locks | Server lesson/placement locks and guarded reads/completion/media; required assessments disable explicit completion | Good, visually improve: make locked lesson state text-visible and add existing prerequisite guidance. No client unlocking. |
| Explicit completion | Existing POST replaces learner snapshot; updates progress, next locks and credential | Good: retain explicit idempotent command, no completion on opening or automatic advancement. |
| Assessments / results | Section/course placements and inline blocks use `AssessmentBlockRenderer`, guarded start/submit, immutable attempts, score/pass/limits and refresh callback | Good: preserve renderer and attempt authority; improve selected placement highlighting and post-result resume transition using refreshed server snapshot. |
| Certificates | Credential CTA from server; `MyCertificates` / `CredentialView`, guarded download/verification, status/snapshot | Good: keep existing issuance/access and formal completion boundary. |
| Previous / next | Flattened ordered eligible lessons; links omit locked previous and display next lock until fresh completion response | Structurally correct, visually improve: clearer next action for completed lesson; keep sequence and explicit completion. |
| Mobile | Shell drawer at 900px, course drawer at 850px; focus trap/Escape/return focus shared hook | Good mechanism; overview action defect above. Duplicate earlier mobile outline CSS conflicts with later full-height drawer rules: consolidate. |
| Arabic / RTL | Translation direction and tenant labels, shell logical spacing/drawer direction | Good foundation; preserve translated lock/current/assessment cues, logical styling and narrow layout. |
| Data loading / access | `elearningPlayer` private/no-store API; course entry keyed by course/lesson/placement; server tenant membership/enrollment/publication/progression authority | Good: keep guarded service/RPC and fresh snapshots. Initial My Learning call and list refresh are duplicated but serve shell metadata versus returning-list freshness; no speculative caching rewrite. |

## Authorized optimization scope

Improve the current player/shell only: visible overview/resume, fixed responsive
curriculum hierarchy and states, assessment transitions and navigation context.
Use current Academy tokens and shared Madar controls. No new course/content model,
Builder lesson layout, cross-domain dependency, account grants, payment setup,
backend, migration, deployment or production mutation is needed.

## Implemented optimization and validation

- Course overview now exposes a fixed resume panel outside the mobile curriculum
  drawer. Its destination still comes from the guarded server snapshot.
- Curriculum retains the same sections/lessons/placements, with section dividers,
  selected lesson/assessment highlighting, visible locked labels and prerequisite
  help. Completed lessons give the unlocked Next action primary emphasis.
- Passing a section/course assessment offers the refreshed server next step;
  the current assessment never receives a Continue link back to itself. Attempts,
  results, completion requirements and certificates retain existing authority.
- Learner navigation removes duplicate Home when no academy exists and highlights
  My Learning on course routes. Academy identity/logo/theme are retained.
- Native browser inspection additionally identified inherited style defects:
  generic button styles exposed mobile curriculum controls on desktop; the Arabic
  global gradient rule painted a heading background instead of readable text.
  Scoped learner rules correct both. The shell Notifications label now has the
  missing English/Arabic translation. Layout spacing is scoped to the player.

Validation uses the existing local testing account, without enrollment grants,
course mutations, completion commands or payment configuration. The native API
returned six existing enrolled courses. Chrome checked a real course overview
and its available lesson in English/Arabic at 1440px and 390px: visible resume,
desktop/mobile control distinction, mobile drawer open/Escape close, shared lesson
content, no document overflow and no page errors. Screenshots are in
`/tmp/fixed-player-qa`. Browser checks do not claim new assessment submission or
certificate issuance; their existing behavior remains covered by retained tests.

Frontend suite: 202 files, 1,497 passed, one existing skip. Added two regressions
cover overview resume placement, duplicate navigation/current context, visible
locks and assessment resume behavior without automatic completion. Full lint and
production build with `/api`, API-origin/theme/bundle-origin/public-tenant-bundle
audits pass. Migration tree/transition, forward release, dependency lock and
secret hygiene source checks pass; historical duplicate migration warnings and
existing build chunk-size warnings remain. `git diff --check` passes.

No backend/schema/release metadata changed for this optimization. Production
Docker/staging/backup/upgrade/deployment gates were not executed by this local UI
pass, and no production readiness or deployment is claimed.
