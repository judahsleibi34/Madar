# Affiliate architecture audit — 2026-10-11

Investigation completed before implementation. Schema141, independent Forms,
Builder, the course player and canonical referral/accounting engines are retained.
The existing local testing account has programmes disabled. Baseline native Chrome
checks in English/Arabic at1440/390px passed without page errors or horizontal
overflow; enabled affiliate lifecycle states require separate labeled fixtures.

| Area / current route | Components / APIs | Works and retain | Missing, confusing or duplicated; correction |
| --- | --- | --- | --- |
| Public Academy → application | `AcademyDataBlock`, Academy login/register, `academyReturnPath`, public academy bootstrap | Tenant-specific terms/capability projection; login/register return validation | Programme block mixes terms and defaults to Tuition; no distinct affiliate CTA. Render one CTA per actually supplied programme; affiliate CTA opens focused account destination. |
| Application/status `/my-learning/programmes?kind=affiliate` | `AcademyProgrammesPage`, `/elearning/programmes/account`, POST `/applications` | Required questions, terms acceptance, idempotency, tenant/user scoping | Approved/pending/suspended applicant still sees a submission form that SQL rejects. Hide duplicate application while an open record exists, show state plus affiliate destination; allow rejected applicant to reapply. |
| Owner review `/e-learning/programmes/affiliate` | `AcademyProgrammeOwner`, management list/review/member profile | Owner-only revision/reason checks, approval/rejection/suspension/reactivation | Preserve existing owner tables and review authority; do not add learner review controls. |
| Affiliate status/dashboard | No focused page; applications mixed with support/exchange/withdrawals | `account.applications` contains tenant-scoped affiliate status | Add focused summary/dashboard using existing account/referral projections; no role promotion or client status store. |
| Referrals `/my-learning/referrals` | `LearnerAccount`, `/elearning/my-learning/referrals` | Eligible code/link and clipboard fallback; balances/history retained even when code eligibility stops | No visible code/share button; finance requests unnecessarily depend on course list. Reuse focused finance pages; show code, optional native share and structured history. |
| Tracking/sales | `get_academy_referral_account`, public referral click POST | Canonical attribution and counts; verified sales in wallet; history limit50 | No private click analytics, referred identities or purchase details returned. Document omissions, never infer identities or show raw internal IDs. |
| Rewards `/my-learning/rewards` | Same account projection | Earned/reversed rows, dates, amounts/currencies; simulated balances separated | Referrals and rewards show same unstructured list. Render table; reward view excludes attribution-only rows and uses actual accounting timestamps/status. |
| Wallet `/my-learning/wallet` | Referral wallet plus programme account | Available/reserved(`pending`)/earned/withdrawn/debt values are server-owned | Preserve accounting; label reserved amount correctly. Keep configured withdrawal link and no client-editable balance. |
| Withdrawals `/my-learning/withdrawals` | `AcademyProgrammesPage`, POST `/withdrawals` | Configured minimum/methods, details/ownership, idempotency and pending→approved→processing→paid/rejected history | Preserve guards/owner separation; use focused route and table/status records. Simulated rewards remain non-withdrawable. |
| Notifications `/my-learning/notifications` | Existing Madar provider/inbox/outbox, notification action validator | Submitted/review lifecycle/referral/reward/reversal/withdrawal events exist and are tenant/recipient bound | Existing actions target generic Account/Programmes. Normalize only known learner events to the appropriate existing/focused destinations; preserve owner actions and unknown/unsafe action fallback. Generic application review events omit application kind and must remain at the programme status view. |
| Account/profile `/my-learning/account` | `LearnerAccount`, user status/My Learning | One identity for learner+affiliate; password and actual learning statistics | Preserve account; finance pages should not depend on course/progress requests. No duplicate account or global affiliate role. |
| Membership/capabilities | `tenant_service`, programme capabilities/flags, `academy_capability_service` | Active tenant membership required; no enrollment requirement for affiliate APIs; canonical commercial grants still gate direct access | Learner shell has no dedicated affiliate navigation. Add capability+configuration-aware affiliate link, keep learning navigation for combined accounts. |
| Suspension/reactivation | `academy_review`, `academy_can_refer`, referral projection | Status is `(tenant,user,kind=affiliate)`; open-record uniqueness; suspension preserves history; reactivation reuses code | Explicit state/help and no duplicate apply form. Suspension does not universally revoke referral eligibility: registration policy or an independently qualifying verified purchase may still permit it. UI must use returned code/can_refer, not override SQL policy. |
| Affiliate-only | Member RPCs, My Learning empty-list projection | No purchase, enrollment or learner row required for application/approval/code | Shell currently bootstraps via My Learning, although empty courses work. Focused affiliate/finance routes should bootstrap independently from account/referral/user APIs; course player remains untouched. |
| Mobile/RTL/theme | Shared learner shell, theme tokens, Inter/IBM Plex Sans Arabic | Existing drawer/logical spacing and design system | Reuse shared panels/status chips/tables; wrap long links, contain table overflow, verify all four language/viewport combinations. |
| Security | Tenant/user filters, member/owner checks, SQL RPCs, immutable history, canonical reward privileges | Existing tests cover same-global-user/different-academy status, foreign tenant review/attribution denial, role preservation and no direct reward edits | Keep internal IDs only as React keys/request identifiers. Verify candidate cannot review or submit another tenant/user authority in payload. No frontend IDs grant permission. |

