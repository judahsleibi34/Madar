from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

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


def create_builder_asset_signed_url(
    *, storage_key: str, expires_in: int = 60, client=None
) -> str:
    database_client = client or service_supabase
    ensure_builder_asset_bucket(client=database_client)
    try:
        result = database_client.storage.from_(BUILDER_ASSET_BUCKET).create_signed_url(
            storage_key,
            max(15, min(int(expires_in), 300)),
        )
        if isinstance(result, dict):
            signed_url = result.get("signedURL") or result.get("signedUrl") or result.get("signed_url")
        else:
            signed_url = getattr(result, "signed_url", None) or getattr(result, "signedURL", None)
        signed_url = str(signed_url or "").strip()
        expected_url = str(os.getenv("SUPABASE_URL") or "").strip()
        signed = urlsplit(signed_url)
        expected = urlsplit(expected_url)
        if (
            not signed_url
            or signed.scheme not in {"http", "https"}
            or not signed.netloc
            or signed.username
            or signed.password
            or signed.fragment
            or not expected.netloc
            or signed.scheme != expected.scheme
            or signed.netloc != expected.netloc
        ):
            raise ValueError("builder_asset_signed_url_invalid")
        return signed_url
    except Exception as error:
        logger.error(
            "builder.asset_signed_url_failed",
            extra={"storage_key": storage_key, "error_type": type(error).__name__},
        )
        raise BuilderAssetStorageError("builder_asset_signed_url_failed") from error


def download_builder_asset(*, storage_key: str, client=None) -> bytes:
    database_client = client or service_supabase
    ensure_builder_asset_bucket(client=database_client)
    try:
        content = database_client.storage.from_(BUILDER_ASSET_BUCKET).download(storage_key)
        if not isinstance(content, bytes) or not content:
            raise ValueError("builder_asset_download_empty")
        return content
    except Exception as error:
        logger.error(
            "builder.asset_download_failed",
            extra={"storage_key": storage_key, "error_type": type(error).__name__},
        )
        raise BuilderAssetStorageError("builder_asset_download_failed") from error


def delete_builder_asset(*, storage_key: str, client=None) -> None:
    database_client = client or service_supabase
    ensure_builder_asset_bucket(client=database_client)
    database_client.storage.from_(BUILDER_ASSET_BUCKET).remove([storage_key])
