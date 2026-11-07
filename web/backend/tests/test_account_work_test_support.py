import unittest

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient

from services.account_work_fence import (
    AccountWorkBusy, AccountWorkFenceMiddleware, account_lock, protect_request,
)
from services.account_erasure_service import require_backend_session
from services.project_dataset_service import schema_version
from tests.account_work_test_support import (
    FenceClient, account_fixture, route_account_fixture, session_token,
)


class OfflineAccountFixtureTests(unittest.TestCase):
    def test_unknown_schema_does_not_admit_registration(self):
        with account_fixture([(3, 7)]) as client:
            client.tables["application_schema_state"][0]["schema_version"] = 168
            with self.assertRaises(AccountWorkBusy):
                with account_lock(3, 7):
                    self.fail("unsupported schema admitted")

    def test_provider_fixture_verifies_tokens_before_real_session_and_fence(self):
        from services.auth_service import get_authenticated_user_row
        app = FastAPI()
        app.add_middleware(AccountWorkFenceMiddleware)

        @app.get("/actor")
        def actor(request: Request, response: Response):
            _, user = get_authenticated_user_row(request, response)
            return {"user_id": user["id"], "tenant_id": user["tenant_id"]}

        with route_account_fixture([(3, 7)]), TestClient(app) as client:
            self.assertEqual(client.get("/actor").status_code, 401)
            for token in ("invalid", session_token("offline-4-7")):
                client.cookies.set("madar_access_token", token)
                self.assertEqual(client.get("/actor").status_code, 401)
            client.cookies.set("madar_access_token", session_token("offline-3-7"))
            response = client.get("/actor")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {"user_id": 7, "tenant_id": 3})

    def test_schema_and_exact_actor_registration(self):
        with account_fixture([(3, 7)]) as client:
            self.assertEqual(schema_version(client=client), 167)
            with account_lock(3, 7):
                with self.assertRaises(AccountWorkBusy):
                    with account_lock(3, 7, exclusive=True):
                        self.fail("exclusive lock admitted during shared work")
            with account_lock(3, 7, exclusive=True):
                pass
            self.assertEqual(client.calls, [("account_fence_registration167",
                                            {"p_tenant_id": 3, "p_user_id": 7})])

    def test_cross_tenant_and_unknown_actor_are_denied(self):
        with account_fixture([(3, 7)]):
            for identity in ((4, 7), (3, 8)):
                with self.subTest(identity=identity), self.assertRaises(HTTPException) as error:
                    with account_lock(*identity):
                        self.fail("unknown actor admitted")
                self.assertEqual(error.exception.status_code, 409)

    def test_hold_blocks_work(self):
        with account_fixture([(3, 7)]):
            with account_lock(3, 7, exclusive=True) as marker:
                marker.write_text("held")
            with self.assertRaises(HTTPException) as error:
                with account_lock(3, 7):
                    self.fail("held account admitted")
            self.assertEqual(error.exception.status_code, 409)

    def test_unknown_tables_rpcs_and_unscoped_queries_fail(self):
        client = FenceClient([(3, 7)])
        with self.assertRaises(AssertionError): client.table("unapproved")
        with self.assertRaises(AssertionError): client.rpc("unapproved", {})
        with self.assertRaises(AssertionError): client.table("users").select("*").execute()
        with self.assertRaises(AssertionError): client.rpc("account_fence_registration167", {"p_user_id": 7})

    def test_verified_identity_session_binding_and_revocation(self):
        sessions = {("actor", "offline-session")}
        client = FenceClient(sessions=sessions)
        token = session_token("actor")
        require_backend_session(auth_id="actor", token=token, client=client)
        for actor, supplied in (("other", token), ("actor", "invalid"),
                                 ("actor", session_token("actor", "unknown"))):
            with self.subTest(actor=actor), self.assertRaises(HTTPException) as error:
                require_backend_session(auth_id=actor, token=supplied, client=client)
            self.assertEqual(error.exception.status_code, 401)
        sessions.clear()
        with self.assertRaises(HTTPException):
            require_backend_session(auth_id="actor", token=token, client=client)

    def test_real_middleware_releases_fences_after_success_and_error(self):
        app = FastAPI()
        app.add_middleware(AccountWorkFenceMiddleware)

        @app.get("/work")
        def work(request: Request, fail: bool = False):
            protect_request(request, 3, 7)
            if fail: raise HTTPException(409, "fixture refusal")
            return {"ok": True}

        with account_fixture([(3, 7)]), TestClient(app) as client:
            for suffix, expected in (("", 200), ("?fail=true", 409)):
                self.assertEqual(client.get("/work" + suffix).status_code, expected)
                with account_lock(3, 7, exclusive=True): pass
