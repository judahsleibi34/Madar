# Privileged-client inventory closure

Source baseline: `86b022f208579341b2a9171255df4df14a9e4348`.
Review date: 2026-10-18. This is a source review of eleven omitted direct-client
paths, not certification of deployed roles, every historical inventory entry,
or platform-wide authorization.

The unchanged `web/scripts/check_privileged_inventory.py` initially failed with
exactly eleven unclassified paths and zero stale paths. The manifest contained
67 entries; the reviewed additions bring its exact direct-reference scope to
78 application files. No checker exclusions/client-name rules were changed.
The original classifications and historical provenance remain in the manifest.

## Authority model and shared authentication evidence

`web/backend/database.py:create_supabase_client` constructs `service_supabase`
with `SUPABASE_SERVICE_KEY`, separately from the anonymous client. This is a
privileged provider credential, not an end-user JWT or a tenant-isolated client.
The native provider bootstrap explicitly creates `service_role ... bypassrls`
(`web/staging/integration/manage.py`); lifecycle rehearsals exercise that role
with BYPASSRLS (`web/scripts/rehearse_migration_147.sh`). This review did not query
live production role flags and does not infer them from an SDK variable name.
Direct queries therefore require explicit tenant/ownership checks; SECURITY
DEFINER RPCs require independent input/state/grant review even if RLS is enabled.

The shared HTTP boundary is concrete:

- `routes/elearning_player_routes.py:member` calls
  `services/tenant_service.py:require_active_tenant_member` with
  `allow_admin_account_access=False, allow_learner=True`.
- `tenant_service.get_current_tenant_context` obtains the authenticated platform
  user, derives tenant/user/auth IDs from that server-owned row, queries active
  membership with **all three IDs**, rejects disallowed learner access, and checks
  tenant lifecycle. Hosted learner requests also verify the website/session
  tenant match. Request query/body tenant IDs are not the actor authority.
- `routes/elearning_assessments_routes.py:owner` calls
  `elearning_access_service.require_elearning_access(..., 'elearning.structure.manage')`;
  the latter obtains current active membership and requires role owner/admin.
- SQL `commerce_assert_member` in migration129 joins membership and users,
  requires active membership/account, and, when requested, owner/admin role.
  `academy_assert_enabled` as replaced in139 additionally checks programme state.
  These SQL guards accept IDs from a trusted service caller; they do not bind a
  browser JWT themselves. Their role-limited EXECUTE grants remain important.

## The eleven paths

### 1. `routes/academy_owner_routes.py`

`contacts`/`contact_read` require `owner`, Contact capability and schema upgrade;
their direct SELECT/UPDATE filters include `actor.tenant_id`, with contact ID on
updates. Document routes use `member` and then application-specific access checks.
`reconcile` also uses `member` before the payment service's buyer/owner check.

The deliberately anonymous `contact` POST is a separate boundary: it rate-limits,
resolves website/tenant server-side, checks academy settings and Contact
capability, and requires the bound academy project to be published and contain
`academyContact`. Its insertion supplies that resolved tenant/project. `Contact`
inherits an extra-fields-forbidden payload, so browser tenant/project fields
cannot override those values. This is intentional public contact intake, not
an omitted login check.

### 2. `routes/academy_programme_routes.py`

Capabilities, own account/applications and withdrawals use `member`; management,
finance, reports, CEFR and member-profile views use `owner`. The CEFR direct read
includes tenant+course. `member_profile` filters its supplementary application
read by actor tenant and target user. Finance/member-profile RPCs supply
actor-derived tenant/admin IDs; migration138's `academy_owner_finance`,
`academy_owner_member_profile` and `academy_owner_report` call
`commerce_assert_member(..., true)` and constrain tenant-owned rows. Target-user
membership is checked by the member-profile RPC before projecting user data.
Entity/kind route parameters are Literal allowlists, not arbitrary table names.

### 3. `routes/billing_routes.py`

`billing_catalog` is intentionally public and selects an explicit price-book
projection using the catalog's server-selected ID, with `limit(1)`; it does not
list tenant subscriptions or return credentials. The remaining commercial reads,
quote, plan/add-on requests and checkout paths derive an active staff context
through `_commercial_context`/`require_active_tenant_member`. The legacy path's
user ID is checked by `assert_context_user`. The direct quote RPC receives that
context tenant and checks the145 protection contract before use.

