from __future__ import annotations

import asyncio
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.routes.jobs import _upsert_file
from app.auth.password import hash_password
from app.core.config import get_settings
from app.db.models import (
    ChunkScore,
    DocumentContent,
    JobDocument,
    RankingJob,
    RankingResult,
    StoredFile,
    User,
)
from app.db.session import AsyncSessionFactory, SyncSessionFactory, get_sync_session
from app.services.document_storage.local import LocalDocumentStorage, StagedFile
from app.services.jobs.worker import JobProcessor, claim_next_job, recover_stale_jobs
from app.services.text_processing.normalization import text_hash
from tests.integration.test_worker_pipeline import FakeReranker

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def require_postgres() -> None:
    if not os.environ.get("POSTGRES_TEST_URL"):
        pytest.skip("Set POSTGRES_TEST_URL to run real PostgreSQL locking tests.")


def _make_user_and_jobs(count: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
    owner = uuid.uuid4()
    with get_sync_session() as db:
        db.add(
            User(
                id=owner,
                email=f"{owner}@example.com",
                normalized_email=f"{owner}@example.com",
                password_hash=hash_password("Strong-Password-Number-42"),
                display_name="PostgreSQL Test",
            )
        )
        jobs = [
            RankingJob(
                user_id=owner,
                baseline_text=f"role {index}",
                baseline_sha256=text_hash(f"role {index}"),
            )
            for index in range(count)
        ]
        db.add_all(jobs)
        db.commit()
        return owner, [job.id for job in jobs]


def _concurrent_claim(barrier: threading.Barrier) -> uuid.UUID | None:
    barrier.wait()
    with SyncSessionFactory() as db:
        return claim_next_job(db, uuid.uuid4())


def test_one_job_is_claimed_by_only_one_of_two_workers() -> None:
    _owner, job_ids = _make_user_and_jobs(1)
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_concurrent_claim, [barrier, barrier]))
    assert results.count(job_ids[0]) == 1
    assert results.count(None) == 1


def test_skip_locked_allows_two_workers_to_claim_distinct_jobs() -> None:
    _owner, job_ids = _make_user_and_jobs(2)
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_concurrent_claim, [barrier, barrier]))
    assert set(results) == set(job_ids)


def test_skip_locked_bypasses_an_open_row_lock() -> None:
    _owner, job_ids = _make_user_and_jobs(2)
    locked = threading.Event()
    release = threading.Event()

    def hold_oldest_lock() -> None:
        with SyncSessionFactory() as db:
            db.scalar(select(RankingJob).where(RankingJob.id == job_ids[0]).with_for_update())
            locked.set()
            assert release.wait(timeout=10)
            db.rollback()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(hold_oldest_lock)
        assert locked.wait(timeout=10)
        with SyncSessionFactory() as db:
            claimed = claim_next_job(db, uuid.uuid4())
        release.set()
        future.result(timeout=10)
    assert claimed == job_ids[1]


def test_rolled_back_claim_remains_claimable() -> None:
    _owner, job_ids = _make_user_and_jobs(1)
    with SyncSessionFactory() as db:
        job = db.scalar(select(RankingJob).where(RankingJob.id == job_ids[0]).with_for_update())
        assert job is not None
        job.status = "processing"
        db.flush()
        db.rollback()
    with SyncSessionFactory() as db:
        assert claim_next_job(db, uuid.uuid4()) == job_ids[0]


def test_concurrent_content_cache_upsert_returns_one_row() -> None:
    owner, _jobs = _make_user_and_jobs(0)
    processor = JobProcessor(get_settings(), FakeReranker(), uuid.uuid4())
    barrier = threading.Barrier(2)
    values = {
        "user_id": owner,
        "file_sha256": "a" * 64,
        "raw_text": "Python",
        "normalized_text": "Python",
        "normalized_text_hash": text_hash("Python"),
        "extractor_name": "test",
        "extractor_version": "test-v1",
        "normalization_version": "test-v1",
        "extraction_metadata": {},
        "warnings": [],
        "truncated": False,
    }

    def upsert() -> uuid.UUID:
        with SyncSessionFactory() as db:
            barrier.wait()
            row_id = processor._upsert(
                db,
                DocumentContent,
                {"id": uuid.uuid4(), **values},
                ["user_id", "file_sha256", "extractor_version", "normalization_version"],
            )
            db.commit()
            return row_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _index: upsert(), range(2)))
    assert ids[0] == ids[1]
    with get_sync_session() as db:
        assert db.scalar(select(func.count()).select_from(DocumentContent)) == 1


