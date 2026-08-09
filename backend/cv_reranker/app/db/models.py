from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
IP_TYPE = String(45).with_variant(INET, "postgresql")

JOB_STATUSES = (
    "queued",
    "processing",
    "completed",
    "completed_with_errors",
    "failed",
    "cancellation_requested",
    "cancelled",
)
DOCUMENT_STATUSES = (
    "pending",
    "stored",
    "extracting",
    "parsed",
    "chunking",
    "ready",
    "ranking",
    "completed",
    "failed",
    "cancelled",
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[RankingJob]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    parent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("auth_sessions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(IP_TYPE)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_token_family_id", "token_family_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )


class StoredFile(Base):
    __tablename__ = "stored_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    storage_version: Mapped[str] = mapped_column(String(32), default="local-v1", nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sanitized_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "file_sha256", "storage_version", name="uq_stored_file_cache"),
        CheckConstraint("file_size > 0", name="ck_stored_file_nonempty"),
    )


class RankingJob(TimestampMixin, Base):
    __tablename__ = "ranking_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    baseline_text: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    baseline_warnings: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_pairs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_pairs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(512))
    model_id: Mapped[str | None] = mapped_column(String(255))
    model_backend: Mapped[str | None] = mapped_column(String(32))
    model_version: Mapped[str | None] = mapped_column(String(128))
    processing_summary: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="jobs")
    documents: Mapped[list[JobDocument]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobDocument.created_at"
    )

    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES}", name="ck_ranking_job_status"),
        Index("ix_ranking_jobs_user_created", "user_id", "created_at"),
        Index("ix_ranking_jobs_user_status", "user_id", "status"),
        Index("ix_ranking_jobs_queue", "status", "available_at", "created_at"),
        Index(
            "ix_ranking_jobs_queued_partial",
            "available_at",
            "created_at",
            postgresql_where=text("status = 'queued'"),
        ),
        Index("ix_ranking_jobs_heartbeat", "status", "heartbeat_at"),
    )


class DocumentContent(Base):
    __tablename__ = "document_contents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    extraction_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    warnings: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="content", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "file_sha256",
            "extractor_version",
            "normalization_version",
            name="uq_document_content_cache",
        ),
        Index("ix_document_contents_user_file", "user_id", "file_sha256"),
        Index("ix_document_contents_user_text", "user_id", "normalized_text_hash"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_content_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_contents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    content: Mapped[DocumentContent] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint(
            "document_content_id",
            "chunk_config_hash",
            "chunk_index",
            name="uq_document_chunk_cache",
        ),
        Index("ix_document_chunks_content", "document_content_id"),
    )


class RankingResult(Base):
    __tablename__ = "ranking_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_content_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_contents.id", ondelete="CASCADE"), nullable=False
    )
    ranking_cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    backend: Mapped[str] = mapped_column(String(32), nullable=False)
    final_relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    matching_excerpts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "ranking_cache_key", name="uq_ranking_result_cache"),
        Index("ix_ranking_results_user_cache", "user_id", "ranking_cache_key"),
    )


class JobDocument(Base):
    __tablename__ = "job_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ranking_jobs.id", ondelete="CASCADE"), nullable=False
    )
    stored_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    document_content_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_contents.id", ondelete="SET NULL")
    )
    ranking_result_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ranking_results.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), default="stored", nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(512))
    warnings: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    job: Mapped[RankingJob] = relationship(back_populates="documents")
    stored_file: Mapped[StoredFile] = relationship()
    content: Mapped[DocumentContent | None] = relationship()
    ranking_result: Mapped[RankingResult | None] = relationship()

    __table_args__ = (
        CheckConstraint(f"status IN {DOCUMENT_STATUSES}", name="ck_job_document_status"),
        UniqueConstraint("job_id", "stored_file_id", name="uq_job_document_file"),
        Index("ix_job_documents_user_job", "user_id", "job_id"),
        Index("ix_job_documents_job", "job_id"),
        Index("ix_job_documents_stored_file", "stored_file_id"),
    )


class ChunkScore(Base):
    __tablename__ = "chunk_scores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ranking_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ranking_results.id", ondelete="CASCADE"), nullable=False
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    raw_relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_matching_excerpt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "ranking_result_id", "document_chunk_id", name="uq_chunk_score_result_chunk"
        ),
    )


class WorkerInstance(Base):
    __tablename__ = "worker_instances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_name: Mapped[str] = mapped_column(String(160), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    backend: Mapped[str] = mapped_column(String(32), nullable=False)
    model_loaded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (Index("ix_worker_instances_heartbeat", "heartbeat_at"),)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
