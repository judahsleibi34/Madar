# Learner experience outside the stable course player

The subsequent [backend regression investigation](backend-regression-investigation.md)
resolved the native-run failures described below: the intended isolated CI suite
passes all 2,917 discovered tests (526 skips), and the separate schema141 rehearsal
passes 292 database tests. All 12 failures and 12 errors were environment issues;
no runtime, assertion or schema correction was needed. The original validation
record below is retained as historical evidence.

2026-10-11. Investigation completed before editing. CoursePlayer, curriculum,
content/progression/assessment/certificate authority and independent Forms storage
are retained. No live payment provider or tenant-specific programme configuration.

| Area / route | Components / existing API | Works / retain | Problems and optimization |
| --- | --- | --- | --- |
| Dashboard: Academy `/dashboard` | `LearnerHome`, Academy public bootstrap `continue_courses` | Real published/enrolled cards and server resume targets | Only two collections; add fixed next-action links and notification summary, without owner analytics. |
| My Learning `/my-learning` | `MyLearning`, `elearningPlayer.fetchMyLearning` | Fresh enrolled courses, progress, exact Continue target, paging | Keep stable list and player; add dashboard navigation entry, no duplicated progress model. |
| Certificates `/my-learning/certificates[/id]` | `MyCertificates`, `CredentialView`, `elearningCredentials` | Guarded list/detail/PDF, immutable design, revoked status, verification link | List uses only course name; show configured certificate title and section/type when actually returned, never infer CEFR. Preserve engine. |
| Notifications `/my-learning/notifications` | Existing `NotificationsPage`, `NotificationProvider`, `notificationsApi` | Inbox/unread/read-all, timestamps, event source, safe tenant-bound actions | No shell unread badge. Existing notification read action supports read, not marking unread. Restrictive client/server path validators reject lesson/assessment destinations; expand only actual fixed guarded routes. Do not create another inbox. |
| Referrals / rewards currently Account | `LearnerAccount`, private `/elearning/my-learning/referrals` | Server code/history, actual balances, simulated currencies separated | Account mixes profile/learning/invitations/rewards, offers generic invitations when referral disabled, manufactures score as lessons ×10. Separate financial views, remove fake score; eligible code required for referral actions. |
| Wallet / withdrawals currently `/my-learning/programmes` | `AcademyProgrammesPage`, `/elearning/programmes/account`, `/withdrawals` | Actual available/reserved/earned/withdrawn/debt, minimum/methods/confirmation/idempotency | Wallet repeated for every programme; actions buried in tabs; hide forms unless configured/capable, add direct withdrawal route, show minimum and methods and submitted payment details/history. No invented money. |
| Support programme same page | Same account/applications API; `AcademySupportDocuments`, guarded private owner-tools document API | Backend configured name/eligibility, upload/read own application documents | Tabs based only on entitlement, not settings; eligibility hidden if no wallet; answers not shown. Show configured eligibility and submitted answers without review notes. |
| Exchange same page | `AcademyExchangeSelector`, `/elearning/owner/exchange/available/for-me`, applications API | Backend available opportunity projection and eligibility | Dropdown loses requested opportunity; details omit dates/deadline/capacity. Honor contextual opportunity and render returned fields. No archived/closed fallback list. |
| Forms contextual Academy Builder | `AcademyFormBlock`, `LearningFormRenderer`, `/public/academies/:tenant/forms/:id[/responses]` | Independent tenant definitions/immutable responses, public/signed-in/enrolled access, conditional logic, validation/pages/files/success | 401 is generic unavailable dead end; provide Academy login preserving exact current page. Keep forms contextual, no blanket student form list. |
| Account `/my-learning/account` | `LearnerAccount`, `/auth/user_status`, My Learning/referral APIs | Profile identity/password and server learning progress | Overloaded/fake score and disabled financial panels above. Keep profile plus concise actual progress; separate referral/reward routes. Profile editing has no existing learner UI and is not invented. |
| Public→learner | Academy `PrimaryAction`, `AcademyLogin`, `academyReturnPath`; Builder `AcademyDataBlock` | Course login/enroll/resume and hosted academy return validation | Programme links all target generic tab; exchange loses opportunity. Use configured kind and opportunity hints in authenticated route, Academy login for guests; hints never provide authority. |
| Capability visibility | `useAcademyCapabilities`, server capability flags and account settings | Server entitlements/member/tenant authority | Shell tests entitlement only, exposes disabled Programmes & Wallet. Combine programme flags with capabilities; financial visibility derives guarded referral/account payload, not guessed grants. |
| Mobile/Arabic/theme | Shared learner shell/tokens, translated controls and logical drawer styling | Existing fonts/theme/RTL | Programme forms inherit owner input/card rules; scope readable learner inputs, grids/tables and heading rules, confirm browser geometry in both languages. |
| Security | Member-scoped learner/credential RPCs; programme `records` tenant/user filters; private documents `application_access`; Forms `public_access`, immutable version/file ownership | Current user/session tenant supplies authority; owner APIs guarded separately | Never render owner notes/history from wildcard application records. Existing source tests cover tenant/recipient/file boundaries; native current-account reads cannot prove cross-user isolation alone. No new frontend tenant IDs. |

