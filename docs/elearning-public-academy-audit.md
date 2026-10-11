# Public Academy runtime audit and optimization

## Investigation completed before implementation

Source review covered TenantSiteRoutes, ELearningAcademy/AcademyNav/AcademyBuilderLanding,
AcademyDataBlock/AcademyFormBlock/AcademyContactBlock, LearningFormRenderer,
PageBuilder routing/chrome/profile/schema validation, StorefrontSeo, public Academy,
Forms/contact/credential routes, hosted identity resolution, authentication continuations,
Academy capability/programme/Exchange services, commerce/provider boundaries and migrations131–142.
The following inventory records the pre-change findings. Validation and corrections follow below.

| Area | Existing implementation and working boundary | Proven gap / decision |
| --- | --- | --- |
| 1 Tenant/host | Hosted `/academy/*`, main `/academy/:subdomain/*`; server resolve_website_settings enforces canonical host identity before tenant-active lookup. Legacy aliases only main host. Foreign session treated as guest. | Preserve resolution and membership authority. |
| 2 Publication/preview | Bound Academy project reads tenant/profile/status-filtered published_schema only. Owner draft preview uses existing Builder and separate owner Form read. | An explicitly bound unpublished/missing project silently falls back to legacy default website; public Academy bootstrap omits website_publish runtime gate. Correct these lifecycle defects. Keep never-bound legacy default compatibility. |
| 3 Pages/navigation | Strict default page, arbitrary validated nested slugs, unique path resolution, published snapshot only; shared Builder chrome handles logo/home, page active states, responsive navigation. Builder publishes whole snapshots, not per-page statuses; unpublished pages are pages absent from snapshot. | Authenticated Builder header still offers login/signup. Fixed navigation lacks active indicators. Missing pages are indexable. Default footer can duplicate chrome when schema has no explicit siteChrome; suppression is ignored. |
| 4 Courses | SQL131 projects only published/catalog-eligible public courses, published outline counts and active linked instructors. No protected lesson bodies/questions. Home and detail API return the same unbounded catalog scope; frontend selecting a course from bootstrap is valid. | Preserve fixed course/player; unavailable course must be noindex. |
| 5 Auth | Tenant login/register reuse Madar auth, canonical learning membership, email-domain/verification policy, safe server/client return handling and referral continuation. | Client validation omits NUL rejected by server. Correct parity. No second login for active session. |
| 6 Access | Existing CTA/enrollment, authorized resume/progress/credentials and commerce authority; free enrollment reaches fixed My Learning. | Buy/Subscribe appears before the existing account projection establishes local simulation availability. Expose unavailable state before a transaction CTA, retaining existing test adapter only. No provider integration. |
| 7 Affiliate | Builder programme component links through Academy login to `/my-learning/affiliate`. Existing application/status service owns eligibility, pending/approved/suspended/reapply and financial authority. | No duplicate public workflow. Preserve existing owner separation and status UI. |
| 8 Support | Configured public programme terms/name, capability/flag-filtered projection, login return to existing specialized tuition application/status. | Action label ignores configured programme name. Correct presentation only; specialized backend stays unchanged. |
| 9 Exchange | Schema142 public RPC filters tenant/published opportunity, active associated Form, deadline/capacity; member detail and Forms submission retain eligibility, tenant, opportunity context and separate decision authority. | Public View opportunity jumps straight to login without displaying full public detail. Expand details in the existing Builder block before Apply. Programme link appears on141 despite new flow requiring142 + Forms/public_form_links; hide unavailable new entry. No new reserved CMS path or legacy submissions. |
| 10 Forms | Independent E-Learning definitions/versions/responses/files, bound published Builder reference, active/access checks, conditional shared validation, multipart bounds, durable idempotency key per answer revision. Standalone Exchange entry uses opportunity authority rather than Builder placement. | Submission-time401 has only generic error; add contextual login recovery without storing answers/files in browser persistence. Public placement must also respect Website entitlement. |
| 11 Contact | Existing reusable contact block and tenant-derived published-project endpoint, Website entitlement, validated/rate-limited payload; owner contact inbox uses current shared contacts scope. | Preserve endpoint/persistence. No native contact mutation needed for audit. |
| 12 Dynamic components | Existing course collection/featured/continue/plans/instructors/programme/opportunity/contact/Form components cover requested layouts without copying records. Guest continuation hidden; instructor links restricted to projected catalog. | Reuse these components; no new CMS/component family. |
| 13 Credentials | Existing learner certificates/private PDF and rate-limited token-based `/verify/credential/:token` public verifier. Backend allowlist controls disclosure and revoked status. | Preserve stable certificate engine; no private credential listing on public site. |
| 14 Language/layout | Shared i18n language switch, responsive Builder artboards/chrome, themed fixed routes, RTL text with LTR canvas geometry. | Verify English/Arabic desktop/mobile; only targeted layout corrections justified by browser evidence. |
| 15 Lifecycle | Active tenant lookup, enabled/academy flags SQL131, capability-filtered programmes/contact, Forms active/public access, guarded Exchange142 lifecycle and retention. | Fix bound publication/Website gate and new Exchange public entry gates. Retain historical responses/applications, decisions and fixed learner access. |
| 16 States | Bootstrap skeleton/error retry, strict missing page, empty catalog filters, editor-only setup placeholders, Form success/error. | Add recoverable submission401 and accurate checkout unavailable/loading states. Keep empty optional published components hidden. |
| 17 Metadata | Existing StorefrontSeo head/canonical machinery and course metadata. | Published custom page names ignored; missing page/course indexed; trailing login slash can be indexed. Reuse metadata engine with resolved page and fixed route classification. Builder has no independent page SEO fields; do not invent a new CMS model. |
| 18 Security | Canonical host tenant derivation, tenant-scoped project/RPC/Form/opportunity reads, strict published schema, membership/eligibility, private no-store bootstrap and protected attachments. | Website lifecycle omission is a security/entitlement gap. No private application answers or owner notes enter public projections. Tests must prove denial before content reads. |

