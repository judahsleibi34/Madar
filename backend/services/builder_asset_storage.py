from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock

from database import service_supabase


logger = logging.getLogger(__name__)

BUILDER_ASSET_BUCKET = os.getenv("BUILDER_ASSET_BUCKET", "builder-assets").strip() or "builder-assets"

_bucket_ready = False
_bucket_lock = Lock()


class BuilderAssetStorageError(RuntimeError):
    pass


def ensure_builder_asset_bucket(*, client=None) -> None:
    global _bucket_ready

    if _bucket_ready:
        return

    storage = (client or service_supabase).storage
    with _bucket_lock:
        if _bucket_ready:
            return

        try:
            storage.get_bucket(BUILDER_ASSET_BUCKET)
        except Exception:
            try:
                storage.create_bucket(
                    BUILDER_ASSET_BUCKET,
                    options={"public": False},
                )
            except Exception as error:
                # Another worker may have created the bucket between the two calls.
                try:
                    storage.get_bucket(BUILDER_ASSET_BUCKET)
                except Exception as verification_error:
                    logger.error(
                        "builder.asset_bucket_unavailable",
                        extra={"error_type": type(error).__name__},
                    )
                    raise BuilderAssetStorageError("builder_asset_bucket_unavailable") from verification_error

        _bucket_ready = True


def store_builder_asset(
    *,
    storage_key: str,
    content: bytes | None = None,
    source_path: Path | None = None,
    content_type: str,
    client=None,
) -> None:
    database_client = client or service_supabase
    ensure_builder_asset_bucket(client=database_client)

    try:
        upload_source = source_path if source_path is not None else content
        if upload_source is None:
            raise ValueError("builder_asset_content_required")
        database_client.storage.from_(BUILDER_ASSET_BUCKET).upload(
            path=storage_key,
            file=upload_source,
            file_options={
                "content-type": content_type,
                "cache-control": "31536000",
                "upsert": "false",
            },
        )
    except Exception as error:
        logger.error(
            "builder.asset_durable_write_failed",
            extra={"storage_key": storage_key, "error_type": type(error).__name__},
        )
        raise BuilderAssetStorageError("builder_asset_durable_write_failed") from error


def load_builder_asset(*, storage_key: str, client=None) -> bytes:
    database_client = client or service_supabase
    ensure_builder_asset_bucket(client=database_client)

    try:
        content = database_client.storage.from_(BUILDER_ASSET_BUCKET).download(storage_key)
    except Exception as error:
        raise FileNotFoundError(storage_key) from error

    if not isinstance(content, bytes) or not content:
        raise FileNotFoundError(storage_key)

    return content


def delete_builder_asset(*, storage_key: str, client=None) -> None:
    database_client = client or service_supabase
    ensure_builder_asset_bucket(client=database_client)
    database_client.storage.from_(BUILDER_ASSET_BUCKET).remove([storage_key])
