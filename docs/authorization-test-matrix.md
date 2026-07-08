# Authorization Test Matrix

This report tracks tenant/user-scoped authorization coverage for the Madar
backend. It focuses on proving that authenticated users cannot cross user,
tenant, project, submission, chart, dataset, or admin boundaries.

## Covered Route Categories

| Category | Routes | Test files | Matrix cases |
| --- | --- | --- | --- |
| User workspace auth boundary | `/users/{user_id}/info`, `/profile`, `/avatar`, data, cleaning, analysis, AI, visualization aliases | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_authorization_boundaries.py` | unauthenticated, wrong `user_id`, admin blocked from regular workspace |
| Dataset upload/read/export | `/users/{user_id}/data/upload`, `/read`, `/export` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_data_upload_privacy.py`, `backend/tests/test_large_dataset_processing.py` | owner success, wrong user blocked, tenant/user-scoped storage, no public mount |
| Cleaning/export | `/users/{user_id}/cleaning/*`, `/export` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_data_cleaning_preparation.py` | wrong user blocked, generic export failure message without private path leakage |
| Analysis and AI | `/users/{user_id}/analysis/run`, `/assist`, `/ai` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_ai_usage_routes.py`, `backend/tests/test_ai_analysis_strictness.py` | wrong user blocked, AI daily quota preserved, AI safety blocks |
| Visualization and private generated files | `/users/{user_id}/visualization/*`, `/visualization/charts/{chart_id}` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_generated_charts_privacy.py`, `backend/tests/test_private_reports_and_explorer_access.py` | wrong user, cross tenant, path traversal, missing file, owner access, HTML security headers |
| Website settings | `/website/settings`, `/users/{user_id}/website/settings` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_website_routes.py` | active tenant member required, wrong compatibility `user_id` blocked |
| Billing checkout | `/billing/checkout`, `/users/{user_id}/billing/checkout` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_billing_routes.py` | tenant membership required, wrong compatibility `user_id` blocked |
| Builder projects | `/builder/projects`, `/builder/projects/{project_id}`, `/publish`, legacy `/users/{user_id}/builder/*` aliases | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_builder_backend_hardening.py`, `backend/tests/test_builder_archived_projects.py` | auth required, wrong user alias blocked, cross-tenant project hidden, write/admin role boundaries |
| Builder form submissions | `/builder/projects/{project_id}/form-submissions*` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_builder_form_submissions.py` | auth required, cross-tenant project/submission hidden, status update audit avoids private answers |
| Admin users/profile/account-access/billing | `/admin/users*`, `/admin/profile/*`, `/admin/account-access/*`, `/admin/billing/features` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_authorization_boundaries.py`, targeted admin tests | regular user blocked, system admin allowed |
| Notifications | `/notifications`, `/notifications/{id}/read`, `/notifications/read-all`, `/notifications/push-subscriptions` | `backend/tests/test_authorization_matrix.py`, `backend/tests/test_notification_service.py` | auth required, service calls scoped to authenticated session user |

## Intentionally Public Routes

These routes are public by design and should be protected through validation,
rate limits, and response minimization rather than login requirements:

- `GET /`
- `GET /health/live`
- `GET /health/ready`
- `GET /public/sites/{subdomain}`
- `POST /public/sites/{subdomain}/forms/{form_id}/submissions`
- `POST /public/sites/{subdomain}/events`
- `POST /public/contact`
- `GET /notifications/push-public-key`
- `POST /billing/webhook` with `X-Madar-Webhook-Secret`
- `GET /uploads/tenant_{tenant_id}/builder_assets/{filename}` for validated public builder images only

## Security Assertions

The matrix asserts:

- 401 for unauthenticated protected access where the route auth helper is invoked.
- 403 for wrong user, wrong tenant scope, inactive/no membership, regular user on admin route, or admin on regular-user workspace route.
- 404 for tenant-hidden project/submission resources where revealing existence would leak cross-tenant data.
- No private storage roots or absolute Windows paths appear in tested error responses.
- Private generated chart and explorer HTML routes do not rely on random filenames for access control.

## Known Limitations And Follow-Up

- The matrix uses route-level fakes for Supabase and service calls, so it proves backend authorization wiring and scoped parameters without calling external services. It does not replace end-to-end browser/session tests.
- Admin avatar/profile storage side effects are mocked; deeper storage rollback tests can be added separately.
- The inactive archive file `backend/data_analysis/visualization/archive/visualization_backup.py` was removed during the dead-code cleanup because it contained historical `generated_charts` behavior and was not imported by active routes.
- Public route abuse controls are covered by separate rate-limit and payload-limit tests, not this authorization matrix.