## Boundaries

Builder owns website pages, slugs, navigation/chrome/theme, content and placement only.
Learning owns catalog, curriculum/player/progress/assessment/credentials. Forms own immutable
answers/files; Exchange owns context, decisions/capacity. Affiliate/referral/accounting and
specialized Support remain independent. No payments, EduHope configuration, migrations,
release selection, local database upgrade, player design or legacy Exchange expansion is authorized.

## Validation and final implementation

The audit led to targeted corrections only. The repository contains earlier uncommitted
architecture work; the file inventory below is limited to this pass.

1. **Architecture map.** `TenantSiteRoutes` owns hosted/main Academy entry. The public
   bootstrap/course endpoints call the fixed SQL131 catalog/CTA authority. Builder supplies
   the published snapshot to the existing SiteRenderer and chrome. Shared dynamic blocks
   consume the Academy composition context; they do not copy authoritative records.
2. **Builder/runtime boundary.** Flexible pages, navigation, logos, theme and placement
   stay in Builder. Fixed course/catalog/player/learner/programme/account routes stay in
   Madar. No CMS, new page schema, course-player change or duplicate application store.
3. **Routes/publication.** Published arbitrary/nested pages use strict snapshot resolution.
   Bound missing/draft/empty websites now return404 rather than resurrecting the default
   website. Never-bound legacy academies retain their existing default presentation.
   Public content requires the existing Website runtime entitlement. Builder header/footer
   suppression is honored, duplicate fallback chrome removed, fixed navigation is active.
4. **Course flow.** Existing covers/descriptions/instructors/outline/offerings and enrollment
   continue through canonical services. Missing course URLs are noindex; invalid courses
   no longer trigger automatic enrollment from a crafted return. Detail URLs with trailing
   slashes retain course metadata. No course API or player redesign was needed.