async def test_concurrent_identical_uploads_share_one_database_and_physical_file() -> None:
    settings = get_settings()
    storage = LocalDocumentStorage(settings)
    owner, _jobs = _make_user_and_jobs(0)
    payload = "identical upload bytes"
    staged_files: list[StagedFile] = []
    for _index in range(2):
        path = settings.temp_directory / f"{uuid.uuid4()}.upload"
        path.write_text(payload, encoding="utf-8")
        staged_files.append(
            StagedFile(
                path,
                text_hash(payload),
                path.stat().st_size,
                "same.txt",
                "text/plain",
            )
        )
    ready = asyncio.Event()
    arrivals = 0
    arrivals_lock = asyncio.Lock()

    async def upload(staged: StagedFile) -> uuid.UUID:
        nonlocal arrivals
        committed: list[str] = []
        async with AsyncSessionFactory() as db:
            async with arrivals_lock:
                arrivals += 1
                if arrivals == 2:
                    ready.set()
            await ready.wait()
            stored = await _upsert_file(db, storage, staged, owner, committed)
            await db.commit()
            return stored.id

    first_id, second_id = await asyncio.gather(*(upload(item) for item in staged_files))
    assert first_id == second_id
    with get_sync_session() as db:
        rows = list(db.scalars(select(StoredFile)).all())
        assert len(rows) == 1
        key = rows[0].storage_key
    assert storage.path(key).exists()
    owner_files = [path for path in (storage.root / str(owner)).rglob("*") if path.is_file()]
    assert owner_files == [storage.path(key)]
    storage.delete(key)


def test_concurrent_pipeline_cache_writes_are_unique() -> None:
    settings = get_settings()
    storage = LocalDocumentStorage(settings)
    owner, _jobs = _make_user_and_jobs(0)
    staged_path = settings.temp_directory / f"{uuid.uuid4()}.upload"
    staged_path.write_text("Python FastAPI PostgreSQL", encoding="utf-8")
    staged = StagedFile(
        staged_path,
        text_hash("Python FastAPI PostgreSQL"),
        staged_path.stat().st_size,
        "shared.txt",
        "text/plain",
    )
    key = storage.commit(staged, owner)
    try:
        with get_sync_session() as db:
            stored = StoredFile(
                user_id=owner,
                storage_key=key,
                file_sha256=staged.sha256,
                file_size=staged.size,
                mime_type=staged.mime_type,
                sanitized_filename=staged.filename,
            )
            role = "Python engineer"
            jobs = [
                RankingJob(
                    user_id=owner,
                    baseline_text=role,
                    baseline_sha256=text_hash(role),
                    total_files=1,
                )
                for _index in range(2)
            ]
            db.add_all([stored, *jobs])
            db.flush()
            db.add_all(
                JobDocument(user_id=owner, job_id=job.id, stored_file_id=stored.id) for job in jobs
            )
            db.commit()
            job_ids = [job.id for job in jobs]
        worker_ids = [uuid.uuid4(), uuid.uuid4()]
        claimed: list[uuid.UUID] = []
        for worker_id in worker_ids:
            with get_sync_session() as db:
                job_id = claim_next_job(db, worker_id)
                assert job_id is not None
                claimed.append(job_id)
        barrier = threading.Barrier(2)

        def process(index: int) -> None:
            barrier.wait()
            with SyncSessionFactory() as db:
                JobProcessor(settings, FakeReranker(), worker_ids[index]).process(
                    db, claimed[index]
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(process, range(2)))
        with get_sync_session() as db:
            assert set(claimed) == set(job_ids)
            assert db.scalar(select(func.count()).select_from(DocumentContent)) == 1
            assert db.scalar(select(func.count()).select_from(RankingResult)) == 1
            assert db.scalar(select(func.count()).select_from(ChunkScore)) == 1
            documents = list(db.scalars(select(JobDocument)).all())
            assert len(documents) == 2
            assert {item.status for item in documents} == {"completed"}
            assert len({item.ranking_result_id for item in documents}) == 1
    finally:
        storage.delete(key)


def test_retry_processing_is_idempotent() -> None:
    settings = get_settings()
    storage = LocalDocumentStorage(settings)
    owner, _jobs = _make_user_and_jobs(0)
    staged_path = settings.temp_directory / f"{uuid.uuid4()}.upload"
    staged_path.write_text("Python FastAPI PostgreSQL", encoding="utf-8")
    staged = StagedFile(
        staged_path,
        text_hash("Python FastAPI PostgreSQL"),
        staged_path.stat().st_size,
        "retry.txt",
        "text/plain",
    )
    key = storage.commit(staged, owner)
    try:
        with get_sync_session() as db:
            stored = StoredFile(
                user_id=owner,
                storage_key=key,
                file_sha256=staged.sha256,
                file_size=staged.size,
                mime_type=staged.mime_type,
                sanitized_filename=staged.filename,
            )
            role = "Python engineer"
            job = RankingJob(
                user_id=owner,
                baseline_text=role,
                baseline_sha256=text_hash(role),
                total_files=1,
            )
            db.add_all([stored, job])
            db.flush()
            db.add(JobDocument(user_id=owner, job_id=job.id, stored_file_id=stored.id))
            db.commit()
            job_id = job.id
        worker_id = uuid.uuid4()
        with get_sync_session() as db:
            assert claim_next_job(db, worker_id) == job_id
        with get_sync_session() as db:
            JobProcessor(settings, FakeReranker(), worker_id).process(db, job_id)
        with get_sync_session() as db:
            job = db.get(RankingJob, job_id)
            assert job is not None
            job.status = "queued"
            job.worker_id = None
            db.commit()
        with get_sync_session() as db:
            assert claim_next_job(db, worker_id) == job_id
        with get_sync_session() as db:
            JobProcessor(settings, FakeReranker(), worker_id).process(db, job_id)
        with get_sync_session() as db:
            job = db.get(RankingJob, job_id)
            assert job is not None
            assert job.status == "completed"
            assert job.processed_files == 1
            assert db.scalar(select(func.count()).select_from(DocumentContent)) == 1
            assert db.scalar(select(func.count()).select_from(RankingResult)) == 1
            assert db.scalar(select(func.count()).select_from(ChunkScore)) == 1
    finally:
        storage.delete(key)


