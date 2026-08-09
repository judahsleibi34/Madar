from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import User
from app.db.session import get_sync_session
from app.main import app


def test_refresh_rotation_detects_reuse_and_revokes_family() -> None:
    with TestClient(app) as client:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "rotate@example.com",
                "password": "Strong-Password-Number-42",
                "display_name": "Rotate User",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "rotate@example.com", "password": "Strong-Password-Number-42"},
        )
        old_token = login.json()["refresh_token"]
        rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
        assert rotated.status_code == 200, rotated.text
        new_token = rotated.json()["refresh_token"]

        reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
        assert reuse.status_code == 401
        family_revoked = client.post("/api/v1/auth/refresh", json={"refresh_token": new_token})
        assert family_revoked.status_code == 401


def test_me_logout_and_disabled_user_authentication() -> None:
    with TestClient(app) as client:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "lifecycle@example.com",
                "password": "Strong-Password-Number-42",
                "display_name": "Lifecycle User",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "lifecycle@example.com",
                "password": "Strong-Password-Number-42",
            },
        )
        access = login.json()["access_token"]
        refresh = login.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {access}"}
        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"] == "lifecycle@example.com"
        assert (
            client.post(
                "/api/v1/auth/logout",
                headers=headers,
                json={"refresh_token": refresh},
            ).status_code
            == 204
        )
        assert (
            client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
        )

        with get_sync_session() as db:
            user = db.scalar(select(User).where(User.normalized_email == "lifecycle@example.com"))
            assert user is not None
            user.is_active = False
            db.commit()
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "lifecycle@example.com",
                    "password": "Strong-Password-Number-42",
                },
            ).status_code
            == 401
        )
