from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "cv-reranker"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://cv_ranker:change_me@localhost:5432/cv_ranker"
    worker_database_url: str = "postgresql+psycopg://cv_ranker:change_me@localhost:5432/cv_ranker"
    db_pool_size: int = Field(5, ge=1, le=50)
    db_max_overflow: int = Field(5, ge=0, le=100)
    db_pool_timeout_seconds: int = Field(30, ge=1)
    db_pool_recycle_seconds: int = Field(1800, ge=60)

    jwt_secret_key: str = "replace-with-at-least-32-random-characters"
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "cv-reranker"
    jwt_audience: str = "cv-reranker-api"
    access_token_expire_minutes: int = Field(15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(30, ge=1, le=365)
    password_min_length: int = Field(12, ge=10, le=128)
    refresh_token_cookie: bool = False
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    upload_directory: Path = Path("./data/uploads")
    temp_directory: Path = Path("./data/tmp")
    model_cache_directory: Path = Path("./data/models")

    rerank_model_id: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    rerank_model_version: str = "default"
    rerank_backend: Literal["onnx", "pytorch"] = "onnx"
    rerank_batch_size: int = Field(8, ge=1, le=64)
    top_chunks_for_score: int = Field(3, ge=1, le=20)
    matching_excerpt_count: int = Field(3, ge=0, le=20)

    max_concurrent_jobs: int = Field(1, ge=1, le=8)
    worker_poll_interval_seconds: float = Field(2.0, ge=0.1, le=60)
    worker_heartbeat_interval_seconds: int = Field(15, ge=2, le=300)
    job_stale_after_minutes: int = Field(30, ge=1)
    job_max_attempts: int = Field(3, ge=1, le=20)

    max_files_per_job: int = Field(50, ge=1, le=500)
    max_file_size_mb: int = Field(10, ge=1, le=100)
    max_total_upload_mb: int = Field(200, ge=1, le=1000)
    max_baseline_characters: int = Field(30000, ge=100, le=1_000_000)
    max_cv_characters: int = Field(200000, ge=1000, le=2_000_000)

    chunk_token_size: int = Field(384, ge=32, le=2048)
    chunk_token_overlap: int = Field(48, ge=0, le=1024)
    max_baseline_tokens: int = Field(128, ge=16, le=1024)

    cache_retention_days: int = Field(30, ge=0)
    cleanup_batch_size: int = Field(500, ge=1, le=10000)
    cache_access_update_interval_minutes: int = Field(60, ge=1)
    default_job_retention_days: int = Field(0, ge=0)
    max_active_jobs_per_user: int = Field(3, ge=1, le=100)
    max_stored_jobs_per_user: int = Field(100, ge=1, le=10_000)

    rate_limit_enabled: bool = True
    registration_rate_limit: int = Field(10, ge=1)
    login_rate_limit: int = Field(20, ge=1)
    refresh_rate_limit: int = Field(30, ge=1)
    job_create_rate_limit: int = Field(10, ge=1)
    rate_limit_window_seconds: int = Field(300, ge=1)

    omp_num_threads: int = Field(2, ge=1, le=64)
    mkl_num_threads: int = Field(2, ge=1, le=64)
    torch_num_threads: int = Field(2, ge=1, le=64)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        clean = value.rstrip("/")
        if not clean.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        return clean

    @model_validator(mode="after")
    def validate_security_and_limits(self) -> Settings:
        if self.chunk_token_overlap >= self.chunk_token_size:
            raise ValueError("CHUNK_TOKEN_OVERLAP must be smaller than CHUNK_TOKEN_SIZE")
        if self.max_total_upload_mb < self.max_file_size_mb:
            raise ValueError("MAX_TOTAL_UPLOAD_MB must be at least MAX_FILE_SIZE_MB")
        if not self.database_url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError("DATABASE_URL must use asyncpg (or aiosqlite in tests)")
        if not self.worker_database_url.startswith(("postgresql+psycopg://", "sqlite://")):
            raise ValueError("WORKER_DATABASE_URL must use psycopg (or sqlite in tests)")
        if self.app_env != "test" and not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("PostgreSQL is required outside tests")
        if self.app_env == "production":
            unsafe_secrets = {"", "replace-with-at-least-32-random-characters", "change_me"}
            if self.jwt_secret_key.strip() in unsafe_secrets or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "Production requires a non-default JWT secret of at least 32 characters"
                )
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError("Production CORS origins must be explicit")
            if self.refresh_token_cookie and not self.cookie_secure:
                raise ValueError("Secure cookies are required in production")
        return self

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_total_upload_bytes(self) -> int:
        return self.max_total_upload_mb * 1024 * 1024

    def ensure_storage(self) -> None:
        for directory in (self.upload_directory, self.temp_directory, self.model_cache_directory):
            if self.app_env == "production" and not directory.exists():
                raise RuntimeError(f"Required storage directory is missing: {directory}")
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write-probe"
            probe.write_bytes(b"")
            probe.unlink()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