The account endpoint returns application records but no learner-permitted workflow
history endpoint. Do not expose owner history or notes as a substitute. Notification
payloads currently commonly link broad course/programme destinations; expanding
validators fixes acceptance of precise supported paths, not historical payloads.
No need to change storage or SQL. Validator backend compatibility is a genuine
missing route allowance and must match its frontend counterpart.

## Implementation report

1. **Architecture:** fixed learner shell and private routes around the stable
   course player, existing Madar inbox, Academy marketing/runtime and independent
   Forms. Server session, memberships and canonical business engines remain authority.
2. **Problems:** overloaded Account, invented lesson score, disabled programme
   navigation, missing unread badge, generic programme links, missing application
   answers, missing form-login recovery and rejected precise learning deep links.
3. **Dashboard:** `/my-learning/dashboard` uses current enrolled course snapshots
   for up to four exact lesson/assessment resume actions and certificate,
   notification and account shortcuts. Empty/completed states do not invent tasks.
   Existing Academy dashboard redirects to this one learner dashboard. My Learning
   remains the paginated course list; no course-player restructuring.
4. **Certificates:** list presents CEFR/section labels only when returned by the
   immutable snapshot. Configured title is used when supplied; existing list API
   removes design, so its usual heading remains course name. Detail already shows
   configured title and verification; PDF/verification/revocation authority unchanged.
5. **Notifications:** shell badge uses existing NotificationContext unread count.
   Matched client/server allowlists now accept real lesson/assessment and new learner
   finance/dashboard destinations. Tenant mismatch, foreign URLs, query/fragment and
   unknown paths still fail closed. Existing inbox/read/source/time behavior retained.
6. **Referrals:** `/my-learning/referrals` shows share/copy only for an enabled,
   available account with an actual eligible server code. Disabled/ineligible accounts
   have no invitation action. Counts/history use existing guarded referral records.
7. **Rewards/wallet:** `/my-learning/rewards` keeps currencies and simulated reward
   balances separate; `/my-learning/wallet` shows actual available, pending, earned,
   withdrawn and debt. No invented accounting. Referrals no longer duplicate balances.
8. **Withdrawals:** `/my-learning/withdrawals` provides direct access from an enabled
   wallet. Uses configured minimum/methods, amount/details/ownership confirmation and
   existing idempotent POST. Available funds/debt/configuration restrict submission.
   History retains actual pending/approved/processing/paid/rejected states/details.
9. **Support:** configured name, eligibility/threshold progress, submitted answer
   table and own private supporting documents. Existing upload lifecycle retained.
   No owner review notes/history are shown.
10. **Exchange:** selected public opportunity survives through `kind=exchange` and
    `opportunity_id` hints. Selector loads only the existing available-for-me API,
    shows institution/location/requirements and actual dates/deadline/capacity.
    No unfiltered archived/closed list or client eligibility authority.
