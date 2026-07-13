import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from classes import BillingCheckoutRequest
from routes import billing_routes, builder_routes
from services import admin_user_service, billing_service
from services.tenant_service import TenantContext


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


class _EntitlementQuery:
    def __init__(self, data):
        self.data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return _Result(self.data)


class _EntitlementSupabase:
    def __init__(self, features):
        self.features = features
        self.table_calls = []

    def table(self, name):
        self.table_calls.append(name)
        return _EntitlementQuery(self.features)


class PublishEntitlementTests(unittest.TestCase):
    def test_current_full_platform_plan_identifiers_are_accepted(self):
        for plan in ("cms", "forms_data", "cms_plus", "complete"):
            request = BillingCheckoutRequest(
                subscription_type="full_platform",
                plan=plan,
                builder_type=None,
            )
            normalized = billing_service.validate_billing_plan(
                subscription_type=request.subscription_type,
                plan=request.plan,
                builder_type=request.builder_type,
            )
            self.assertEqual(normalized["plan"], plan)

    def test_rollout_defaults_to_beta_compatibility_without_database_lookup(self):
        fake = _EntitlementSupabase([])
        with patch.dict("os.environ", {}, clear=False), \
             patch.dict("os.environ", {"ENFORCE_PUBLISH_ENTITLEMENT": "false"}), \
             patch.object(billing_service, "service_supabase", fake):
            result = billing_service.require_publish_entitlement(7)

        self.assertFalse(result["enforced"])
        self.assertEqual(fake.table_calls, [])

    def test_active_website_feature_allows_publish_when_enforced(self):
        fake = _EntitlementSupabase([
            {
                "id": 12,
                "subscription_type": "individual_builder",
                "builder_type": "website",
                "payment_status": "active",
            }
        ])
        with patch.dict("os.environ", {"ENFORCE_PUBLISH_ENTITLEMENT": "true", "PUBLISH_BETA_TENANT_IDS": ""}), \
             patch.object(billing_service, "service_supabase", fake):
            result = billing_service.require_publish_entitlement(7)

        self.assertTrue(result["active"])
        self.assertEqual(result["feature_id"], 12)

    def test_pending_feature_returns_stable_entitlement_code(self):
        fake = _EntitlementSupabase([
            {
                "subscription_type": "full_platform",
                "builder_type": None,
                "payment_status": "pending",
            }
        ])
        with patch.dict("os.environ", {"ENFORCE_PUBLISH_ENTITLEMENT": "true", "PUBLISH_BETA_TENANT_IDS": ""}), \
             patch.object(billing_service, "service_supabase", fake):
            with self.assertRaises(HTTPException) as raised:
                billing_service.require_publish_entitlement(7)

        self.assertEqual(raised.exception.status_code, 402)
        self.assertEqual(raised.exception.detail["code"], "entitlement_pending")

    def test_past_due_canceled_expired_and_missing_features_are_inactive(self):
        for features in (
            [{"subscription_type": "full_platform", "payment_status": "past_due"}],
            [{"subscription_type": "full_platform", "payment_status": "canceled"}],
            [{"subscription_type": "full_platform", "payment_status": "expired"}],
            [],
        ):
            with self.subTest(features=features), patch.dict(
                "os.environ",
                {"ENFORCE_PUBLISH_ENTITLEMENT": "true", "PUBLISH_BETA_TENANT_IDS": ""},
            ), patch.object(
                billing_service,
                "service_supabase",
                _EntitlementSupabase(features),
            ):
                with self.assertRaises(HTTPException) as raised:
                    billing_service.require_publish_entitlement(7)
                self.assertEqual(raised.exception.status_code, 402)
                self.assertEqual(raised.exception.detail["code"], "entitlement_inactive")
                expected_state = (
                    features[0]["payment_status"] if features else "missing"
                )
                self.assertEqual(
                    raised.exception.detail["context"]["billing_states"],
                    [expected_state],
                )


class _RpcCall:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return _Result(self.data)


class _BillingRpcSupabase:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return _RpcCall(self.result)


