from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.models import (
    AuthSession,
    DocumentContent,
    JobDocument,
    RankingJob,
    RankingResult,
    StoredFile,
)
from app.db.session import get_sync_session
from app.services.document_storage.local import LocalDocumentStorage

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    storage = LocalDocumentStorage(settings)
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=settings.cache_retention_days)
    counts = {"jobs": 0, "sessions": 0, "results": 0, "contents": 0, "files": 0}

    with get_sync_session() as db:
        expired_jobs = (
            select(RankingJob)
            .where(
                RankingJob.expires_at.is_not(None),
                RankingJob.expires_at < now,
                RankingJob.status.not_in(("processing", "cancellation_requested")),
            )
            .limit(settings.cleanup_batch_size)
        )
        for job in db.scalars(expired_jobs).all():
            db.delete(job)
            counts["jobs"] += 1
        db.flush()

        expired_sessions = (
            select(AuthSession)
            .where(
                or_(
                    AuthSession.expires_at < now,
                    AuthSession.revoked_at.is_not(None),
                )
            )
            .limit(settings.cleanup_batch_size)
        )
        for session in db.scalars(expired_sessions).all():
            db.delete(session)
            counts["sessions"] += 1

        referenced_results = select(JobDocument.ranking_result_id).where(
            JobDocument.ranking_result_id.is_not(None)
        )
        old_results = (
            select(RankingResult)
            .where(
                func.coalesce(RankingResult.last_accessed_at, RankingResult.created_at) < cutoff,
                ~RankingResult.id.in_(referenced_results),
            )
            .limit(settings.cleanup_batch_size)
        )
        for result in db.scalars(old_results).all():
            db.delete(result)
            counts["results"] += 1

        referenced_content = select(JobDocument.document_content_id).where(
            JobDocument.document_content_id.is_not(None)
        )
        old_content = (
            select(DocumentContent)
            .where(
                func.coalesce(DocumentContent.last_accessed_at, DocumentContent.created_at)
                < cutoff,
                ~DocumentContent.id.in_(referenced_content),
            )
            .limit(settings.cleanup_batch_size)
        )
        for content in db.scalars(old_content).all():
            db.delete(content)
            counts["contents"] += 1
        db.flush()

        unreferenced_files = (
            select(StoredFile)
            .where(~StoredFile.id.in_(select(JobDocument.stored_file_id)))
            .limit(settings.cleanup_batch_size)
        )
        for item in db.scalars(unreferenced_files).all():
            storage.delete(item.storage_key)
            db.delete(item)
            counts["files"] += 1
        db.commit()

    logger.info("cleanup_completed", extra={"event": "cleanup_completed", **counts})


if __name__ == "__main__":
    main()
