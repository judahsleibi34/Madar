from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import not_found
from app.db.models import JobDocument, RankingJob


async def owned_job(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> RankingJob:
    job = await db.scalar(
        select(RankingJob)
        .where(RankingJob.id == job_id, RankingJob.user_id == user_id)
        .options(
            selectinload(RankingJob.documents).selectinload(JobDocument.stored_file),
            selectinload(RankingJob.documents).selectinload(JobDocument.ranking_result),
            selectinload(RankingJob.documents).selectinload(JobDocument.content),
        )
    )
    if job is None:
        raise not_found()
    return job


async def owned_document(
    db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID, document_id: uuid.UUID
) -> JobDocument:
    document = await db.scalar(
        select(JobDocument)
        .where(
            JobDocument.id == document_id,
            JobDocument.job_id == job_id,
            JobDocument.user_id == user_id,
        )
        .options(
            selectinload(JobDocument.stored_file),
            selectinload(JobDocument.content),
            selectinload(JobDocument.ranking_result),
        )
    )
    if document is None:
        raise not_found()
    return document
