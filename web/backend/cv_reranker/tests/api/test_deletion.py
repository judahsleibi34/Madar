from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import StoredFile
from app.db.session import get_sync_session
from app.main import app
from app.services.document_storage.local import LocalDocumentStorage


def token(client: TestClient) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "delete@example.com",
            "password": "Strong-Password-Number-42",
            "display_name": "Delete Test",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "delete@example.com", "password": "Strong-Password-Number-42"},
    )
    return response.json()["access_token"]


def create(client: TestClient, access: str) -> str:
    response = client.post(
        "/api/v1/ranking-jobs",
        headers={"Authorization": f"Bearer {access}"},
        data={"baseline": "Python engineer"},
        files=[("files", ("candidate.txt", b"Python engineer", "text/plain"))],
    )
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_delete_preserves_shared_file_then_removes_last_reference() -> None:
    with TestClient(app) as client:
        access = token(client)
        first = create(client, access)
        client.post(
            f"/api/v1/ranking-jobs/{first}/cancel",
            headers={"Authorization": f"Bearer {access}"},
        )
        second = create(client, access)
        client.post(
            f"/api/v1/ranking-jobs/{second}/cancel",
            headers={"Authorization": f"Bearer {access}"},
        )

        with get_sync_session() as db:
            stored = db.scalar(select(StoredFile))
            assert stored is not None
            key = stored.storage_key
        storage = LocalDocumentStorage(get_settings())
        assert storage.path(key).exists()

        deleted_first = client.delete(
            f"/api/v1/ranking-jobs/{first}",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert deleted_first.status_code == 204
        assert storage.path(key).exists()

        deleted_second = client.delete(
            f"/api/v1/ranking-jobs/{second}",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert deleted_second.status_code == 204
        assert not storage.path(key).exists()
        with get_sync_session() as db:
            assert db.scalar(select(StoredFile)) is None
