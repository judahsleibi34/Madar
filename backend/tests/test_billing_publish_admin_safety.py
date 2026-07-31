import copy
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request
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

    def test_publish_uses_server_authoritative_entitlements(self):
        expected = {"plan_id": "website", "capabilities": ["website_publish"]}
        with patch(
            "services.entitlement_service.require_any_entitlement",
            return_value=expected,
        ) as require:
            result = billing_service.require_publish_entitlement(7)

        self.assertEqual(result, expected)
        require.assert_called_once_with(
            7,
            {"website_publish", "public_form_links"},
            message="An active website or public-form publishing entitlement is required.",
        )

    def test_publish_denial_is_not_disabled_by_legacy_environment_flags(self):
        denial = HTTPException(status_code=402, detail={"code": "entitlement_required"})
        with patch.dict("os.environ", {"ENFORCE_PUBLISH_ENTITLEMENT": "false"}), patch(
            "services.entitlement_service.require_any_entitlement",
            side_effect=denial,
        ):
            with self.assertRaises(HTTPException) as raised:
                billing_service.require_publish_entitlement(7)

        self.assertIs(raised.exception, denial)


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
    @staticmethod
    def _contract_request(value=None):
        headers = []
        if value is not None:
            headers.append((b"x-madar-builder-contract", value.encode("ascii")))
        return Request({
            "type": "http",
            "method": "PUT",
            "path": "/builder/projects/project-1",
            "headers": headers,
        })

    def test_current_builder_client_contract_is_accepted(self):
        supplied = builder_routes.require_supported_builder_client(
            self._contract_request(builder_routes.BUILDER_CLIENT_CONTRACT)
        )
        self.assertEqual(supplied, builder_routes.BUILDER_CLIENT_CONTRACT)

    def test_obsolete_builder_client_is_rejected_before_mutation(self):
        with self.assertRaises(HTTPException) as raised:
            builder_routes.require_supported_builder_client(
                self._contract_request("browser-first-v4")
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"],
            "builder_client_upgrade_required",
        )

        client = _builder_client()
        with patch.object(builder_routes, "require_builder_context") as require_context:
            response = client.put(
                "/builder/projects/project-1",
                headers={"X-Madar-Builder-Contract": "browser-first-v4"},
                json={"draft_schema": {"pages": [{"id": "home"}]}, "expected_revision": 1},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"],
            "builder_client_upgrade_required",
        )
        require_context.assert_not_called()

    def test_missing_contract_has_staged_rollout_then_enforcement(self):
        with patch.dict(
            "os.environ",
            {"ENFORCE_BUILDER_CLIENT_CONTRACT": "false"},
        ):
            self.assertEqual(
                builder_routes.require_supported_builder_client(
                    self._contract_request()
                ),
                "",
            )
        with patch.dict(
            "os.environ",
            {"ENFORCE_BUILDER_CLIENT_CONTRACT": "true"},
        ):
            with self.assertRaises(HTTPException) as raised:
                builder_routes.require_supported_builder_client(
                    self._contract_request()
                )
        self.assertEqual(
            raised.exception.detail["code"],
            "builder_client_upgrade_required",
        )

    def test_publish_routing_prefers_home_over_editor_selection_and_form_pages(self):
        schema = {
            "activePageId": "form-page",
            "pages": [
                {
                    "id": "form-page",
                    "name": "Form",
                    "slug": "/form",
                    "sections": [{"freeElements": [{
                        "id": "form-block",
                        "type": "formBlock",
                        "connectedFormId": "form-1",
                    }]}],
                },
                {"id": "home", "name": "Home", "sections": [{"freeElements": [{"id": "hero", "type": "heading"}]}]},
                {"id": "about", "name": "About", "slug": "/about", "showInNavigation": False, "sections": []},
            ],
            "forms": [{"id": "form-1"}],
        }

        validated, _ = builder_routes.validate_publish_schema(schema)

        self.assertEqual(validated["defaultPageId"], "home")
        self.assertEqual([page["id"] for page in validated["pages"]], ["form-page", "home", "about"])
        self.assertEqual([page["slug"] for page in validated["pages"]], ["/form", "/", "/about"])
        self.assertEqual([page["isDefault"] for page in validated["pages"]], [False, True, False])
        self.assertFalse(validated["pages"][2]["showInNavigation"])

    def test_publish_routing_rejects_duplicate_invalid_and_reserved_slugs(self):
        with self.assertRaises(HTTPException) as duplicate:
            builder_routes.validate_publish_schema({
                "pages": [
                    {"id": "home", "name": "Home", "slug": "/"},
                    {"id": "one", "name": "One", "slug": "/about"},
                    {"id": "two", "name": "Two", "slug": "/about"},
                ],
                "forms": [],
            })
        self.assertEqual(duplicate.exception.detail["context"]["issue_type"], "duplicate_page_slug")

        with self.assertRaises(HTTPException) as invalid:
            builder_routes.validate_publish_schema({
                "pages": [
                    {"id": "home", "name": "Home", "slug": "/"},
                    {"id": "bad", "name": "Bad", "slug": "/../bad"},
                ],
                "forms": [],
            })
        self.assertEqual(invalid.exception.detail["context"]["issue_type"], "invalid_page_slug")

        with self.assertRaises(HTTPException) as reserved:
            builder_routes.validate_publish_schema({
                "pages": [
                    {"id": "home", "name": "Home", "slug": "/"},
                    {"id": "login", "name": "Login", "slug": "/login"},
                ],
                "forms": [],
            })
        self.assertEqual(reserved.exception.detail["context"]["issue_type"], "reserved_page_slug")

    def test_publish_validation_rejects_global_duplicate_block_ids_with_safe_context(self):
        schema = {
            "pages": [
                {
                    "id": "home",
                    "name": "Home",
                    "slug": "/",
                    "sections": [{"freeElements": [
                        {"id": "duplicate", "type": "text", "content": "Private content is omitted"},
                    ]}],
                },
                {
                    "id": "page-2",
                    "name": "Page 2",
                    "slug": "/page-2",
                    "sections": [{"rows": [{"columns": [{"elements": [
                        {"id": "duplicate", "type": "formBlock", "connectedFormId": "form-1"},
                    ]}]}]}],
                },
            ],
            "forms": [{"id": "form-1"}],
        }
        before = copy.deepcopy(schema)

        with self.assertRaises(HTTPException) as duplicate:
            builder_routes.validate_publish_schema(schema)

        context = duplicate.exception.detail["context"]
        self.assertEqual(context["issue_type"], "duplicate_block_id")
        self.assertEqual(context["duplicate_id"], "duplicate")
        self.assertEqual(
            context["occurrences"],
            [
                {
                    "page_id": "home",
                    "page_name": "Home",
                    "block_id": "duplicate",
                    "block_type": "text",
                    "occurrence_index": 0,
                },
                {
                    "page_id": "page-2",
                    "page_name": "Page 2",
                    "block_id": "duplicate",
                    "block_type": "formBlock",
                    "occurrence_index": 0,
                },
            ],
        )
        self.assertNotIn("content", context["occurrences"][0])
        self.assertEqual(schema, before)

    def test_publish_validation_rejects_duplicate_page_and_form_ids_with_context(self):
        with self.assertRaises(HTTPException) as duplicate_page:
            builder_routes.validate_publish_schema({
                "pages": [{"id": "page", "name": "One"}, {"id": "page", "name": "Two"}],
                "forms": [],
            })
        self.assertEqual(
            duplicate_page.exception.detail["context"]["issue_type"],
            "duplicate_page_id",
        )

        with self.assertRaises(HTTPException) as duplicate_form:
            builder_routes.validate_publish_schema({
                "pages": [{"id": "home"}],
                "forms": [{"id": "form", "title": "One"}, {"id": "form", "title": "Two"}],
            })
        self.assertEqual(
            duplicate_form.exception.detail["context"]["issue_type"],
            "duplicate_form_id",
        )

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
        self.assertEqual(
            disconnected.exception.detail["context"],
            {
                "issue_type": "orphaned_form_block",
                "page_id": "home",
                "page_name": "",
                "block_id": "form-block-1",
                "block_label": "Form",
                "form_id": "missing-form",
            },
        )

    def test_publish_validation_normalizes_valid_legacy_form_reference(self):
        schema = {
            "pages": [{
                "id": "home",
                "name": "Home",
                "sections": [{"elements": [{
                    "id": "form-block-1",
                    "type": "formBlock",
                    "formId": "contact-form",
                }]}],
            }],
            "forms": [{"id": "contact-form"}],
        }

        validated, _ = builder_routes.validate_publish_schema(schema)

        self.assertEqual(
            validated["pages"][0]["sections"][0]["elements"][0]["connectedFormId"],
            "contact-form",
        )
        self.assertNotIn(
            "formId",
            validated["pages"][0]["sections"][0]["elements"][0],
        )

    def test_publish_validation_accepts_canonical_multi_page_form_references_without_adding_blocks(self):
        schema = {
            "pages": [
                {
                    "id": "home",
                    "name": "Home",
                    "slug": "/",
                    "sections": [{"elements": [{
                        "id": "home-form-block",
                        "type": "formBlock",
                        "connectedFormId": "form-1",
                    }]}],
                },
                {
                    "id": "contact",
                    "name": "Contact",
                    "slug": "/contact",
                    "sections": [{"elements": [{
                        "id": "contact-form-block",
                        "type": "formBlock",
                        "connectedFormId": "form-2",
                    }]}],
                },
            ],
            "forms": [{"id": "form-1"}, {"id": "form-2"}],
        }
        block_count_before = sum(
            len(section.get("elements") or [])
            for page in schema["pages"]
            for section in page["sections"]
        )

        validated, _ = builder_routes.validate_publish_schema(schema)

        block_count_after = sum(
            len(section.get("elements") or [])
            for page in validated["pages"]
            for section in page["sections"]
        )
        self.assertEqual(block_count_after, block_count_before)
        self.assertEqual(block_count_after, 2)

    def test_publish_validation_normalizes_snake_case_legacy_form_reference(self):
        schema = {
            "pages": [{
                "id": "home",
                "sections": [{"elements": [{
                    "id": "form-block-1",
                    "type": "formBlock",
                    "form_id": "form-1",
                }]}],
            }],
            "forms": [{"id": "form-1"}],
        }

        validated, _ = builder_routes.validate_publish_schema(schema)
        block = validated["pages"][0]["sections"][0]["elements"][0]

        self.assertEqual(block["connectedFormId"], "form-1")
        self.assertNotIn("form_id", block)

    def test_publish_validation_does_not_resurrect_legacy_reference_after_explicit_disconnect(self):
        schema = {
            "pages": [{
                "id": "home",
                "sections": [{"elements": [{
                    "id": "form-block-1",
                    "type": "formBlock",
                    "connectedFormId": "",
                    "formId": "form-1",
                }]}],
            }],
            "forms": [{"id": "form-1"}],
        }

        with self.assertRaises(HTTPException) as disconnected:
            builder_routes.validate_publish_schema(schema)

        self.assertEqual(
            disconnected.exception.detail["context"]["issue_type"],
            "orphaned_form_block",
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

        self.assertEqual(version, 1)
        self.assertEqual(
            validated["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"][0]["action"]["pageId"],
            "home",
        )
        self.assertIsNot(validated, schema)
        self.assertEqual(
            validated["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"][0]["action"],
            {"type": "goToPage", "pageId": "home"},
        )
        self.assertNotIn("defaultPageId", schema)

    def test_publish_validation_keeps_page_block_collections_separate(self):
        schema = {
            "pages": [
                {"id": "home", "name": "Home", "slug": "/", "sections": [{"freeElements": [{"id": "hero", "type": "heading"}]}]},
                {"id": "form", "name": "Form", "slug": "/form", "sections": [{"freeElements": [{"id": "form-block", "type": "formBlock", "connectedFormId": "form-1"}]}]},
                {"id": "buttons", "name": "Buttons", "slug": "/buttons", "sections": [{"freeElements": [{"id": "message", "type": "button", "action": {"type": "showMessage", "message": "Hello"}}]}]},
            ],
            "forms": [{"id": "form-1"}],
        }

        validated, _ = builder_routes.validate_publish_schema(schema)

        self.assertEqual([item["type"] for item in validated["pages"][0]["sections"][0]["freeElements"]], ["heading"])
        self.assertEqual([item["type"] for item in validated["pages"][1]["sections"][0]["freeElements"]], ["formBlock"])
        self.assertEqual([item["type"] for item in validated["pages"][2]["sections"][0]["freeElements"]], ["button"])

    def test_publish_validation_enforces_button_action_contract_with_safe_context(self):
        def schema_for(action):
            return {
                "pages": [{
                    "id": "home",
                    "name": "Home",
                    "slug": "/",
                    "sections": [{"freeElements": [{"id": "button-1", "type": "button", "action": action}]}],
                }],
                "forms": [],
            }

        valid_actions = [
            {"type": "goToPage", "pageId": "home"},
            {"type": "openUrl", "url": "https://example.com/path"},
            {"type": "showMessage", "message": "Safe plain text"},
        ]
        for action in valid_actions:
            validated, _ = builder_routes.validate_publish_schema(schema_for(action))
            self.assertEqual(validated["pages"][0]["sections"][0]["freeElements"][0]["action"]["type"], action["type"])

        invalid_actions = [
            ({"type": "goToPage", "pageId": "missing"}, "invalid_button_page_target"),
            ({"type": "openUrl", "url": "javascript:alert(1)"}, "invalid_button_url"),
            ({"type": "showMessage", "message": "  "}, "empty_button_message"),
        ]
        for action, issue_type in invalid_actions:
            with self.assertRaises(HTTPException) as rejected:
                builder_routes.validate_publish_schema(schema_for(action))
            context = rejected.exception.detail["context"]
            self.assertEqual(context["issue_type"], issue_type)
            self.assertEqual(context["page_id"], "home")
            self.assertEqual(context["block_id"], "button-1")
            self.assertNotIn("message", context)

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

    def test_archived_project_update_is_rejected_before_mutation(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "archived",
            "draft_schema": {"pages": [{"id": "home"}]},
            "draft_revision": 4,
        }
        fake = _ProjectMutationSupabase(project)
        client = _builder_client()
        with patch.object(builder_routes, "service_supabase", fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project):
            response = client.put(
                "/builder/projects/project-1",
                json={"draft_schema": {"pages": []}, "expected_revision": 4},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "builder_project_archived")
        self.assertIsNone(fake.query.payload)

    def test_draft_update_replaces_one_page_with_complete_three_page_schema(self):
        project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"pages": [{"id": "home", "name": "Home"}]},
            "draft_revision": 5,
        }
        three_pages = {
            "defaultPageId": "home",
            "pages": [
                {"id": "home", "name": "Home"},
                {"id": "test-2", "name": "Test 2"},
                {"id": "page-3", "name": "Page 3"},
            ],
        }
        fake = _ProjectMutationSupabase(project)
        client = _builder_client()
        with patch.object(builder_routes, "service_supabase", fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=project):
            response = client.put(
                "/builder/projects/project-1",
                json={"draft_schema": three_pages, "expected_revision": 5},
            )

        self.assertEqual(response.status_code, 200)
        saved = response.json()["project"]
        self.assertEqual(saved["draft_revision"], 6)
        self.assertEqual(len(saved["draft_schema"]["pages"]), 3)
        self.assertEqual(
            [page["name"] for page in saved["draft_schema"]["pages"]],
            ["Home", "Test 2", "Page 3"],
        )

        second_schema = copy.deepcopy(three_pages)
        second_schema["pages"][2]["name"] = "Renamed"
        second_fake = _ProjectMutationSupabase(saved)
        with patch.object(builder_routes, "service_supabase", second_fake), \
             patch.object(builder_routes, "require_builder_write_access", return_value=_builder_context()), \
             patch.object(builder_routes, "get_project_for_tenant", return_value=saved):
            second = client.put(
                "/builder/projects/project-1",
                json={"draft_schema": second_schema, "expected_revision": 6},
            )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["project"]["draft_revision"], 7)
        self.assertEqual(second.json()["project"]["draft_schema"]["pages"][2]["name"], "Renamed")

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
            "draft_schema": {
                "schema_version": 1,
                "pages": [{"id": "home", "name": "Home"}],
            },
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
        self.assertEqual(fake.calls[0][0], "publish_validated_builder_project_atomic")
        self.assertEqual(fake.calls[0][1]["p_expected_revision"], 4)
        self.assertEqual(
            fake.calls[0][1]["p_published_schema"],
            {
                "schema_version": 1,
                "defaultPageId": "home",
                "pages": [
                    {
                        "id": "home",
                        "name": "Home",
                        "slug": "/",
                        "isDefault": True,
                        "showInNavigation": True,
                        "order": 0,
                    }
                ],
            },
        )
        self.assertNotIn("defaultPageId", project["draft_schema"])
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
             patch.object(builder_routes, "get_website_settings_record", return_value=None), \
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