## Forms boundary decision

Retain specialised affiliate approval. Schema138 validates fixed required business
questions and status transitions;139 preserves ownership; approval determines
canonical referral eligibility. Generic E-Learning Form responses must not create
affiliate status. Reusing the field/schema methodology for configurable questions
would require a versioned question definition, business-field mapping, terms
snapshot compatibility and immutable application answers. This is a larger explicit
architecture change, deferred here. Builder submissions are never used.

New Exchange applications should use opportunity-associated E-Learning Forms.
Existing specialised Exchange records and routes remain compatible; this pass
does not expand or refactor that workflow.

## Implementation scope selected after audit

Focused affiliate dashboard/status with summary links; separate course-independent
affiliate/finance route bootstrap; prevent duplicate application UI; code/copy/share
and structured referral/reward history; capability-aware navigation; distinct public
affiliate entry; narrow notification destination compatibility. Existing financial
authority and owner workflows remain unchanged. No payments, payout execution,
EduHope configuration, new engine or migration is planned.

## Implementation and E2E report

1. **Architecture:** affiliate status remains an academy application keyed by
   tenant and user, not a global account/staff role. Existing member checks,
   capability ledger, referral RPCs, reward/reversal records, wallet calculation,
   withdrawal reservations and owner review remain authoritative.
2. **Problems corrected:** missing focused dashboard, duplicate application forms
   for open records, generic public application CTA, finance pages depending on
   course-list requests, hidden referral code/share, unstructured history and
   overly broad notification destinations.
3. **Application:** `/my-learning/affiliate/application` reuses the specialised
   application component and existing idempotent POST. Required questions and terms
   retain SQL validation. Submitted/under-review/approved/suspended records hide the
   duplicate form. Rejected applicants can reapply. No purchase requirement added.
4. **Dashboard:** `/my-learning/affiliate` shows actual application state, existing
   referral counts, balance summaries separated by currency/simulation, verified
   sales when returned, wallet availability, up to three referral and withdrawal
   activity rows each, and focused-page links. Loading/error/retry states retained.
5. **Referral UX:** shared `ReferralInvitation` renders an eligible code and public
   URL, copy/manual fallback, and browser Share where supported. Dashboard and
   referrals reuse that widget. Returned code/eligibility controls visibility;
   internal application/reward IDs are never rendered. No click counts invented.
6. **Rewards:** shared account view now renders structured date/amount/status
   tables. Reward view uses earned/reversed rows and their accounting timestamps;
   attribution-only pending records remain in Referrals. Simulated amounts retain
   explicit demo labels and separate balances. No reward amount is editable.