def test_stale_recovery_requeues_fails_and_finishes_cancellation() -> None:
    settings = get_settings().model_copy(
        update={"job_stale_after_minutes": 1, "job_max_attempts": 3}
    )
    owner, _jobs = _make_user_and_jobs(0)
    stale = datetime.now(UTC) - timedelta(minutes=5)
    with get_sync_session() as db:
        requeue = RankingJob(
            user_id=owner,
            baseline_text="requeue",
            baseline_sha256=text_hash("requeue"),
            status="processing",
            heartbeat_at=stale,
            attempt_count=1,
        )
        fail = RankingJob(
            user_id=owner,
            baseline_text="fail",
            baseline_sha256=text_hash("fail"),
            status="processing",
            heartbeat_at=stale,
            attempt_count=3,
        )
        cancel = RankingJob(
            user_id=owner,
            baseline_text="cancel",
            baseline_sha256=text_hash("cancel"),
            status="cancellation_requested",
            heartbeat_at=stale,
            attempt_count=1,
        )
        db.add_all([requeue, fail, cancel])
        db.commit()
        ids = (requeue.id, fail.id, cancel.id)
    with get_sync_session() as db:
        assert recover_stale_jobs(db, settings) == 3
    with get_sync_session() as db:
        assert db.get(RankingJob, ids[0]).status == "queued"  # type: ignore[union-attr]
        assert db.get(RankingJob, ids[1]).status == "failed"  # type: ignore[union-attr]
        assert db.get(RankingJob, ids[2]).status == "cancelled"  # type: ignore[union-attr]


def test_processing_cancellation_is_observed_between_inference_batches() -> None:
    settings = get_settings().model_copy(
        update={"rerank_batch_size": 1, "chunk_token_size": 32, "chunk_token_overlap": 0}
    )
    storage = LocalDocumentStorage(settings)
    owner, _jobs = _make_user_and_jobs(0)
    content = " ".join(f"token{index}" for index in range(70))
    staged_path = settings.temp_directory / f"{uuid.uuid4()}.upload"
    staged_path.write_text(content, encoding="utf-8")
    staged = StagedFile(
        staged_path,
        text_hash(content),
        staged_path.stat().st_size,
        "cancel.txt",
        "text/plain",
    )
    key = storage.commit(staged, owner)
    try:
        with get_sync_session() as db:
            stored = StoredFile(
                user_id=owner,
                storage_key=key,
                file_sha256=staged.sha256,
                file_size=staged.size,
                mime_type=staged.mime_type,
                sanitized_filename=staged.filename,
            )
            role = "token0 engineer"
            job = RankingJob(
                user_id=owner,
                baseline_text=role,
                baseline_sha256=text_hash(role),
                total_files=1,
            )
            db.add_all([stored, job])
            db.flush()
            db.add(JobDocument(user_id=owner, job_id=job.id, stored_file_id=stored.id))
            db.commit()
            job_id = job.id
        worker_id = uuid.uuid4()

        class CancellingReranker(FakeReranker):
            calls = 0

            def predict(self, pairs: list[tuple[str, str]], batch_size: int) -> list[float]:
                values = super().predict(pairs, batch_size)
                self.calls += 1
                if self.calls == 1:
                    with get_sync_session() as cancellation_db:
                        running = cancellation_db.get(RankingJob, job_id)
                        assert running is not None
                        running.status = "cancellation_requested"
                        running.current_stage = "cancellation_requested"
                        cancellation_db.commit()
                return values

        reranker = CancellingReranker()
        with get_sync_session() as db:
            assert claim_next_job(db, worker_id) == job_id
        with get_sync_session() as db:
            JobProcessor(settings, reranker, worker_id).process(db, job_id)
        with get_sync_session() as db:
            cancelled = db.get(RankingJob, job_id)
            assert cancelled is not None
            assert cancelled.status == "cancelled"
            assert 0 < cancelled.processed_pairs < cancelled.total_pairs
            document = db.scalar(select(JobDocument).where(JobDocument.job_id == job_id))
            assert document is not None
            assert document.status == "cancelled"
        assert reranker.calls == 1
    finally:
        storage.delete(key)
