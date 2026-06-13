import asyncio
import unittest

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.testclient import TestClient

from services.request_body_limits import RequestBodyLimitMiddleware
from services.request_security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    create_csrf_token,
    get_allowed_origins,
    validate_cookie_write_origin,
    validate_csrf_token,
)


def build_body_limit_client(
    *,
    max_request_body_bytes=2048,
    max_json_body_bytes=256,
    max_small_json_body_bytes=64,
    max_data_json_body_bytes=128,
):
    app = FastAPI()
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_request_body_bytes=max_request_body_bytes,
        max_json_body_bytes=max_json_body_bytes,
        max_small_json_body_bytes=max_small_json_body_bytes,
        max_data_json_body_bytes=max_data_json_body_bytes,
    )

    @app.post("/auth/login")
    def login(payload: dict):
        return {"ok": True, "payload": payload}

    @app.post("/public/contact")
    def public_contact(payload: dict):
        return {"ok": True, "payload": payload}

    @app.post("/public/sites/example/forms/form-1/submissions")
    def public_form(payload: dict):
        return {"ok": True, "payload": payload}

    @app.post("/builder/projects")
    def create_builder_project(payload: dict):
        raise HTTPException(status_code=400, detail="business validation reached")

    @app.post("/users/1/data/upload")
    async def upload_data(file: UploadFile = File(...)):
        content = await file.read()
        return {"size": len(content)}

    @app.get("/builder/projects")
    def list_builder_projects():
        return {"ok": True}

    return TestClient(app)


class RequestBodyLimitTests(unittest.TestCase):
    def assert_payload_too_large(self, response):
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"detail": "Request body too large"})

    def test_normal_small_json_request_succeeds(self):
        client = build_body_limit_client()

        response = client.post("/auth/login", json={"ok": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"], {"ok": True})

    def test_oversized_small_json_route_returns_413(self):
        client = build_body_limit_client(max_small_json_body_bytes=48)

        response = client.post("/auth/login", json={"payload": "x" * 80})

        self.assert_payload_too_large(response)

    def test_oversized_public_contact_and_form_json_return_413(self):
        client = build_body_limit_client(max_small_json_body_bytes=48)

        for path in [
            "/public/contact",
            "/public/sites/example/forms/form-1/submissions",
        ]:
            with self.subTest(path=path):
                response = client.post(path, json={"payload": "x" * 80})
                self.assert_payload_too_large(response)

    def test_builder_json_under_builder_limit_reaches_route_validation(self):
        client = build_body_limit_client(
            max_json_body_bytes=512,
            max_small_json_body_bytes=48,
        )

        response = client.post("/builder/projects", json={"draft_schema": {"text": "x" * 120}})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "business validation reached")

    def test_oversized_builder_json_returns_413(self):
        client = build_body_limit_client(max_json_body_bytes=128)

        response = client.post("/builder/projects", json={"draft_schema": {"text": "x" * 200}})

        self.assert_payload_too_large(response)

    def test_multipart_upload_under_limit_passes_middleware(self):
        client = build_body_limit_client(max_request_body_bytes=2048)

        response = client.post(
            "/users/1/data/upload",
            files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["size"], len(b"a,b\n1,2\n"))

    def test_multipart_upload_over_middleware_limit_returns_413(self):
        client = build_body_limit_client(max_request_body_bytes=512)

        response = client.post(
            "/users/1/data/upload",
            files={"file": ("data.csv", b"x" * 2000, "text/csv")},
        )

        self.assert_payload_too_large(response)

    def test_misleading_content_length_is_enforced_by_stream_count(self):
        async def body_reader_app(scope, receive, send):
            while True:
                message = await receive()
                if message.get("type") != "http.request" or not message.get("more_body"):
                    break

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": b'{"ok":true}'})

        middleware = RequestBodyLimitMiddleware(
            body_reader_app,
            max_request_body_bytes=10,
            max_json_body_bytes=10,
        )
        messages = [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"678901", "more_body": False},
        ]
        sent_messages = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent_messages.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/raw",
            "headers": [
                (b"content-type", b"application/octet-stream"),
                (b"content-length", b"5"),
            ],
        }

        asyncio.run(middleware(scope, receive, send))

        response_start = next(message for message in sent_messages if message["type"] == "http.response.start")
        response_body = next(message for message in sent_messages if message["type"] == "http.response.body")
        self.assertEqual(response_start["status"], 413)
        self.assertEqual(response_body["body"], b'{"detail":"Request body too large"}')

    def test_csrf_origin_flow_remains_unchanged_for_normal_authenticated_write(self):
        app = FastAPI()
        allowed_origins = get_allowed_origins(["https://app.example.com"])
        app.add_middleware(RequestBodyLimitMiddleware, max_json_body_bytes=512)

        @app.middleware("http")
        async def csrf_middleware(request: Request, call_next):
            blocked_response = validate_cookie_write_origin(request, allowed_origins)
            if blocked_response is not None:
                return blocked_response
            blocked_response = validate_csrf_token(request)
            if blocked_response is not None:
                return blocked_response
            return await call_next(request)

        @app.post("/protected-write")
        def protected_write(payload: dict):
            return {"ok": True, "payload": payload}

        client = TestClient(app)
        csrf_token = create_csrf_token(
            access_token="access-token",
            refresh_token="refresh-token",
        )
        response = client.post(
            "/protected-write",
            json={"ok": True},
            headers={
                "Origin": "https://app.example.com",
                CSRF_HEADER_NAME: csrf_token,
            },
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
                CSRF_COOKIE_NAME: csrf_token,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"], {"ok": True})

    def test_get_routes_do_not_trigger_body_limit_issues(self):
        client = build_body_limit_client(max_request_body_bytes=1)

        response = client.get("/builder/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()