7. **Wallet:** existing available, reserved(`pending`), earned, withdrawn and debt
   projections retained. UI calls the reserved value “Reserved amount.” No client
   ledger, editable balance or payout engine added.
8. **Withdrawals:** existing focused page retains configured minimum/methods,
   amount, payout information, ownership confirmation, idempotency and history.
   Owner actions remain in existing owner routes; affiliate pages expose none.
   Pending→Approved→Processing→Paid and Rejected states remain unchanged.
9. **Suspension/reactivation:** clear suspended state/help, no duplicate application,
   historical balances/activity retained under existing read policy. SQL eligibility
   decides whether a referral code is returned; suspension does not override another
   valid registration/purchase eligibility rule. Reactivation reuses the code and
   application. No history/role changes performed by the UI.
10. **Combined accounts:** one user/session and tenant membership serve learning and
    affiliate functions. Shared learner shell adds a capability/configuration-aware
    Affiliate dashboard link; existing Learning, Notifications and Profile remain.
11. **Affiliate-only:** affiliate/finance/programme route bootstrap uses existing
    `/elearning/programmes/capabilities`, now returning the same public academy
    presentation as My Learning. Those routes and their finance views do not fetch
    courses to authorize/render account functionality. A route regression proves
    course requests are not made. The ordinary Profile still shows real learning
    statistics (empty when none), without requiring purchase or enrollment.
12. **Notifications:** existing Madar inbox/event/outbox/delivery remain. A read-time
    projection sends known affiliate-submitted, referral-attributed, reward-earned/
    reversed and withdrawal recipient events to focused routes. It preserves
    immutable event data, tenant mismatch checks, explicit/owner/unknown actions.
    Client/server allowlists add only Affiliate dashboard/application paths.
    Generic application status events omit programme kind and retain the existing
    programme status destination rather than guessing affiliate identity.
13. **Public entry:** programme information presents distinct CTAs only for the
    actual public programme projection. “Become an affiliate” opens the focused
    dashboard, which resolves application/status; guests pass that same destination
    through Academy login/register return validation. Approved/suspended/pending
    users reach status, not another application prompt. Unit coverage verifies the
    guest affiliate destination. Existing Exchange navigation is retained.
14. **Owner↔affiliate E2E:** native PostgreSQL rehearsal uses a distinct candidate
    with learner membership but no learner record, course, purchase or enrollment.
    Candidate applies and cannot self-approve. Owner approves; code becomes eligible.
    Synthetic verified-provider sales use existing attribution/reward authority.
    Owner suspension removes the code for this policy, preserves wallet, then
    reactivation restores the same code. Candidate requests withdrawal and cannot
    review it; owner moves it through Approved/Processing/Paid. Reservation clears,
    total withdrawn updates, membership remains learner and no learner row is added.
    This is disposable test data and **not a live payment/payout claim**.
15. **Forms:** independent E-Learning definitions/responses and Builder storage were
    untouched. Specialised approval stays in its existing workflow. Configurable
    question schemas require an explicit versioned mapping design and remain deferred.
    No generic form submission confers affiliate status. New Exchange applications
    should use associated learning forms; legacy Exchange was not expanded.
16. **Mobile/RTL:** native Chrome checks at1440px/390px in English/Arabic. Native
    configured account: login and disabled Affiliate access. Enabled candidate/owner
    browser lifecycle: explicitly intercepted API fixtures; application, approval,
    code/link, referral/reward tables, wallet, withdrawal through Paid, suspension and
    reactivation all pass. Notifications page remains the real existing inbox.
    No page errors, private review-note display or document horizontal overflow.
    Screenshots/logs: `/tmp/affiliate-qa`, `/tmp/affiliate-browser-final.log`.