5. **Affiliate flow.** Public capability-filtered terms/action preserve tenant Academy login
   and `/my-learning/affiliate` continuation. Existing pending/approval/suspension/reapply
   services and financial records remain unchanged; no public owner-review endpoint.
6. **Support flow.** Action now uses the configured Support name and keeps the existing
   `/my-learning/programmes?kind=tuition` continuation. No specialized backend changes.
7. **Exchange → Forms.** Existing public opportunity cards expand full description,
   requirements, dates/deadline/capacity before contextual Apply/login. This uses native
   accessible details/summary inside the same Builder block, avoiding another reserved
   page path or CMS collision. New programme entry requires142, Exchange + Forms grants
   and `public_form_links`; public SQL142 still filters lifecycle/deadline/capacity and active
   associated Form. Member eligibility and independent Forms/decision authority remain.
8. **Generic Forms.** Public placement requires both Website and existing Forms authority,
   tenant-bound published reference, active/access checks. Submission401 now offers a
   contextual login link preserving page/query/hash; answers remain in component memory,
   not local/session storage. A retry without editing uses the same idempotency key. Hidden
   answers, conditional validation and file handling remain in the shared Forms renderer.
9. **Dynamic components.** Existing collections, plans, instructors, continuation,
   programmes, opportunity, contact and Form blocks cover the audited public layouts.
   No additional dynamic component family or duplicated persistence was added.
10. **Auth/returns and independent access.** Published authenticated headers now show My
    Learning instead of login/signup. Client return validation also rejects NUL, matching
    server policy. New owner-only `GET /public/academies/{identifier}/preview` supplies live
    composition data while Builder owns the separately authorized draft; it requires an
    E-Learning owner/admin, Page Builder entitlement, active host identity and matching tenant,
    with private/no-store caching. Guest/foreign owner requests reject. Hosted My Learning
    now uses the existing authenticated learning account context instead of public website
    bootstrap, so publication/Website expiration cannot disable authorized fixed learning.
    Hosted tenant membership remains enforced by tenant_service;401 preserves course return.
11. **Theme/mobile/RTL.** Existing shared theme, chrome, responsive artboards and i18n remain.
    Added only fixed active-link styling and bounded opportunity detail spacing/wrapping.
    Native and intercepted browser checks pass English/Arabic at1440 and390 pixels without
    horizontal overflow or browser page exceptions.
12. **Security/entitlements.** New guards reuse canonical operational authority, never a
    test-only production bypass. Public denied Website requests stop before content reads.
    Public Form denial stops before definition/submission authority. Historical responses,
    legacy Exchange applications and accounting are untouched. Public projections contain
    no private application answers/owner review notes. Preview is authorized server-side;
    its internal service flag is not accepted from public request parameters.
13. **Problems fixed.** Bound unpublished fallback, Website bypass, expired Website public
    Form placement, schema141/Forms-ineligible Exchange entry, guest Exchange detail jump,
    incorrect Support action label, redundant authenticated login, inactive fixed menus,
    ignored/suppressed/duplicated chrome, missing/custom/trailing-slash metadata, client NUL
    return mismatch, expired Form submission recovery, unavailable transaction buttons,
    invalid course enrollment intent, and public-bootstrap coupling of preview/hosted learning.
    Checkout uses the existing authenticated account availability read: loading/error retry,
    disabled unavailable actions, and explicit local-test notice. Guest actions say Log in;
    no working live payment is implied. Checkout/provider/accounting authority is unchanged.