11. **Forms:** guest 401 now offers Academy login with exact contextual return page
    and query. Definitions, responses, validation/conditional logic/pages/files and
    success remain independent. Native submission succeeded; no blanket Forms menu.
12. **Account:** profile/password and real course statistics retained. Manufactured
    lessons×10 score replaced by actual completed lesson count. Finance moved to
    focused views; profile no longer requests referral data itself.
13. **Public transitions:** marketing links retain login/enroll/resume. Programme
    and exchange links now preserve their intended kind/opportunity through Academy
    login for guests. Public and hosted Academy dashboard share the new fixed entry.
14. **Visibility:** application menu requires both server capability and configured
    programme flag. Referral/reward/wallet links derive guarded account data; forms
    require configured flags/capabilities. Withdrawal link additionally requires
    enabled account settings and capability. Historical records remain readable.
15. **Mobile:** scoped learner input/card/table/quick-action layouts, wrapping and
    responsive single-column actions; native and fixture pages had no document overflow.
16. **RTL:** native Arabic rendering checked at 1440/390px, including form submission,
    finance/programme fixtures, logical spacing/direction and existing Academy theme.
17. **Security:** scoped member RPCs and tenant/user filters retained; document tests
    deny another applicant, Forms tests deny wrong tenant/response/files and require
    enrollment. Credential tests verify server-supplied identity and guarded access.
    UI displays only submitted answers/payment information, never staff review notes.
    No frontend tenant IDs grant authority. SQL/database cross-user rehearsals were
    not rerun; native testing identity has owner access and cannot prove all student
    denial cases. Focused server tests supplement, not replace, those rehearsals.
18. **Files/routes:** new `LearnerDashboard.jsx` and tests; updated LearnerAccount,
    ELearningLearnerShell, routing in ELearningPlayer (CoursePlayer unchanged), Academy
    dashboard, certificates, programmes/exchange selector, AcademyDataBlock/FormBlock,
    learner shell CSS and English/Arabic copy. Only backend runtime change is the
    matching notification path compatibility validator; regression test added.
19. **Validation:** 203 frontend files, 1,502 passed, one existing skip; lint and
    production build/API-origin/theme/bundle/public-tenant audits pass. 70 focused
    backend notification/Form/credential/private-document tests pass. Five source
    release validators and diff whitespace checks pass. Broad backend hermetic run:
    2,817 tests, 12 failures, 12 errors, 526 skips, external attempts blocked. Failures
    include production REDIS_URL configuration, missing expected CI paths, operator
    entitlement/cookie settings and readiness; this is not a passing backend gate.
20. **Remaining gaps:** no learner-permitted workflow history endpoint (staff notes
    must stay private); no notification mark-unread API; existing event payloads often
    target broad destinations rather than exact attempts/forms; referral projection
    does not supply detailed purchase/source identities; certificate list does not
    include immutable design title; profile editing is not implemented here. These
    are documented limitations, not fabricated client features. No live payments,
    EduHope configuration, schema migration or production deployment occurred.

## Native versus fixture evidence

Native Chrome used the existing local testing identity and real API. Verified login,
dashboard → exact Continue lesson → dashboard, My Learning/certificates (empty real
list), notifications, account and disabled optional-feature states; submitted one
labeled QA response with actual PDF through the existing published Academy form.
English/Arabic at 1440px/390px: no page errors or document overflow. Programmes API
returned403 disabled; server programme flags were all false. No feature was enabled.

Only those disabled optional referral/finance/programme reads were replaced with
isolated browser GET fixtures: eligible/ineligible support, available exchange,
pending withdrawal, real-model wallet numbers, eligible referral code/history and
private-document empty state. All four language/viewport combinations passed;
opportunity preselection and owner-note exclusion were checked. No fixture POST,
financial transaction, programme application or production mutation was executed.
Screenshots/logs are `/tmp/learner-surroundings-qa` and
`/tmp/learner-surroundings-{browser,fixtures,security}.log`.

Native issued certificate download/revoked workflow, live withdrawal/applications,
cross-user browser denials and production Docker/staging/backup/upgrade gates remain
unverified locally. The full backend failure is reported, never bypassed. No PR or
deployment readiness is claimed.
