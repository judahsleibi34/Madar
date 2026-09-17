from __future__ import annotations

import uuid
from pathlib import Path

from app.auth.password import hash_password
from app.core.config import get_settings
from app.db.models import JobDocument, RankingJob, StoredFile, User
from app.db.session import get_sync_session
from app.services.document_storage.local import LocalDocumentStorage, StagedFile
from app.services.jobs.worker import JobProcessor, claim_next_job
from app.services.text_processing.normalization import text_hash


class FakeTokenizer:
    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        del add_special_tokens
        self.words = text.split()
        return list(range(len(self.words)))

    def decode(self, tokens: list[int], skip_special_tokens: bool = True) -> str:
        del skip_special_tokens
        return " ".join(self.words[index] for index in tokens)


class FakeReranker:
    model_id = "fake-model"
    model_version = "test-v1"
    backend = "fake"
    tokenizer = FakeTokenizer()

    def predict(self, pairs: list[tuple[str, str]], batch_size: int) -> list[float]:
        del batch_size
        return [float(len(set(role.split()) & set(cv.split()))) for role, cv in pairs]


class RecordingReranker(FakeReranker):
    def __init__(self) -> None:
        self.batches: list[list[tuple[str, str]]] = []

    def predict(self, pairs: list[tuple[str, str]], batch_size: int) -> list[float]:
        self.batches.append(list(pairs))
        return super().predict(pairs, batch_size)


def test_worker_claims_extracts_chunks_and_persists_raw_score(tmp_path: Path) -> None:
    settings = get_settings()
    storage = LocalDocumentStorage(settings)
    owner = uuid.uuid4()
    staged_path = settings.temp_directory / f"{uuid.uuid4()}.upload"
    staged_path.write_text("Python FastAPI PostgreSQL leadership", encoding="utf-8")
    staged = StagedFile(
        staged_path,
        text_hash("Python FastAPI PostgreSQL leadership"),
        staged_path.stat().st_size,
        "candidate.txt",
        "text/plain",
    )
    key = storage.commit(staged, owner)
    worker_id = uuid.uuid4()
    try:
        with get_sync_session() as db:
            user = User(
                id=owner,
                email="worker@example.com",
                normalized_email="worker@example.com",
                password_hash=hash_password("Strong-Password-Number-42"),
                display_name="Worker Test",
            )
            db.add(user)
            db.flush()
            stored = StoredFile(
                user_id=owner,
                storage_key=key,
                file_sha256=staged.sha256,
                file_size=staged.size,
                mime_type=staged.mime_type,
                sanitized_filename=staged.filename,
            )
            role = "Python FastAPI engineer"
            job = RankingJob(
                user_id=owner,
                baseline_text=role,
                baseline_sha256=text_hash(role),
                total_files=1,
            )
            db.add_all([stored, job])
            db.flush()
            document = JobDocument(
                user_id=owner,
                job_id=job.id,
                stored_file_id=stored.id,
            )
            db.add(document)
            db.commit()
            job_id = job.id

        with get_sync_session() as db:
            assert claim_next_job(db, worker_id) == job_id
        with get_sync_session() as db:
            JobProcessor(settings, FakeReranker(), worker_id).process(db, job_id)

        with get_sync_session() as db:
            job = db.get(RankingJob, job_id)
            assert job is not None
            assert job.status == "completed"
            assert job.processed_files == 1
            document = db.query(JobDocument).filter_by(job_id=job_id).one()
            assert document.status == "completed"
            assert document.ranking_result is not None
            assert document.ranking_result.final_relevance_score == 2.0
            assert document.ranking_result.matching_excerpts[0]["score"] == 2.0
    finally:
        storage.delete(key)


def test_worker_flattens_all_candidates_into_bounded_batches_and_maps_scores() -> None:
    settings = get_settings().model_copy(update={"rerank_batch_size": 2})
    storage = LocalDocumentStorage(settings)
    owner = uuid.uuid4()
    role = "alpha beta gamma"
    candidates = {
        "one.txt": "alpha",
        "two.txt": "alpha beta",
        "three.txt": "alpha beta gamma",
    }
    keys: list[str] = []
    try:
        with get_sync_session() as db:
            user = User(
                id=owner,
                email="batch@example.com",
                normalized_email="batch@example.com",
                password_hash=hash_password("Strong-Password-Number-42"),
                display_name="Batch Test",
            )
            db.add(user)
            db.flush()
            stored_files: list[StoredFile] = []
            for filename, content in candidates.items():
                path = settings.temp_directory / f"{uuid.uuid4()}.upload"
                path.write_text(content, encoding="utf-8")
                staged = StagedFile(
                    path,
                    text_hash(content),
                    path.stat().st_size,
                    filename,
                    "text/plain",
                )
                key = storage.commit(staged, owner)
                keys.append(key)
                stored_files.append(
                    StoredFile(
                        user_id=owner,
                        storage_key=key,
                        file_sha256=staged.sha256,
                        file_size=staged.size,
                        mime_type=staged.mime_type,
                        sanitized_filename=filename,
                    )
                )
            job = RankingJob(
                user_id=owner,
                baseline_text=role,
                baseline_sha256=text_hash(role),
                total_files=len(stored_files),
            )
            db.add_all([*stored_files, job])
            db.flush()
            db.add_all(
                JobDocument(user_id=owner, job_id=job.id, stored_file_id=item.id)
                for item in stored_files
            )
            db.commit()
            job_id = job.id

        worker_id = uuid.uuid4()
        reranker = RecordingReranker()
        with get_sync_session() as db:
            assert claim_next_job(db, worker_id) == job_id
        with get_sync_session() as db:
            JobProcessor(settings, reranker, worker_id).process(db, job_id)
        assert [len(batch) for batch in reranker.batches] == [2, 1]
        assert [pair[1] for batch in reranker.batches for pair in batch] == list(
            candidates.values()
        )
        with get_sync_session() as db:
            documents = db.query(JobDocument).filter_by(job_id=job_id).all()
            scores = {
                item.stored_file.sanitized_filename: item.ranking_result.final_relevance_score
                for item in documents
                if item.ranking_result is not None
            }
            ranks = {item.stored_file.sanitized_filename: item.rank for item in documents}
        assert scores == {"one.txt": 1.0, "two.txt": 2.0, "three.txt": 3.0}
        assert ranks == {"one.txt": 3, "two.txt": 2, "three.txt": 1}
    finally:
        for key in keys:
            storage.delete(key)