14. **Files/routes changed in this pass.**
    - Backend: `routes/elearning_academy_routes.py`, `routes/elearning_forms_routes.py`,
      `services/elearning_academy_service.py`; tests `test_elearning_academy.py`,
      `test_elearning_forms.py`, new `test_public_academy_lifecycle.py`.
    - Frontend: `ELearning/ELearningAcademy.jsx`, `AcademyBuilderLanding.jsx`, `AcademyNav.jsx`,
      `LearningFormRenderer.jsx`; `PageBuilder/blocks/AcademyDataBlock.jsx`, `AcademyFormBlock.jsx`;
      `services/elearningAcademy.js`, `styles/elearning-academy.css`; their affected Academy,
      Forms, dynamic-block and service tests. This audit document.
    - Only new route: authorized Academy preview data endpoint above. No public CMS or
      opportunity path added; existing member detail remains `/my-learning/exchange/:id`.
15. **Schema142 readiness/local141 boundary.** A read-only native SQL check reports141.
    Disposable rehearsal validates001–141, populated141 preservation/rollback, then142
    and concurrent capacity decisions. The rehearsal drops its marked disposable database.
    All349 migration/release artifacts match the pre-pass checksum baseline; no migrations,
    release selection, deployment gating, payment provider or tenant configuration changed.
16. **Validation.** Focused frontend77 passed; full frontend206 files,1536 passed,1 skipped.
    Focused backend34 passed; related modules213 passed; exact isolated CI full backend2951
    discovered,2410 passed,541 expected skips, zero failures/errors and zero external network
    attempts/sites. Disposable DB299 retained tests +8 schema142 tests passed. Lint and
    production build passed, including API-origin contract and tenant bundle audit. Dependency
    locks, mirrored migrations, migration transitions, secret hygiene, forward release/source
    contract, diff whitespace and final container pip consistency passed. Source checks retain
    only the two known013/014 historical duplicate-content warnings.
17. **Native vs fixture evidence.**
    - Native local schema141, actual Chrome/API: guest published home, QA custom page/direct
      refresh, catalog, public course detail and unavailable metadata; authenticated public
      header; all four language/viewport combinations. Local Exchange endpoint returns403
      because programmes are disabled; no enabled native142 Exchange flow is claimed.
    - Actual local QA persistence: one browser submission to the existing public QA Form
      persisted response `a54f0455-e9fc-491f-9a58-3ddc402286e6` under existing Form
      `1f80bc69-de7f-4e07-8211-944d62fc9bb6`. A direct native SQL check confirms that
      exact response; authorized owner HTTP reads its same answers and returns200.
      Authorized native owner preview also returns200. No definition/configuration was
      changed. The submission harness stalled after persistence and was stopped; the
      subsequent owner verification was read-only. The corrected harness then replayed
      the same server-owned idempotency key through the actual browser: HTTP200 and the
      real success UI both passed. Final SQL confirms exactly one QA response after retries;
      the harness stall was response-body inspection, not a failed submission or UI state.
      This is actual schema141 Forms persistence, not enabled native142 Exchange.
    - Intercepted browser fixtures, all four combinations: enabled public Affiliate/Support
      login destinations, opportunity expanded details/Forms continuation, conditional fields,
      multipart PDF selection, submission401 recovery/stable retry, Contact submission,
      nested custom page/direct reload and guest login→same page with authenticated header.
      These intercepted responses are not database persistence or enabled native Exchange E2E.
    - Disposable database: actual SQL persistence, tenant/publication/Forms guards and
      schema142 context/decision/capacity/retention tests; not native browser HTTP142.
    - Evidence logs/screenshots are in `/tmp/public-academy-*.log` and
      `/tmp/public-academy-qa/`; native public inventory and schema verification are separate.
18. **Remaining limits.** Real payments remain deliberately unconfigured. Native local
    Affiliate/Support/Exchange and Contact are disabled, so enabled browser checks use
    labeled fixtures plus existing backend/disposable database tests. Real hosted DNS/TLS,
    email verification delivery and external provider integration are not locally verified.
    The token credential engine is covered by existing regression/database tests; no new
    issued credential was created for native browser verification. Builder publishes whole
    snapshots: an individual unpublished page is absent from that snapshot, not a separate
    page lifecycle store. No unresolved regression or additional public CMS gap was found.
