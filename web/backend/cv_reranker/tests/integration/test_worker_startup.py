from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.db.models import WorkerInstance
from app.db.session import get_sync_session
from app.workers import ranking_worker
from tests.integration.test_worker_pipeline import FakeReranker


def test_worker_initializes_reranker_once_connects_and_polls(monkeypatch: Any) -> None:
    initializations = 0

    class StartupReranker(FakeReranker):
        def __init__(self, _settings: object) -> None:
            nonlocal initializations
            initializations += 1

    def stop_after_first_idle_poll(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(ranking_worker, "SentenceTransformerReranker", StartupReranker)
    monkeypatch.setattr(ranking_worker.time, "sleep", stop_after_first_idle_poll)
    ranking_worker.main()
    assert initializations == 1
    with get_sync_session() as db:
        assert db.scalar(select(func.count()).select_from(WorkerInstance)) == 1