17. **Security/capabilities:** active membership/session tenant supplies authority;
    capabilities and programme flags control navigation, API and SQL remain guards.
    Tests verify foreign-tenant actions and unchanged global membership role, deny
    candidate review/direct reward edits, and preserve owner/foreign notification
    actions. Browser fixture submissions verify no client tenant/user authority IDs.
    Disabled native programme access remains rejected; no local academy was enabled.
18. **Files/routes:** new `AffiliateDashboard.jsx`, `ReferralInvitation.jsx`,
    `AffiliateDashboard.test.jsx`, `AffiliateRoutes.test.jsx`; updated learner shell,
    account and specialised application UI, surrounding route declarations, existing
    account-context service, public Academy programme block, learner CSS and English/
    Arabic copy. Existing account/application/public-block/notification tests extended.
    Backend changes are academy metadata in the existing capabilities GET, narrow
    notification action allowance and inbox destination projection. New
    `test_affiliate_account_experience.py` and an affiliate-only database lifecycle
    regression cover them. No course-player body, accounting engine or schema change.
19. **Validation:** final results are recorded below. Backend uses the exact isolated
    workflow environment, not the local production dotenv. Database rehearsal creates
    and removes only its marked disposable database. Application data/configuration
    are retained. All345 migration/release JSON checksums match the regression-pass
    inventory; both namespaces remain001–141 with no142.
20. **Remaining gaps:** private referral API exposes only the most recent50 rows,
    aggregated counts and limited accounting timestamps. It provides no referred-user
    identities, purchase/source detail, click analytics or historical pagination.
    These are not fabricated. Generic application-review notification payloads lack
    programme kind; historical push payloads retain their original broad actions
    (focused projection is applied when reading the inbox). Owner history remains
    separate from learner status. Configurable affiliate questions and routing new
    Exchange submissions through associated Forms require later scoped architecture
    work. Full enabled browser lifecycle against native application HTTP, new-account
    registration and native browser cross-account denials were not executed: enabled
    browser API transitions are fixtures; native SQL independently verifies authority.

No real provider, live checkout or payout was enabled. No EduHope course, prices,
rewards, terms or eligibility configuration was applied. Existing historical test
fixtures retain their values only in the marked disposable database. Production
staging/deployment/backup acceptance was not attempted and is not implied.

## Final validation results

| Check | Result |
| --- | --- |
| Focused frontend UI/contracts | 50 passed before the final shared-widget/bootstrap regression additions; the final complete suite covers those additions. |
| Complete frontend suite | 205 files passed;1,516 tests passed, one existing skip;47.90s. |
| Frontend lint/build | Passed; API-origin/theme/tenant bundle checks passed. Production bundle-origin check explicitly skips in this non-production build, so no production artifact acceptance is claimed. |
| Focused backend | 17 passed;0.092s; no external attempts. |
| Related backend modules | 187 passed;6.602s; no external attempts. |
| Complete intended backend CI suite | **2,927 discovered;2,394 passing cases;533 explicit skips; zero failures/errors;39.233s; no external attempts/sites.** |
| Disposable schema141 rehearsal | **299 passed;15.921s**, plus immutable001–141 migration/upgrade/preservation/rollback checks; marked database removed. |
| Native Chrome | Disabled account checks plus labeled enabled lifecycle fixtures: English/Arabic ×1440/390px passed; no page errors/document overflow. |
| Release/source checks | Dependency locks, mirrored migrations, transitions, secret hygiene and forward-release contract passed. Historical013/014 duplicate warnings retained, zero migration errors. |
| Locked backend image / pip | Image built; no broken requirements. |
| Immutability / whitespace | All345 migration/release checksums unchanged, exact001–141 namespaces, no142; `git diff --check` passed. |

The backend count increased by10: three new account/notification tests plus the
affiliate-only database method discovered in seven inherited fixture classes.
Those seven opt-in database cases skip in the isolated CI unit run and execute in
the native disposable rehearsal; skip count consequently increased from526 to533.
This passes the backend regression gate for continued architecture work, with the
browser/native and deferred-feature limits above retained explicitly.
