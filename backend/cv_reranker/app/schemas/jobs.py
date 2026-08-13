from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobCreated(BaseModel):
    job_id: uuid.UUID
    status: str
    file_count: int
    created_at: datetime
    status_url: str


class JobListItem(BaseModel):
    job_id: uuid.UUID
    status: str
    file_count: int
    created_at: datetime
    completed_at: datetime | None


class JobListResponse(BaseModel):
    items: list[JobListItem]
    total: int
    limit: int
    offset: int


class Progress(BaseModel):
    stage: str
    total_files: int
    processed_files: int
    total_pairs: int
    processed_pairs: int
    percent: float


class ModelInfo(BaseModel):
    id: str | None
    backend: str | None
    version: str | None


class BaselineInfo(BaseModel):
    truncated: bool
    warnings: list[str]


class RankedCandidate(BaseModel):
    candidate_id: uuid.UUID
    filename: str
    rank: int | None
    score: float
    parsed_text_url: str
    download_url: str
    matching_excerpts: list[dict[str, object]]
    warnings: list[str]


class FileError(BaseModel):
    document_id: uuid.UUID
    filename: str
    error_code: str
    message: str


class JobDetail(BaseModel):
    job_id: uuid.UUID
    status: str
    progress: Progress
    model: ModelInfo
    baseline: BaselineInfo
    results: list[RankedCandidate]
    file_errors: list[FileError]
    processing_summary: dict[str, object]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    mime_type: str
    file_size: int
    status: str
    rank: int | None
    score: float | None
    has_original: bool
    has_parsed_text: bool
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]


class ParsedDocument(BaseModel):
    document_id: uuid.UUID
    filename: str
    parsed_text: str
    text_hash: str
    extractor: dict[str, str]
    warnings: list[str]
    truncated: bool
    created_at: datetime