class BillingWebhookIdempotencyTests(unittest.TestCase):
    occurred_at = "2026-07-12T12:00:00+00:00"

    def test_shared_secret_webhook_is_disabled_in_production_by_default(self):
        app = FastAPI()
        app.include_router(billing_routes.router)
        client = TestClient(app)
        with patch.dict(
            "os.environ",
            {
                "APP_ENV": "production",
                "BILLING_WEBHOOK_SECRET": "configured-secret",
                "BILLING_WEBHOOK_ALLOW_SHARED_SECRET": "false",
            },
        ), patch.object(billing_routes, "apply_billing_webhook_event") as apply_event:
            response = client.post(
                "/billing/webhook",
                headers={"x-madar-webhook-secret": "configured-secret"},
                json={
                    "tenant_id": 7,
                    "subscription_type": "full_platform",
                    "plan": "pro",
                    "builder_type": None,
                    "payment_status": "active",
                    "provider_event_id": "event-1",
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "billing_not_configured")
        apply_event.assert_not_called()

    def test_same_event_and_payload_returns_existing_feature(self):
        event = {"id": "event-1", "payload_hash": "ignored", "status": "processed"}
        expected_hash = billing_service._billing_event_payload_hash(
            tenant_id=7,
            subscription_type="full_platform",
            plan="pro",
            builder_type=None,
            payment_status="active",
            provider_occurred_at=self.occurred_at,
        )
        event["payload_hash"] = expected_hash
        with patch.object(billing_service, "get_billing_webhook_event", return_value=event), \
             patch.object(billing_service, "get_existing_feature_for_tenant", return_value={"id": 4}) as get_feature:
            result = billing_service.apply_billing_webhook_event(
                tenant_id=7,
                subscription_type="full_platform",
                plan="pro",
                builder_type=None,
                payment_status="active",
                provider_event_id="provider-1",
                provider_occurred_at=self.occurred_at,
            )

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["feature"], {"id": 4})
        get_feature.assert_called_once()

    def test_event_hash_is_stable_when_server_assigns_receipt_time(self):
        first = billing_service._billing_event_payload_hash(
            tenant_id=7,
            subscription_type="full_platform",
            plan="pro",
            builder_type=None,
            payment_status="active",
            provider_occurred_at="2026-07-12T12:00:00+00:00",
        )
        retry = billing_service._billing_event_payload_hash(
            tenant_id=7,
            subscription_type="full_platform",
            plan="pro",
            builder_type=None,
            payment_status="active",
            provider_occurred_at="2026-07-12T12:00:05+00:00",
        )

        self.assertEqual(first, retry)

    def test_reused_event_id_with_different_payload_is_rejected(self):
        with patch.object(
            billing_service,
            "get_billing_webhook_event",
            return_value={"id": "event-1", "payload_hash": "0" * 64},
        ):
            with self.assertRaises(HTTPException) as raised:
                billing_service.apply_billing_webhook_event(
                    tenant_id=7,
                    subscription_type="full_platform",
                    plan="pro",
                    builder_type=None,
                    payment_status="active",
                    provider_event_id="provider-1",
                    provider_occurred_at=self.occurred_at,
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "idempotency_conflict")

    def test_first_event_uses_transactional_rpc(self):
        fake = _BillingRpcSupabase({
            "duplicate": False,
            "event_id": "event-1",
            "feature": {"id": 4, "payment_status": "active"},
        })
        with patch.object(billing_service, "get_billing_webhook_event", return_value=None), \
             patch.object(billing_service, "service_supabase", fake):
            result = billing_service.apply_billing_webhook_event(
                tenant_id=7,
                subscription_type="full_platform",
                plan="pro",
                builder_type=None,
                payment_status="active",
                provider_event_id="provider-1",
                provider_occurred_at=self.occurred_at,
            )

        self.assertFalse(result["duplicate"])
        self.assertEqual(result["feature"]["payment_status"], "active")
        self.assertEqual(fake.calls[0][0], "apply_billing_webhook_event")
        self.assertEqual(
            fake.calls[0][1]["p_provider_occurred_at"],
            self.occurred_at,
        )

    def test_stale_event_result_is_reported_without_reactivation(self):
        fake = _BillingRpcSupabase(
            {
                "duplicate": False,
                "ignored": True,
                "status": "ignored",
                "event_id": "event-stale",
                "feature": {"id": 4, "payment_status": "canceled"},
            }
        )
        with patch.object(billing_service, "get_billing_webhook_event", return_value=None), patch.object(
            billing_service, "service_supabase", fake
        ):
            result = billing_service.apply_billing_webhook_event(
                tenant_id=7,
                subscription_type="full_platform",
                plan="pro",
                builder_type=None,
                payment_status="active",
                provider_event_id="provider-stale",
                provider_occurred_at="2026-07-01T00:00:00+00:00",
            )

        self.assertTrue(result["ignored"])
        self.assertEqual(result["event_status"], "ignored")
        self.assertEqual(result["feature"]["payment_status"], "canceled")


def _builder_context():
    return TenantContext(
        tenant_id=7,
        user_id=3,
        auth_id="auth-3",
        role="owner",
        membership_status="active",
        user={},
        membership={"role": "owner"},
    )


def _builder_client():
    app = FastAPI()
    app.include_router(builder_routes.router)
    return TestClient(app)


class _BuilderRpcSupabase:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return _RpcCall(self.row)