Plan/add-on/legacy checkout endpoints save manual-review requests; this inventory
does not grant payment or activation authority. `billing_webhook` is a distinct
test boundary: it refuses `APP_ENV=prod/production`, refuses a missing configured
secret and uses `secrets.compare_digest`. It must not be described as a configured
signed live-provider webhook. Billing service event handling remains a separate
integrity boundary.

### 4. `routes/elearning_forms_routes.py`

Owner management routes obtain `owner` before privileged service operations.
Applicant history/detail uses a current member including learners. Public
`context` resolves the academy tenant, checks publishing entitlement/settings,
and reads only a published bound project containing the requested form ID. An
authenticated actor from another tenant is not reused. `definition` is followed
by `public_access`, which requires an active form and enforces its access policy.
Published questions may intentionally be viewed anonymously; submission still
requires the configured login/enrollment/programme eligibility. Public reads and
submissions are rate-limited; file and request sizes are bounded.

### 5. `services/academy_exchange_service.py`

`opportunity` scopes tenant+opportunity; `detail` additionally scopes personal
responses by user, and decision/history reads by tenant+response.
`gate` checks schema, Exchange availability and Forms entitlement.
`exchange_opportunity_available`/`assert_exchange_submission` in142 validate
member, configured opportunity/form, publication, deadline, capacity and learner
eligibility. `review_exchange_response` rechecks owner/admin, tenant response,
revision and capacity under locks. Routes `exchange_detail`/`exchange_submit`
supply current members; `exchange_review` supplies owners. The service is not an
independently authenticated HTTP interface.

### 6. `services/academy_owner_service.py`

`application_access` scopes tenant+tuition application. Reads allow the applicant
or tenant owner/admin; writes require the applicant and submitted/under-review
state. `document_row` adds application+document IDs and `removed_at IS NULL`.
Uploads use generated tenant/application keys, content validation and storage
quotas. `require_private_storage` requires bucket `public` to be exactly false;
downloads verify SHA256 before returning bytes. SQL `manage_academy_document`
in140 independently checks member, tenant application, applicant and review state.
Owner opportunity/dashboard/student RPCs use actor IDs and SQL owner assertions.
Management-list authorization resides in its owner route, not in an implicit
service-role/RLS restriction.

### 7. `services/academy_programme_service.py`

`read_access`/`available` enforce schema/capability/programme availability.
`records` always filters tenant; self-service additionally filters user, while
`admin=True` requires owner/admin. Its table argument comes from fixed internal
calls or a Literal-constrained route selection. `review`, `report` and
`configure_cefr` also check owner/admin. Wallet/application/withdrawal RPCs receive
actor-derived tenant/user; review/report RPCs receive actor-derived admin.
The latest academy review wrapper in144 delegates to guarded Forms review or
the private retained core, rather than exposing an unrestricted table mutation.

### 8. `services/elearning_forms_service.py`

Definitions/versions, responses, files, decision history and reviewer-name queries
are explicitly tenant scoped; response/file lookups include their resource IDs.
Owner routes provide the management permission. Applicant reads filter user and
use144's `get_elearning_form_applicant_response`, which rechecks membership and
returns an applicant projection without owner notes/reviewer identity/history.
Owner mutations use `manage_elearning_form`/response-management/review RPCs with
SQL actor guards;144 review also forbids self-approval.

Public `submit` enforces `public_access`, same-tenant actors, canonical answers,
generated response/file identities and private storage. Migration142's
`submit_elearning_form` scopes and locks the form/opportunity, rechecks membership,
form publication/version/access/enrollment, validates replay identity, and writes
response/file metadata atomically. Migration144 adds domain-workflow eligibility
and review triggers. `definition` and generic `rpc` are privileged internal
helpers; neither authenticates an arbitrary caller on its own.

### 9. `services/elearning_recording_service.py`

Upload/download routes in `elearning_assessments_routes` obtain `member`.
`get_elearning_recording_admission` and `register_elearning_recording` in143 bind
tenant+user+attempt+question, recheck enrollment/placement and control the generated
storage key. `get_elearning_recording` permits the owning learner with access or
an authorized reviewer of referenced submitted/pending-review evidence. The
dedicated bucket must be private; uploads validate bounded canonical PCM WAV and
do not upsert; downloads check size/hash. Registration acknowledgement uncertainty
is checked before cleanup so referenced evidence is retained.

