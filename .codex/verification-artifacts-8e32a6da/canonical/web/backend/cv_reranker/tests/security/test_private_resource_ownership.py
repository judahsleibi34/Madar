from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import JobDocument
from app.db.session import get_sync_session
from app.main import app
from app.services.jobs.worker import JobProcessor, claim_next_job
from tests.api.test_auth_and_ownership import register_and_login
from tests.integration.test_worker_pipeline import FakeReranker


def test_every_private_job_resource_uses_equivalent_not_found() -> None:
    settings = get_settings()
    with TestClient(app) as client:
        owner_token = register_and_login(client, "private-owner@example.com")
        attacker_token = register_and_login(client, "private-attacker@example.com")
        created = client.post(
            "/api/v1/ranking-jobs",
            headers={"Authorization": f"Bearer {owner_token}"},
            data={"baseline": "Python PostgreSQL engineer"},
            files=[("files", ("private.txt", b"Python PostgreSQL", "text/plain"))],
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        worker_id = uuid.uuid4()
        with get_sync_session() as db:
            claimed = claim_next_job(db, worker_id)
        assert str(claimed) == job_id
        assert claimed is not None
        with get_sync_session() as db:
            JobProcessor(settings, FakeReranker(), worker_id).process(db, claimed)
            document = db.query(JobDocument).filter_by(job_id=claimed).one()
            document_id = document.id

        attacker_headers = {"Authorization": f"Bearer {attacker_token}"}
        paths = [
            ("GET", f"/api/v1/ranking-jobs/{job_id}"),
            ("GET", f"/api/v1/ranking-jobs/{job_id}/documents"),
            ("GET", f"/api/v1/ranking-jobs/{job_id}/documents/{document_id}/parsed"),
            ("GET", f"/api/v1/ranking-jobs/{job_id}/documents/{document_id}/original"),
            ("POST", f"/api/v1/ranking-jobs/{job_id}/cancel"),
            ("DELETE", f"/api/v1/ranking-jobs/{job_id}"),
        ]
        for method, path in paths:
            response = client.request(method, path, headers=attacker_headers)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
            assert response.json()["error"]["message"] == "The requested resource was not found."

        unknown = client.get(f"/api/v1/ranking-jobs/{uuid.uuid4()}", headers=attacker_headers)
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        listing = client.get("/api/v1/ranking-jobs", headers=attacker_headers)
        assert listing.status_code == 200
        assert listing.json()["items"] == []
