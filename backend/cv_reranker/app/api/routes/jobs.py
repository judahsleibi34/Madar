from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser, DatabaseSession, SettingsDependency
from app.core.errors import ApiError
from app.db.models import (
    DocumentContent,
    JobDocument,
    RankingJob,
    RankingResult,
    StoredFile,
)
from app.schemas.jobs import (
    BaselineInfo,
    DocumentItem,
    DocumentListResponse,
    FileError,
    JobCreated,
    JobDetail,
    JobListItem,
    JobListResponse,
    ModelInfo,
    ParsedDocument,
    Progress,
    RankedCandidate,
)
from app.services.document_storage.local import LocalDocumentStorage, StagedFile
from app.services.jobs.queries import owned_document, owned_job
from app.services.rate_limit import DatabaseRateLimiter
from app.services.text_processing.normalization import normalize_text, text_hash

router = APIRouter(prefix="/ranking-jobs", tags=["ranking"])


def _detail(job: RankingJob, prefix: str) -> JobDetail:
    results: list[RankedCandidate] = []
    errors: list[FileError] = []
    for item in job.documents:
        if item.ranking_result is not None:
            results.append(
                RankedCandidate(
                    candidate_id=item.id,
                    filename=item.stored_file.sanitized_filename,
                    rank=item.rank,
                    score=item.ranking_result.final_relevance_score,
                    parsed_text_url=f"{prefix}/ranking-jobs/{job.id}/documents/{item.id}/parsed",
                    download_url=f"{prefix}/ranking-jobs/{job.id}/documents/{item.id}/original",
                    matching_excerpts=list(item.ranking_result.matching_excerpts),
                    warnings=list(item.warnings),
                )
            )
        if item.error_code and item.error_message:
            errors.append(
                FileError(
                    document_id=item.id,
                    filename=item.stored_file.sanitized_filename,
                    error_code=item.error_code,
                    message=item.error_message,
                )
            )
    results.sort(key=lambda item: (item.rank is None, item.rank or 0, item.filename))
    denominator = job.total_pairs if job.total_pairs else job.total_files
    numerator = job.processed_pairs if job.total_pairs else job.processed_files
    percent = min(100.0, round((numerator / denominator * 100), 2)) if denominator else 0.0
    if job.status in ("completed", "completed_with_errors", "failed", "cancelled"):
        percent = 100.0
    return JobDetail(
        job_id=job.id,
        status=job.status,
        progress=Progress(
            stage=job.current_stage,
            total_files=job.total_files,
            processed_files=job.processed_files,
            total_pairs=job.total_pairs,
            processed_pairs=job.processed_pairs,
            percent=percent,
        ),
        model=ModelInfo(id=job.model_id, backend=job.model_backend, version=job.model_version),
        baseline=BaselineInfo(
            truncated=job.baseline_truncated,
            warnings=list(job.baseline_warnings),
        ),
        results=results,
        file_errors=errors,
        processing_summary=dict(job.processing_summary),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


async def _upsert_file(
    db: AsyncSession,
    storage: LocalDocumentStorage,
    staged: StagedFile,
    owner_id: uuid.UUID,
    committed_keys: list[str],
) -> StoredFile:
    existing = await db.scalar(
        select(StoredFile).where(
            StoredFile.user_id == owner_id,
            StoredFile.file_sha256 == staged.sha256,
            StoredFile.storage_version == "local-v1",
        )
    )
    if existing is not None:
        storage.discard(staged)
        return existing

    key = storage.commit(staged, owner_id)
    values = {
        "id": uuid.uuid4(),
        "user_id": owner_id,
        "storage_key": key,
        "storage_version": "local-v1",
        "file_sha256": staged.sha256,
        "file_size": staged.size,
        "mime_type": staged.mime_type,
        "sanitized_filename": staged.filename,
    }
    dialect = db.bind.dialect.name if db.bind is not None else ""
    insert = pg_insert(StoredFile) if dialect == "postgresql" else sqlite_insert(StoredFile)
    statement = (
        insert.values(**values)
        .on_conflict_do_nothing(index_elements=["user_id", "file_sha256", "storage_version"])
        .returning(StoredFile.id)
    )
    stored_id = (await db.execute(statement)).scalar_one_or_none()
    if stored_id is None:
        storage.delete(key)
        conflicting_file = await db.scalar(
            select(StoredFile).where(
                StoredFile.user_id == owner_id,
                StoredFile.file_sha256 == staged.sha256,
                StoredFile.storage_version == "local-v1",
            )
        )
        if conflicting_file is None:
            raise ApiError(409, "UPLOAD_CONFLICT", "The upload conflicted with another request.")
        return conflicting_file
    committed_keys.append(key)
    stored_file = await db.get(StoredFile, stored_id)
    if stored_file is None:
        raise RuntimeError("Inserted stored file was not found.")
    return stored_file


@router.post("", response_model=JobCreated, status_code=202)
async def create_job(
    user: CurrentUser,
    db: DatabaseSession,
    settings: SettingsDependency,
    baseline: str = Form(...),
    files: list[UploadFile] = File(...),
) -> JobCreated:
    if settings.rate_limit_enabled:
        await DatabaseRateLimiter().enforce(
            db,
            action="create-job",
            identity=str(user.id),
            limit=settings.job_create_rate_limit,
            window_seconds=settings.rate_limit_window_seconds,
        )
    if not files or len(files) > settings.max_files_per_job:
        raise ApiError(
            422, "INVALID_FILE_COUNT", "The number of files is outside the allowed range."
        )
    active = await db.scalar(
        select(func.count())
        .select_from(RankingJob)
        .where(
            RankingJob.user_id == user.id,
            RankingJob.status.in_(("queued", "processing", "cancellation_requested")),
        )
    )
    if int(active or 0) >= settings.max_active_jobs_per_user:
        raise ApiError(
            409, "ACTIVE_JOB_LIMIT", "Finish or cancel an active job before creating another."
        )
    stored_count = await db.scalar(
        select(func.count()).select_from(RankingJob).where(RankingJob.user_id == user.id)
    )
    if int(stored_count or 0) >= settings.max_stored_jobs_per_user:
        raise ApiError(409, "STORED_JOB_LIMIT", "Delete an old job before creating another.")

    normalized = normalize_text(baseline)
    if not normalized:
        raise ApiError(422, "EMPTY_BASELINE", "A role profile is required.")
    warnings: list[str] = []
    truncated = len(normalized) > settings.max_baseline_characters
    if truncated:
        normalized = normalized[: settings.max_baseline_characters]
        warnings.append("Role profile was truncated to the configured character limit.")

    storage = LocalDocumentStorage(settings)
    staged: list[StagedFile] = []
    committed_keys: list[str] = []
    try:
        total = 0
        seen: set[str] = set()
        for upload in files:
            item = await storage.stage(upload)
            total += item.size
            if total > settings.max_total_upload_bytes:
                storage.discard(item)
                raise ApiError(
                    413, "BATCH_TOO_LARGE", "The upload batch exceeds the configured limit."
                )
            if item.sha256 in seen:
                storage.discard(item)
                raise ApiError(422, "DUPLICATE_FILE", "The same file was uploaded more than once.")
            seen.add(item.sha256)
            staged.append(item)

        job = RankingJob(
            user_id=user.id,
            baseline_text=normalized,
            baseline_sha256=text_hash(normalized),
            baseline_truncated=truncated,
            baseline_warnings=warnings,
            total_files=len(staged),
            expires_at=(
                datetime.now(UTC) + timedelta(days=settings.default_job_retention_days)
                if settings.default_job_retention_days
                else None
            ),
        )
        db.add(job)
        await db.flush()
        for item in staged:
            stored_file = await _upsert_file(db, storage, item, user.id, committed_keys)
            db.add(JobDocument(user_id=user.id, job_id=job.id, stored_file_id=stored_file.id))
        await db.commit()
        await db.refresh(job)
        return JobCreated(
            job_id=job.id,
            status=job.status,
            file_count=job.total_files,
            created_at=job.created_at,
            status_url=f"{settings.api_v1_prefix}/ranking-jobs/{job.id}",
        )
    except IntegrityError as error:
        await db.rollback()
        for key in committed_keys:
            storage.delete(key)
        raise ApiError(
            409, "UPLOAD_CONFLICT", "The upload conflicted with another request."
        ) from error
    except Exception:
        await db.rollback()
        for item in staged:
            storage.discard(item)
        for key in committed_keys:
            storage.delete(key)
        raise


@router.get("", response_model=JobListResponse)
async def list_jobs(
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: Literal["newest", "oldest"] = "newest",
) -> JobListResponse:
    filters = [RankingJob.user_id == user.id]
    if status:
        filters.append(RankingJob.status == status)
    if created_after:
        filters.append(RankingJob.created_at >= created_after)
    if created_before:
        filters.append(RankingJob.created_at <= created_before)
    total = await db.scalar(select(func.count()).select_from(RankingJob).where(*filters))
    order = RankingJob.created_at.desc() if sort == "newest" else RankingJob.created_at.asc()
    jobs = (
        await db.scalars(
            select(RankingJob).where(*filters).order_by(order).limit(limit).offset(offset)
        )
    ).all()
    return JobListResponse(
        items=[
            JobListItem(
                job_id=job.id,
                status=job.status,
                file_count=job.total_files,
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
            for job in jobs
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DatabaseSession,
    settings: SettingsDependency,
) -> JobDetail:
    return _detail(await owned_job(db, user.id, job_id), settings.api_v1_prefix)


@router.get("/{job_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    job_id: uuid.UUID, user: CurrentUser, db: DatabaseSession
) -> DocumentListResponse:
    job = await owned_job(db, user.id, job_id)
    return DocumentListResponse(
        items=[
            DocumentItem(
                document_id=item.id,
                filename=item.stored_file.sanitized_filename,
                mime_type=item.stored_file.mime_type,
                file_size=item.stored_file.file_size,
                status=item.status,
                rank=item.rank,
                score=(
                    item.ranking_result.final_relevance_score
                    if item.ranking_result is not None
                    else None
                ),
                has_original=True,
                has_parsed_text=item.content is not None,
                created_at=item.created_at,
            )
            for item in job.documents
        ]
    )


@router.get("/{job_id}/documents/{document_id}/parsed", response_model=ParsedDocument)
async def get_parsed(
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DatabaseSession,
) -> ParsedDocument:
    item = await owned_document(db, user.id, job_id, document_id)
    if item.content is None:
        raise ApiError(409, "DOCUMENT_NOT_PARSED", "The document has not been parsed yet.")
    return ParsedDocument(
        document_id=item.id,
        filename=item.stored_file.sanitized_filename,
        parsed_text=item.content.normalized_text,
        text_hash=item.content.normalized_text_hash,
        extractor={
            "name": item.content.extractor_name,
            "version": item.content.extractor_version,
        },
        warnings=list(item.content.warnings),
        truncated=item.content.truncated,
        created_at=item.content.created_at,
    )


@router.get("/{job_id}/documents/{document_id}/original")
async def get_original(
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DatabaseSession,
    settings: SettingsDependency,
) -> StreamingResponse:
    item = await owned_document(db, user.id, job_id, document_id)
    stream = LocalDocumentStorage(settings).open(item.stored_file.storage_key)
    download_name = Path(item.stored_file.sanitized_filename).name
    headers = {"Content-Disposition": f'attachment; filename="{download_name}"'}
    return StreamingResponse(stream, media_type=item.stored_file.mime_type, headers=headers)


@router.post("/{job_id}/cancel", response_model=JobDetail)
async def cancel_job(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DatabaseSession,
    settings: SettingsDependency,
) -> JobDetail:
    job = await owned_job(db, user.id, job_id)
    if job.status == "queued":
        job.status = "cancelled"
        job.current_stage = "cancelled"
        job.completed_at = datetime.now(UTC)
    elif job.status == "processing":
        job.status = "cancellation_requested"
        job.current_stage = "cancellation_requested"
    elif job.status not in ("cancelled", "completed", "completed_with_errors", "failed"):
        raise ApiError(
            409, "JOB_NOT_CANCELLABLE", "The job cannot be cancelled in its current state."
        )
    await db.commit()
    return _detail(await owned_job(db, user.id, job_id), settings.api_v1_prefix)


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DatabaseSession,
    settings: SettingsDependency,
) -> None:
    job = await owned_job(db, user.id, job_id)
    if job.status in ("processing", "cancellation_requested"):
        raise ApiError(409, "JOB_ACTIVE", "Cancel the job before deleting it.")

    result_ids = {item.ranking_result_id for item in job.documents if item.ranking_result_id}
    content_ids = {item.document_content_id for item in job.documents if item.document_content_id}
    file_ids = {item.stored_file_id for item in job.documents}
    await db.delete(job)
    await db.flush()

    for result_id in result_ids:
        references = await db.scalar(
            select(func.count())
            .select_from(JobDocument)
            .where(JobDocument.ranking_result_id == result_id)
        )
        if not references:
            result = await db.get(RankingResult, result_id)
            if result is not None:
                await db.delete(result)
    await db.flush()

    for content_id in content_ids:
        job_references = await db.scalar(
            select(func.count())
            .select_from(JobDocument)
            .where(JobDocument.document_content_id == content_id)
        )
        result_references = await db.scalar(
            select(func.count())
            .select_from(RankingResult)
            .where(RankingResult.document_content_id == content_id)
        )
        if not job_references and not result_references:
            content = await db.get(DocumentContent, content_id)
            if content is not None:
                await db.delete(content)
    await db.flush()

    storage = LocalDocumentStorage(settings)
    moved: list[tuple[Path, Path]] = []
    for file_id in file_ids:
        references = await db.scalar(
            select(func.count())
            .select_from(JobDocument)
            .where(JobDocument.stored_file_id == file_id)
        )
        if references:
            continue
        stored_file = await db.get(StoredFile, file_id)
        if stored_file is None:
            continue
        source = storage.path(stored_file.storage_key)
        if source.exists():
            trash = storage.temp / f"{uuid.uuid4()}.delete"
            os.replace(source, trash)
            moved.append((source, trash))
        await db.delete(stored_file)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        for source, trash in moved:
            if trash.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(trash, source)
        raise
    for _source, trash in moved:
        trash.unlink(missing_ok=True)
