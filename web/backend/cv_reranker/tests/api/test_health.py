from fastapi.testclient import TestClient

from app.main import app


def test_health_paths_are_unversioned_and_ready() -> None:
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/v1/health/live").status_code == 404
