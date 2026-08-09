from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client: TestClient, email: str) -> str:
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Strong-Password-Number-42",
            "display_name": "Test User",
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Strong-Password-Number-42"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_auth_job_creation_and_idor_protection() -> None:
    with TestClient(app) as client:
        first = register_and_login(client, "first@example.com")
        second = register_and_login(client, "second@example.com")
        created = client.post(
            "/api/v1/ranking-jobs",
            headers={"Authorization": f"Bearer {first}"},
            data={"baseline": "Senior Python engineer building reliable APIs"},
            files=[("files", ("candidate.txt", b"Python FastAPI PostgreSQL", "text/plain"))],
        )
        assert created.status_code == 202, created.text
        job_id = created.json()["job_id"]
        visible = client.get(
            f"/api/v1/ranking-jobs/{job_id}",
            headers={"Authorization": f"Bearer {first}"},
        )
        assert visible.status_code == 200
        hidden = client.get(
            f"/api/v1/ranking-jobs/{job_id}",
            headers={"Authorization": f"Bearer {second}"},
        )
        assert hidden.status_code == 404
        assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_error_shape_contains_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ranking-jobs")
        assert response.status_code == 401
        assert set(response.json()["error"]) == {"code", "message", "request_id"}
