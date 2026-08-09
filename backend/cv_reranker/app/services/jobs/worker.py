from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.db.models import (
    ChunkScore,
    DocumentChunk,
    DocumentContent,
    JobDocument,
    RankingJob,
    RankingResult,
)
from app.services.document_extraction.extractors import (
    EXTRACTOR_VERSION,
    ExtractionError,
    extract_document,
)
from app.services.document_storage.local import LocalDocumentStorage
from app.services.ranking.cache import ranking_cache_key
from app.services.ranking.reranker import Reranker, aggregate_scores
from app.services.text_processing.chunking import chunk_config_hash, chunk_text
from app.services.text_processing.normalization import (
    NORMALIZATION_VERSION,
    normalize_text,
    text_hash,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def claim_next_job(db: Session, worker_id: uuid.UUID) -> uuid.UUID | None:
    job = db.scalar(
        select(RankingJob)
        .where(RankingJob.status == "queued", RankingJob.available_at <= utc_now())
        .order_by(RankingJob.available_at, RankingJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        db.rollback()
        return None
    now = utc_now()
    job.status = "processing"
    job.current_stage = "starting"
    job.worker_id = worker_id
    job.locked_at = now
    job.heartbeat_at = now
    job.started_at = job.started_at or now
    job.attempt_count += 1
    db.commit()
    return job.id


def recover_stale_jobs(db: Session, settings: Settings) -> int:
    cutoff = utc_now() - timedelta(minutes=settings.job_stale_after_minutes)
    jobs = db.scalars(
        select(RankingJob)
        .where(
            RankingJob.status.in_(("processing", "cancellation_requested")),
            RankingJob.heartbeat_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in jobs:
        job.worker_id = None
        job.locked_at = None
        job.heartbeat_at = None
        if job.status == "cancellation_requested":
            job.status = "cancelled"
            job.current_stage = "cancelled"
            job.completed_at = utc_now()
            for item in job.documents:
                if item.status not in ("completed", "failed"):
                    item.status = "cancelled"
        elif job.attempt_count >= settings.job_max_attempts:
            job.status = "failed"
            job.current_stage = "failed"
            job.error_code = "MAX_ATTEMPTS_EXCEEDED"
            job.error_message = "The job exceeded its retry limit."
            job.completed_at = utc_now()
        else:
            job.status = "queued"
            job.current_stage = "recovered"
            job.available_at = utc_now()
    db.commit()
    return len(jobs)


@dataclass
class PreparedDocument:
    item: JobDocument
    content: DocumentContent
    chunks: list[DocumentChunk]
    cache_key: str
    cached_result: RankingResult | None


class CancellationRequested(Exception):
    """Internal control flow used to stop work at a safe commit boundary."""


class JobProcessor:
    def __init__(self, settings: Settings, reranker: Reranker, worker_id: uuid.UUID) -> None:
        self.settings = settings
        self.reranker = reranker
        self.worker_id = worker_id
        self.storage = LocalDocumentStorage(settings)

    def process(self, db: Session, job_id: uuid.UUID) -> None:
        started = time.perf_counter()
        job = db.scalar(
            select(RankingJob)
            .where(RankingJob.id == job_id)
            .options(selectinload(RankingJob.documents).joinedload(JobDocument.stored_file))
        )
        if job is None or job.status != "processing":
            return
        job.processed_files = 0
        job.total_pairs = 0
        job.processed_pairs = 0
        job.completed_at = None
        job.error_code = None
        job.error_message = None
        job.model_id = self.reranker.model_id
        job.model_version = self.reranker.model_version
        job.model_backend = self.reranker.backend
        summary = {
            "submitted_files": job.total_files,
            "valid_files": 0,
            "failed_files": 0,
            "extraction_cache_hits": 0,
            "chunk_cache_hits": 0,
            "ranking_cache_hits": 0,
            "model_pairs_processed": 0,
            "inference_batches": 0,
            "duration_ms": 0,
        }
        prepared: list[PreparedDocument] = []

        for item in job.documents:
            if self._cancelled(db, job):
                self._cancel_remaining(db, job)
                return
            try:
                prepared.append(self._prepare_document(db, job, item, summary))
                summary["valid_files"] += 1
            except CancellationRequested:
                self._cancel_remaining(db, job)
                return
            except ExtractionError as error:
                self._fail_document(db, job, item, "EXTRACTION_FAILED", str(error))
                summary["failed_files"] += 1
            except Exception:
                self._fail_document(
                    db,
                    job,
                    item,
                    "PROCESSING_FAILED",
                    "The document could not be processed.",
                )
                summary["failed_files"] += 1

        uncached = [entry for entry in prepared if entry.cached_result is None]
        pair_metadata = [(entry, chunk) for entry in uncached for chunk in entry.chunks]
        job.total_pairs = len(pair_metadata)
        job.current_stage = "ranking"
        db.commit()

        score_map: dict[uuid.UUID, list[tuple[DocumentChunk, float]]] = {
            entry.item.id: [] for entry in uncached
        }
        baseline_for_model = self._baseline_for_model(job)
        try:
            for start in range(0, len(pair_metadata), self.settings.rerank_batch_size):
                if self._cancelled(db, job):
                    self._cancel_remaining(db, job)
                    return
                batch = pair_metadata[start : start + self.settings.rerank_batch_size]
                values = self.reranker.predict(
                    [(baseline_for_model, chunk.chunk_text) for _entry, chunk in batch],
                    self.settings.rerank_batch_size,
                )
                for (entry, chunk), score in zip(batch, values, strict=True):
                    score_map[entry.item.id].append((chunk, score))
                job.processed_pairs += len(values)
                summary["model_pairs_processed"] += len(values)
                summary["inference_batches"] += 1
                job.heartbeat_at = utc_now()
                db.commit()
        except Exception:
            for entry in uncached:
                self._fail_document(
                    db,
                    job,
                    entry.item,
                    "INFERENCE_FAILED",
                    "The ranking model could not score this document.",
                )
            summary["failed_files"] += len(uncached)
            summary["valid_files"] -= len(uncached)
            self._finish(db, job, prepared, summary, started)
            return

        for entry in prepared:
            if self._cancelled(db, job):
                self._cancel_remaining(db, job)
                return
            if entry.cached_result is not None:
                result = entry.cached_result
                result.last_accessed_at = utc_now()
            else:
                entry.item.status = "ranking"
                result = self._persist_result(
                    db,
                    job,
                    entry,
                    score_map[entry.item.id],
                )
            entry.item.ranking_result_id = result.id
            entry.item.ranking_result = result
            entry.item.status = "completed"
            entry.item.warnings = list(entry.content.warnings)
            job.processed_files += 1
            job.heartbeat_at = utc_now()
            db.commit()

        self._finish(db, job, prepared, summary, started)

    def _prepare_document(
        self,
        db: Session,
        job: RankingJob,
        item: JobDocument,
        summary: dict[str, int],
    ) -> PreparedDocument:
        content = db.scalar(
            select(DocumentContent).where(
                DocumentContent.user_id == job.user_id,
                DocumentContent.file_sha256 == item.stored_file.file_sha256,
                DocumentContent.extractor_version == EXTRACTOR_VERSION,
                DocumentContent.normalization_version == NORMALIZATION_VERSION,
            )
        )
        if content is None:
            item.status = "extracting"
            job.current_stage = "extracting"
            job.heartbeat_at = utc_now()
            db.commit()
            extracted = extract_document(
                self.storage.path(item.stored_file.storage_key), item.stored_file.mime_type
            )
            normalized = normalize_text(extracted.text)
            if not normalized:
                raise ExtractionError(
                    "No extractable text was found. The document may require OCR."
                )
            truncated = len(normalized) > self.settings.max_cv_characters
            if truncated:
                normalized = normalized[: self.settings.max_cv_characters]
            content_id = self._upsert(
                db,
                DocumentContent,
                {
                    "id": uuid.uuid4(),
                    "user_id": job.user_id,
                    "file_sha256": item.stored_file.file_sha256,
                    "raw_text": extracted.text[: self.settings.max_cv_characters],
                    "normalized_text": normalized,
                    "normalized_text_hash": text_hash(normalized),
                    "extractor_name": extracted.extractor,
                    "extractor_version": EXTRACTOR_VERSION,
                    "normalization_version": NORMALIZATION_VERSION,
                    "page_count": extracted.page_count,
                    "extraction_metadata": extracted.metadata,
                    "warnings": extracted.warnings,
                    "truncated": truncated,
                },
                ["user_id", "file_sha256", "extractor_version", "normalization_version"],
            )
            content = db.get(DocumentContent, content_id)
            if content is None:
                raise RuntimeError("Extracted content cache row was not found.")
        else:
            summary["extraction_cache_hits"] += 1
            content.last_accessed_at = utc_now()

        item.document_content_id = content.id
        if self._cancelled(db, job):
            raise CancellationRequested
        item.status = "chunking"
        job.current_stage = "chunking"
        db.commit()

        baseline_tokens, effective_size, effective_overlap = self._token_budget(job)
        del baseline_tokens
        config_hash = chunk_config_hash(
            effective_size,
            effective_overlap,
            self.reranker.model_id,
            self.reranker.model_version,
        )
        chunks = list(
            db.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_content_id == content.id,
                    DocumentChunk.chunk_config_hash == config_hash,
                )
                .order_by(DocumentChunk.chunk_index)
            ).all()
        )
        if chunks:
            summary["chunk_cache_hits"] += 1
        else:
            made = chunk_text(
                content.normalized_text,
                self.reranker.tokenizer,
                effective_size,
                effective_overlap,
            )
            if not made:
                raise ExtractionError("No rankable text was found in the document.")
            values = [
                {
                    "id": uuid.uuid4(),
                    "document_content_id": content.id,
                    "chunk_config_hash": config_hash,
                    "chunk_index": chunk.index,
                    "chunk_text": chunk.text,
                    "chunk_hash": chunk.sha256,
                    "token_count": chunk.token_count,
                }
                for chunk in made
            ]
            insert = self._insert_for(db, DocumentChunk).values(values)
            db.execute(
                insert.on_conflict_do_nothing(
                    index_elements=[
                        "document_content_id",
                        "chunk_config_hash",
                        "chunk_index",
                    ]
                )
            )
            db.flush()
            chunks = list(
                db.scalars(
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.document_content_id == content.id,
                        DocumentChunk.chunk_config_hash == config_hash,
                    )
                    .order_by(DocumentChunk.chunk_index)
                ).all()
            )

        cache_key = ranking_cache_key(
            job.baseline_sha256,
            content.normalized_text_hash,
            config_hash,
            self.reranker.model_id,
            self.reranker.model_version,
            self.reranker.backend,
            self.settings.top_chunks_for_score,
            self.settings.matching_excerpt_count,
        )
        result = db.scalar(
            select(RankingResult).where(
                RankingResult.user_id == job.user_id,
                RankingResult.ranking_cache_key == cache_key,
            )
        )
        if result is not None:
            summary["ranking_cache_hits"] += 1
        item.status = "ready"
        db.commit()
        return PreparedDocument(item, content, chunks, cache_key, result)

    def _persist_result(
        self,
        db: Session,
        job: RankingJob,
        entry: PreparedDocument,
        scored_chunks: list[tuple[DocumentChunk, float]],
    ) -> RankingResult:
        scores = [score for _chunk, score in scored_chunks]
        top_indexes = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[
            : self.settings.matching_excerpt_count
        ]
        excerpts = [
            {
                "text": scored_chunks[index][0].chunk_text,
                "score": scores[index],
                "chunk_index": scored_chunks[index][0].chunk_index,
            }
            for index in top_indexes
        ]
        result_id = self._upsert(
            db,
            RankingResult,
            {
                "id": uuid.uuid4(),
                "user_id": job.user_id,
                "document_content_id": entry.content.id,
                "ranking_cache_key": entry.cache_key,
                "baseline_sha256": job.baseline_sha256,
                "model_id": self.reranker.model_id,
                "model_version": self.reranker.model_version,
                "backend": self.reranker.backend,
                "final_relevance_score": aggregate_scores(
                    scores, self.settings.top_chunks_for_score
                ),
                "matching_excerpts": excerpts,
            },
            ["user_id", "ranking_cache_key"],
        )
        result = db.get(RankingResult, result_id)
        if result is None:
            raise RuntimeError("Ranking result cache row was not found.")
        score_values = [
            {
                "id": uuid.uuid4(),
                "user_id": job.user_id,
                "ranking_result_id": result.id,
                "document_chunk_id": chunk.id,
                "raw_relevance_score": score,
                "is_matching_excerpt": index in top_indexes,
            }
            for index, (chunk, score) in enumerate(scored_chunks)
        ]
        if score_values:
            insert = self._insert_for(db, ChunkScore).values(score_values)
            db.execute(
                insert.on_conflict_do_nothing(
                    index_elements=["ranking_result_id", "document_chunk_id"]
                )
            )
            db.flush()
        return result

    def _upsert(
        self,
        db: Session,
        model: Any,
        values: dict[str, Any],
        conflict_columns: list[str],
    ) -> uuid.UUID:
        insert = self._insert_for(db, model).values(**values)
        row_id = db.scalar(
            insert.on_conflict_do_nothing(index_elements=conflict_columns).returning(model.id)
        )
        if row_id is not None:
            return uuid.UUID(str(row_id))
        filters = [getattr(model, key) == values[key] for key in conflict_columns]
        existing_id = db.scalar(select(model.id).where(*filters))
        if existing_id is None:
            raise RuntimeError("Concurrent cache insert could not be resolved.")
        return uuid.UUID(str(existing_id))

    @staticmethod
    def _insert_for(db: Session, model: Any) -> Any:
        return (
            pg_insert(model)
            if db.bind and db.bind.dialect.name == "postgresql"
            else sqlite_insert(model)
        )

    def _token_budget(self, job: RankingJob) -> tuple[list[int], int, int]:
        all_baseline_tokens = self.reranker.tokenizer.encode(
            job.baseline_text, add_special_tokens=False
        )
        baseline_tokens = all_baseline_tokens[: self.settings.max_baseline_tokens]
        if len(all_baseline_tokens) > len(baseline_tokens):
            job.baseline_truncated = True
            warning = "Role profile was truncated to the configured token limit."
            if warning not in job.baseline_warnings:
                job.baseline_warnings = [*job.baseline_warnings, warning]
        configured_limit = int(getattr(self.reranker.tokenizer, "model_max_length", 512))
        model_limit = configured_limit if configured_limit < 100_000 else 512
        effective_size = min(
            self.settings.chunk_token_size,
            model_limit - len(baseline_tokens) - 3,
        )
        if effective_size < 32:
            raise ExtractionError("The role profile leaves no usable model input for CV text.")
        return (
            baseline_tokens,
            effective_size,
            min(self.settings.chunk_token_overlap, effective_size - 1),
        )

    def _baseline_for_model(self, job: RankingJob) -> str:
        baseline_tokens, _size, _overlap = self._token_budget(job)
        return str(self.reranker.tokenizer.decode(baseline_tokens, skip_special_tokens=True))

    def _fail_document(
        self,
        db: Session,
        job: RankingJob,
        item: JobDocument,
        code: str,
        message: str,
    ) -> None:
        if item.status not in ("failed", "completed"):
            job.processed_files += 1
        item.status = "failed"
        item.error_code = code
        item.error_message = message[:512]
        db.commit()

    def _finish(
        self,
        db: Session,
        job: RankingJob,
        prepared: list[PreparedDocument],
        summary: dict[str, int],
        started: float,
    ) -> None:
        completed = [entry.item for entry in prepared if entry.item.status == "completed"]
        completed.sort(
            key=lambda item: (
                -(
                    item.ranking_result.final_relevance_score
                    if item.ranking_result
                    else float("-inf")
                ),
                item.stored_file.sanitized_filename.casefold(),
                str(item.id),
            )
        )
        for rank, item in enumerate(completed, 1):
            item.rank = rank
        failures = sum(item.status == "failed" for item in job.documents)
        job.status = "completed_with_errors" if failures else "completed"
        job.current_stage = job.status
        job.completed_at = utc_now()
        job.heartbeat_at = utc_now()
        summary["failed_files"] = failures
        summary["valid_files"] = len(completed)
        summary["duration_ms"] = round((time.perf_counter() - started) * 1000)
        job.processing_summary = summary
        db.commit()

    def _cancelled(self, db: Session, job: RankingJob) -> bool:
        db.refresh(job, attribute_names=["status"])
        cancellation_requested = job.status == "cancellation_requested"
        db.commit()
        return cancellation_requested

    def _cancel_remaining(self, db: Session, job: RankingJob) -> None:
        for item in job.documents:
            if item.status not in ("completed", "failed"):
                item.status = "cancelled"
        job.status = "cancelled"
        job.current_stage = "cancelled"
        job.completed_at = utc_now()
        db.commit()