`cleanup` is intentionally cross-tenant **operator** authority. Its discovered
caller is `backend/scripts/cleanup_elearning_recordings.py`, with bounded limit
and explicit `--apply`; no HTTP cleanup route was found. SQL cleanup selects old
unreferenced recordings, shares the registration advisory lock, rechecks protected
references, and restricts EXECUTE to service_role. This is not authority granted
to every authenticated learner.

### 10. `services/learning_payment_provider.py`

Checkout routes obtain members and `create_commerce_learning_checkout` in129
rechecks membership and uses tenant-owned offering/product price snapshots.
`reconcile_checkout` reads tenant+checkout, requires the buyer or owner/admin,
looks up its recorded provider and rejects provider truth for another
tenant/checkout. The webhook caller in `elearning_commerce_routes` obtains the
configured code-registered adapter, limits raw body size and calls
`verify_webhook` before `apply_verified_event`. Stripe and development-only dummy
adapters are separate configured implementations, not request-imported code.

`apply_verified_event` itself is a privileged internal sink. SQL129 validates the
tenant+checkout+provider, price/currency, event/transaction identity and ordering,
then commits entitlement/order effects atomically. SQL cannot authenticate an
external provider signature: that remains the adapter's responsibility. Browser
redirect parameters never establish successful payment authority.

### 11. `workers/data_deletion_worker.py`

This is a cross-tenant process, not an end-user route. `main` invokes provider
recovery startup authority and checks enabled configuration; valid READ_ONLY
standbys expose non-consuming health without calling the prohibited protocol RPC.
Enabled startup and each consuming poll require exact integer protocol2.
`run_batch` rechecks consumption authority before claiming. Deletion service RPCs
carry the original request owner/generation/attempt and step attempt;150 enforces
leases and ACLs. Request enrollment is separately authenticated in
`data_deletion_routes` and authorized by150's creation RPC.

Health/metrics expose aggregate queue/worker state on the configured internal
interface, not a user-selected tenant listing. Broad service-role business-table
authority remains outside the narrower lifecycle-table ACL repair: complete
legacy/manual actor exclusion and future scoped deletion credentials remain
necessary. The protocol marker alone is not evidence of ownership correctness.

## Results and limitations

| Check | Result |
| --- | --- |
| Original unchanged completeness checker | FAIL:11 omissions,0 stale |
| Checker after reviewed inventory additions | PASS:78 application files |
| New stdlib adversarial checker suite | PASS:8 tests,0 skips |
| New path/function/caller evidence references | PASS:all11 resolve in current AST/source |
| Checker algorithm/client names/exclusions changed | No |
| Live database role/grant inspection in this review | NOT TESTED |
| New native tenant/HTTP tests executed by this review | NOT TESTED |
| Production or staging mutation by this review | None |

Executed commands:

```text
python3 web/scripts/check_privileged_inventory.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s web/backend/tests -p 'test_privileged_inventory_check.py' -v
git diff --check
```

The eight tests exercise missing routes, every supported client name/import alias
and attribute, workers, stale paths, duplicate entries, missing/empty boundaries,
scope exclusions, and AST-only inspection without executing application code.
The real checkout checker must also run outside the hermetic test container,
whose existing mounts do not include the full manifest. No inventory entry makes
an unreviewed future caller safe automatically.

Existing targeted suites for future reruns include `test_academy_owner_tools`,
`test_academy_programme_service`, `test_elearning_forms`, `test_elearning_recording_validation`,
`test_learning_payment_provider`, `test_data_deletion_worker`, and the corresponding
marked native academy/Forms/recording tests. Their presence is not a claim that
this source review reran them or established complete tenant isolation.

No confirmed authorization bypass was found in the eleven reviewed paths.
A separate integrity concern remains under investigation: private-document and
Forms upload exception paths clean staged bytes without the recording service's
equivalent commit-unknown reconciliation. A persisted-metadata/lost-response
reproduction is required before calling that a confirmed data-loss defect.
No application repair, migration change or operational approval is included in
this inventory closure.