class _ProjectMutationQuery:
    def __init__(self, row):
        self.row = dict(row)
        self.payload = None
        self.filters = []

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if all(self.row.get(column) == value for column, value in self.filters):
            self.row.update(self.payload or {})
            return _Result([dict(self.row)])
        return _Result([])


class _ProjectMutationSupabase:
    def __init__(self, row):
        self.query = _ProjectMutationQuery(row)

    def table(self, name):
        if name != "builder_projects":
            raise AssertionError(name)
        return self.query


class BuilderRevisionSafetyTests(unittest.TestCase):
    def test_publish_validation_rejects_unsafe_and_inconsistent_blocks(self):
        unsafe_schema = {
            "pages": [
                {
                    "id": "home",
                    "sections": [
                        {"elements": [{"id": "raw-1", "type": "rawHtml"}]}
                    ],
                }
            ]
        }
        with self.assertRaises(HTTPException) as unsafe:
            builder_routes.validate_publish_schema(unsafe_schema)
        self.assertEqual(unsafe.exception.detail["code"], "publish_validation_failed")

        disconnected_form = {
            "pages": [
                {
                    "id": "home",
                    "sections": [
                        {
                            "elements": [
                                {
                                    "id": "form-block-1",
                                    "type": "formBlock",
                                    "connectedFormId": "missing-form",
                                }
                            ]
                        }
                    ],
                }
            ],
            "forms": [],
        }
        with self.assertRaises(HTTPException) as disconnected:
            builder_routes.validate_publish_schema(disconnected_form)
        self.assertEqual(
            disconnected.exception.detail["code"],
            "publish_validation_failed",
        )

    def test_publish_validation_accepts_nested_action_type_as_configuration(self):
        schema = {
            "pages": [
                {
                    "id": "home",
                    "slug": "/",
                    "sections": [
                        {
                            "rows": [
                                {
                                    "columns": [
                                        {
                                            "elements": [
                                                {
                                                    "id": "button-1",
                                                    "type": "button",
                                                    "action": {
                                                        "type": "goToPage",
                                                        "pageId": "home",
                                                    },
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                }
            ],
            "forms": [],
        }

        validated, version = builder_routes.validate_publish_schema(schema)

        self.assertIs(validated, schema)
        self.assertEqual(version, 1)

    def test_draft_update_increments_revision_with_expected_filter(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"pages": []},
            "draft_revision": 4,
        }
        fake = _ProjectMutationSupabase(project)
        client = _builder_client()
        with patch.object(builder_routes, "service_supabase", fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project):
            response = client.put(
                "/builder/projects/project-1",
                json={"draft_schema": {"pages": [{"id": "home"}]}, "expected_revision": 4},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"]["draft_revision"], 5)
        self.assertIn(("draft_revision", 4), fake.query.filters)

    def test_stale_publish_revision_returns_structured_conflict(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"pages": []},
            "draft_revision": 4,
        }
        client = _builder_client()
        with patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project), \
             patch.object(builder_routes, "require_publish_entitlement"), \
             patch.object(builder_routes, "require_public_subdomain", return_value={"subdomain": "site", "tenant_id": 7}):
            response = client.post(
                "/builder/projects/project-1/publish",
                json={"expected_revision": 3},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "project_revision_conflict")
        self.assertEqual(response.json()["detail"]["context"]["current_revision"], 4)

    def test_publish_uses_atomic_rpc_and_returns_revision(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"schema_version": 1, "pages": []},
            "draft_revision": 4,
            "published_version": 2,
            "schema_version": 1,
        }
        published = {
            **project,
            "status": "published",
            "published_revision": 4,
            "published_version": 3,
            "published_schema": project["draft_schema"],
        }
        fake = _BuilderRpcSupabase(published)
        client = _builder_client()
        with patch.object(builder_routes, "service_supabase", fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project), \
             patch.object(builder_routes, "require_publish_entitlement"), \
             patch.object(builder_routes, "require_public_subdomain", return_value={"subdomain": "site", "tenant_id": 7}), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.post(
                "/builder/projects/project-1/publish",
                json={"expected_revision": 4},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"]["published_revision"], 4)
        self.assertEqual(fake.calls[0][0], "publish_builder_project_atomic")
        self.assertEqual(fake.calls[0][1]["p_expected_revision"], 4)
        self.assertIn("p_require_active_entitlement", fake.calls[0][1])

    def test_revision_is_required_once_project_supports_concurrency(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"pages": []},
            "draft_revision": 4,
        }
        client = _builder_client()
        with patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), patch.object(
            builder_routes, "get_project_for_tenant", return_value=project
        ):
            response = client.put(
                "/builder/projects/project-1",
                json={"name": "Unsafe stale save"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "project_revision_required")

    def test_publish_rejects_unsupported_schema_version_before_rpc(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"schema_version": 99, "pages": []},
            "draft_revision": 0,
        }
        fake = _BuilderRpcSupabase({})
        client = _builder_client()
        with patch.object(builder_routes, "service_supabase", fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project), \
             patch.object(builder_routes, "require_publish_entitlement"), \
             patch.object(builder_routes, "require_public_subdomain", return_value={"subdomain": "site", "tenant_id": 7}):
            response = client.post("/builder/projects/project-1/publish", json={"expected_revision": 0})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "publish_validation_failed")
        self.assertEqual(fake.calls, [])

    def test_unpublish_preserves_last_published_snapshot(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "published",
            "draft_schema": {"pages": [{"id": "draft"}]},
            "published_schema": {"pages": [{"id": "live"}]},
            "draft_revision": 5,
            "published_revision": 4,
            "published_version": 2,
        }
        fake = _ProjectMutationSupabase(project)
        client = _builder_client()
        with patch.object(builder_routes, "service_supabase", fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.post(
                "/builder/projects/project-1/unpublish",
                json={"expected_revision": 5},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"]["status"], "draft")
        self.assertEqual(response.json()["project"]["published_schema"], {"pages": [{"id": "live"}]})
        self.assertEqual(response.json()["project"]["published_version"], 2)


class _AdminQuery:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args):
        return self

    def neq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return _Result(self.data, self.count)


class _AdminSupabase:
    def __init__(self, target, admin_count=1, rpc_result=None):
        self.target = target
        self.admin_count = admin_count
        self.rpc_result = rpc_result or target
        self.table_calls = 0
        self.rpc_calls = []

    def table(self, name):
        if name != "users":
            raise AssertionError(name)
        self.table_calls += 1
        if self.table_calls == 1:
            return _AdminQuery([self.target])
        return _AdminQuery([], self.admin_count)

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return _RpcCall(self.rpc_result)


class AdminLifecycleSafetyTests(unittest.TestCase):
    def test_unverified_user_cannot_be_promoted(self):
        target = {
            "id": 4,
            "auth_id": "auth-4",
            "email_verified": False,
            "user_type": "user",
        }
        fake = _AdminSupabase(target)
        with patch.object(admin_user_service, "service_supabase", fake):
            with self.assertRaises(HTTPException) as raised:
                admin_user_service.update_user_type(user_id=4, user_type="admin")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "email_verification_required")
        self.assertEqual(fake.rpc_calls, [])

    def test_promotion_uses_rpc_that_requires_mfa(self):
        target = {
            "id": 4,
            "auth_id": "auth-4",
            "email_verified": True,
            "user_type": "user",
        }
        promoted = {**target, "user_type": "admin"}
        fake = _AdminSupabase(target, rpc_result=promoted)
        with patch.object(admin_user_service, "service_supabase", fake):
            result = admin_user_service.update_user_type(user_id=4, user_type="admin")

        self.assertEqual(result["user_type"], "admin")
        self.assertEqual(result["old_user_type"], "user")
        self.assertEqual(fake.rpc_calls[0][0], "admin_update_user_type_safely")

    def test_last_admin_cannot_be_demoted(self):
        target = {
            "id": 4,
            "auth_id": "auth-4",
            "email_verified": True,
            "account_status": "active",
            "user_type": "admin",
        }
        fake = _AdminSupabase(target, admin_count=0)
        with patch.object(admin_user_service, "service_supabase", fake):
            with self.assertRaises(HTTPException) as raised:
                admin_user_service.update_user_type(user_id=4, user_type="user")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "last_system_admin_required")

    def test_disabled_admin_is_not_treated_as_last_active_admin(self):
        target = {
            "id": 4,
            "auth_id": "auth-4",
            "email_verified": True,
            "account_status": "disabled",
            "user_type": "admin",
        }
        fake = _AdminSupabase(
            target,
            admin_count=0,
            rpc_result={**target, "user_type": "user"},
        )
        with patch.object(admin_user_service, "service_supabase", fake):
            result = admin_user_service.update_user_type(user_id=4, user_type="user")

        self.assertEqual(result["user_type"], "user")

    def test_last_active_admin_cannot_be_deleted(self):
        target = {
            "id": 4,
            "auth_id": "auth-4",
            "tenant_id": None,
            "email_verified": True,
            "account_status": "active",
            "user_type": "admin",
        }
        fake = _AdminSupabase(target, admin_count=0)

        with patch.object(admin_user_service, "service_supabase", fake):
            with self.assertRaises(HTTPException) as raised:
                admin_user_service.delete_user_account(
                    user_id=4,
                    requesting_user_id=1,
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"],
            "last_system_admin_required",
        )
        self.assertEqual(fake.rpc_calls, [])


if __name__ == "__main__":
    unittest.main()
