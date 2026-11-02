"""Private, bounded Parquet cache for authorized immutable CSV versions."""
from __future__ import annotations
from services.account_work_fence import account_file_work

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from uuid import uuid4

from services.storage_quota_service import StorageSafetyError, ensure_disk_capacity
from services.upload_config import (
    assert_path_within_root,
    get_data_upload_dir,
    resolve_private_user_file_path,
    safe_scope_part,
)


CACHE_FORMAT_VERSION = 1
MIN_SOURCE_BYTES = 10 * 1024 * 1024
MAX_SOURCE_BYTES = 250_000_000
CONVERSION_SCRATCH_BYTES = 512 * 1024 * 1024
CONVERSION_TIMEOUT_SECONDS = 15.0
# Pinned DuckDB + Polars map about 2.89 GiB while resident use stays below the
# separately enforced 512 MiB ceiling on the verified 249.1 MB workload.
CONVERSION_ADDRESS_SPACE_BYTES = 4 * 1024 * 1024 * 1024
CONVERSION_RSS_BYTES = 512 * 1024 * 1024
MAX_CACHE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TENANT_CACHE_BYTES = 512 * 1024 * 1024
MAX_CACHE_ENTRIES = 128
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_CONCURRENT_CONVERSIONS = 1
_conversion_slots = threading.BoundedSemaphore(MAX_CONCURRENT_CONVERSIONS)
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_HASH = re.compile(r"[0-9a-f]{64}")
_CONFIG = {
    "format_version": CACHE_FORMAT_VERSION,
    "engine": "duckdb",
    "compression": "zstd",
    "row_group_size": 122_880,
    "csv": {"header": True, "sample_size": -1, "strict_mode": True},
}
CONFIG_HASH = hashlib.sha256(
    json.dumps(_CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class ParquetArtifact:
    path: Path
    sha256: str
    size_bytes: int
    row_count: int
    cache_hit: bool
    polars_compatible_columns: tuple[str, ...] = ()
    polars_numeric_columns: tuple[str, ...] = ()


def _enabled() -> bool:
    return os.getenv("PARQUET_CACHE_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _cache_root(storage_root: Path | None = None, *, create: bool = True) -> Path:
    root = (storage_root or get_data_upload_dir()) / ".parquet_cache"
    if root.is_symlink():
        raise PermissionError('cache root symlink refused')
    if create:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
    return root.resolve()


def _safe_uuid(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not _UUID.fullmatch(normalized):
        raise ValueError("invalid parquet cache identity")
    return normalized


def _safe_hash(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not _HASH.fullmatch(normalized):
        raise ValueError("invalid parquet cache hash")
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_dir(
    *, tenant_id: int, user_id: int, project_id: str, dataset_id: str, version_id: str,
    create: bool = True,
) -> Path:
    root = _cache_root()
    directory = root.joinpath(
        safe_scope_part("tenant", tenant_id),
        safe_scope_part("user", user_id),
        safe_scope_part("project", _safe_uuid(project_id)),
        safe_scope_part("dataset", _safe_uuid(dataset_id)),
        safe_scope_part("version", _safe_uuid(version_id)),
    )
    component = root
    for part in directory.relative_to(root).parts:
        component = component / part
        if component.is_symlink():
            raise PermissionError('cache scope directory symlink refused')
    assert_path_within_root(directory, root)
    if create:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
    return directory.resolve()


def _paths(directory: Path, source_hash: str) -> tuple[Path, Path, Path]:
    key = f"{_safe_hash(source_hash)}-{CONFIG_HASH}"
    return directory / f"{key}.parquet", directory / f"{key}.json", directory / ".conversion.lock"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(payload, output, sort_keys=True, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remove_pair(manifest: Path, artifact: Path) -> None:
    artifact.unlink(missing_ok=True)
    manifest.unlink(missing_ok=True)


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or path.stat().st_size > 32 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def cleanup_cache(*, now: float | None = None) -> dict[str, int]:
    """Bound cache growth; callers may run this repeatedly and concurrently."""
    root = _cache_root()
    cutoff = (time.time() if now is None else float(now)) - CACHE_TTL_SECONDS
    entries: list[tuple[float, int, Path, Path, str]] = []
    removed = 0
    for manifest in root.glob("tenant_*/user_*/project_*/dataset_*/version_*/*.json"):
        try:
            assert_path_within_root(manifest, root)
            artifact = manifest.with_suffix(".parquet")
            data = _read_manifest(manifest)
            if data is None or not artifact.is_file() or manifest.stat().st_mtime < cutoff:
                _remove_pair(manifest, artifact)
                removed += 1
                continue
            tenant_part = manifest.relative_to(root).parts[0]
            entries.append((manifest.stat().st_mtime, artifact.stat().st_size,
                            manifest, artifact, tenant_part))
        except OSError:
            continue
    known = {artifact.resolve() for _, _, _, artifact, _ in entries if artifact.exists()}
    for artifact in root.glob("tenant_*/user_*/project_*/dataset_*/version_*/*.parquet"):
        try:
            if artifact.resolve() not in known and artifact.stat().st_mtime < cutoff:
                artifact.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue

    tenant_bytes: dict[str, int] = {}
    total = 0
    kept = 0
    for _, size, manifest, artifact, tenant_part in sorted(entries, reverse=True):
        next_tenant = tenant_bytes.get(tenant_part, 0) + size
        if kept >= MAX_CACHE_ENTRIES or total + size > MAX_CACHE_BYTES \
                or next_tenant > MAX_TENANT_CACHE_BYTES:
            _remove_pair(manifest, artifact)
            removed += 1
            continue
        tenant_bytes[tenant_part] = next_tenant
        total += size
        kept += 1
    return {"removed": removed, "entries": kept, "bytes": total}


def _manifest_matches(
    data: dict[str, Any] | None, *, artifact: Path, tenant_id: int, user_id: int,
    project_id: str, dataset_id: str, version_id: str, source_name: str,
    source_hash: str, source_size: int, declared_rows: int | None,
) -> ParquetArtifact | None:
    if data is None:
        return None
    expected = {
        "format_version": CACHE_FORMAT_VERSION,
        "tenant_id": int(tenant_id), "user_id": int(user_id),
        "project_id": _safe_uuid(project_id), "dataset_id": _safe_uuid(dataset_id),
        "dataset_version_id": _safe_uuid(version_id), "source_filename": source_name,
        "source_sha256": _safe_hash(source_hash), "source_size_bytes": int(source_size),
        "config_sha256": CONFIG_HASH,
    }
    if any(data.get(key) != value for key, value in expected.items()):
        return None
    if not isinstance(data.get("polars_compatible_columns"), list) \
            or not isinstance(data.get("polars_numeric_columns"), list):
        return None
    try:
        size = int(data["parquet_size_bytes"])
        rows = int(data["row_count"])
        digest = _safe_hash(data["parquet_sha256"])
        if size <= 0 or rows < 0 or artifact.is_symlink() \
                or not artifact.is_file() or artifact.stat().st_size != size:
            return None
        if isinstance(declared_rows, int) and rows != declared_rows:
            return None
        if _sha256(artifact) != digest:
            return None
        compatible = tuple(
            str(value) for value in data.get("polars_compatible_columns", [])
            if isinstance(value, str)
        )
        numeric = tuple(
            str(value) for value in data.get("polars_numeric_columns", [])
            if isinstance(value, str)
        )
        os.utime(artifact.with_suffix(".json"), None)
        return ParquetArtifact(artifact, digest, size, rows, True, compatible, numeric)
    except (KeyError, TypeError, ValueError, OSError):
        return None


def _worker_limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (
        CONVERSION_ADDRESS_SPACE_BYTES, CONVERSION_ADDRESS_SPACE_BYTES,
    ))
    seconds = max(1, int(CONVERSION_TIMEOUT_SECONDS))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (
        MAX_TENANT_CACHE_BYTES, MAX_TENANT_CACHE_BYTES,
    ))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    os.umask(0o077)


def _resident_bytes(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return 0
    return 0


def _tree_bytes(root: Path) -> int:
    total = 0
    for item in root.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _convert(
    source: Path, target: Path, *, declared_rows: int | None,
) -> tuple[int, int, list[str], list[str], int, int]:
    with source.open("rb") as source_file, tempfile.TemporaryDirectory(
        prefix="madar-parquet-", dir=target.parent,
    ) as scratch_name:
        scratch = Path(scratch_name)
        result_path = scratch / "result.json"
        payload = json.dumps({
            "source_fd": source_file.fileno(), "output_path": str(target),
            "scratch_path": str(scratch), "declared_rows": declared_rows,
        }, separators=(",", ":")).encode("utf-8")
        worker = Path(__file__).with_name("parquet_conversion_worker.py")
        maximum_rss = maximum_scratch = 0
        process = None
        try:
            with result_path.open("wb") as output:
                process = subprocess.Popen(
                    [sys.executable, "-I", str(worker)], stdin=subprocess.PIPE,
                    stdout=output, stderr=subprocess.DEVNULL,
                    pass_fds=(source_file.fileno(),), cwd=scratch,
                    env={
                        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                        "POLARS_MAX_THREADS": "1", "TMPDIR": str(scratch),
                        "PYTHONHASHSEED": "0", "TZ": "UTC",
                    },
                    preexec_fn=_worker_limits,
                )
                assert process.stdin is not None
                process.stdin.write(payload)
                process.stdin.close()
                deadline = time.monotonic() + CONVERSION_TIMEOUT_SECONDS
                while process.poll() is None:
                    maximum_rss = max(maximum_rss, _resident_bytes(process.pid))
                    maximum_scratch = max(maximum_scratch, _tree_bytes(scratch))
                    output_size = target.stat().st_size if target.exists() else 0
                    if maximum_rss > CONVERSION_RSS_BYTES \
                            or maximum_scratch > CONVERSION_SCRATCH_BYTES \
                            or output_size > MAX_TENANT_CACHE_BYTES:
                        process.kill()
                        process.wait()
                        raise RuntimeError("parquet conversion resource limit exceeded")
                    if time.monotonic() >= deadline:
                        process.kill()
                        process.wait()
                        raise TimeoutError("parquet conversion deadline exceeded")
                    time.sleep(0.01)
                process.wait()
            if result_path.stat().st_size > 32 * 1024:
                raise RuntimeError("parquet conversion result limit exceeded")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if process.returncode != 0 or not result.get("ok"):
                raise RuntimeError("parquet conversion failed")
            return (
                int(result["size_bytes"]), int(result["row_count"]),
                [str(value) for value in result["polars_compatible_columns"]],
                [str(value) for value in result["polars_numeric_columns"]],
                maximum_rss, maximum_scratch,
            )
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()


def is_metric_compatible(artifact: ParquetArtifact, metric: dict[str, Any]) -> bool:
    operation = str(metric.get("operation") or "").lower()
    group = str(metric.get("group_column") or "")
    value = str(metric.get("value_column") or "")
    compatible = set(artifact.polars_compatible_columns)
    numeric = set(artifact.polars_numeric_columns)
    if operation == "date_aggregate":
        date_column = str(metric.get("date_column") or "")
        aggregation = str(metric.get("aggregation") or "count").lower()
        return bool(date_column and date_column in compatible) and (
            aggregation == "count" or (
                aggregation in {"sum", "mean", "min", "max"}
                and value in compatible and value in numeric
            )
        )
    if group and group not in compatible:
        return False
    if operation == "count" and not value:
        return True
    if not value or value not in compatible:
        return False
    if operation in {"sum", "mean", "min", "max"} and value not in numeric:
        return False
    return operation in {"count", "sum", "mean", "min", "max", "distinct_count"}


def get_existing(
    *, source_path: str, tenant_id: int, user_id: int, project_id: str,
    dataset_id: str, version_id: str, source_hash: str, source_size: int,
    declared_rows: int | None,
) -> ParquetArtifact | None:
    """Reuse a verified cache entry without triggering speculative conversion."""
    if not _enabled() or source_size < MIN_SOURCE_BYTES or source_size > MAX_SOURCE_BYTES:
        return None
    try:
        source = resolve_private_user_file_path(
            source_path, storage_root=get_data_upload_dir(), tenant_id=tenant_id,
            user_id=user_id, allowed_extensions={".csv"},
        )
        actual_size = source.stat().st_size
        digest = _safe_hash(source_hash)
        if actual_size != int(source_size) or _sha256(source) != digest:
            return None
        directory = _identity_dir(
            tenant_id=tenant_id, user_id=user_id, project_id=project_id,
            dataset_id=dataset_id, version_id=version_id, create=False,
        )
        if not directory.is_dir():
            return None
        artifact, manifest, _ = _paths(directory, digest)
        return _manifest_matches(
            _read_manifest(manifest), artifact=artifact, tenant_id=tenant_id,
            user_id=user_id, project_id=project_id, dataset_id=dataset_id,
            version_id=version_id, source_name=source.name, source_hash=digest,
            source_size=actual_size, declared_rows=declared_rows,
        )
    except (OSError, ValueError):
        return None


@account_file_work
def get_or_create(
    *, source_path: str, tenant_id: int, user_id: int, project_id: str,
    dataset_id: str, version_id: str, source_hash: str, source_size: int,
    declared_rows: int | None,
) -> ParquetArtifact | None:
    """Return only an integrity-checked artifact bound to an authorized CSV."""
    if not _enabled() or source_size < MIN_SOURCE_BYTES or source_size > MAX_SOURCE_BYTES:
        return None
    try:
        source = resolve_private_user_file_path(
            source_path, storage_root=get_data_upload_dir(), tenant_id=tenant_id,
            user_id=user_id, allowed_extensions={".csv"},
        )
        actual_size = source.stat().st_size
        digest = _safe_hash(source_hash)
        if actual_size != int(source_size) or _sha256(source) != digest:
            return None
        directory = _identity_dir(
            tenant_id=tenant_id, user_id=user_id, project_id=project_id,
            dataset_id=dataset_id, version_id=version_id,
        )
        artifact, manifest, lock_path = _paths(directory, digest)
        existing = _manifest_matches(
            _read_manifest(manifest), artifact=artifact, tenant_id=tenant_id,
            user_id=user_id, project_id=project_id, dataset_id=dataset_id,
            version_id=version_id, source_name=source.name, source_hash=digest,
            source_size=actual_size, declared_rows=declared_rows,
        )
        if existing:
            return existing
        if not _conversion_slots.acquire(blocking=False):
            return None
        try:
            lock_descriptor = os.open(
                lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600,
            )
            with os.fdopen(lock_descriptor, "a+b") as lock:
                os.chmod(lock_path, 0o600)
                try:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return None
                existing = _manifest_matches(
                    _read_manifest(manifest), artifact=artifact, tenant_id=tenant_id,
                    user_id=user_id, project_id=project_id, dataset_id=dataset_id,
                    version_id=version_id, source_name=source.name, source_hash=digest,
                    source_size=actual_size, declared_rows=declared_rows,
                )
                if existing:
                    return existing
                # A cache miss must not mutate another process's publication or
                # repair before owning the version's filesystem lock.
                _remove_pair(manifest, artifact)
                cleanup_cache()
                ensure_disk_capacity(directory, incoming_bytes=actual_size)
                temporary = directory / f".{artifact.name}.{uuid4().hex}.building"
                try:
                    size, rows, compatible, numeric, peak_rss, peak_scratch = _convert(
                        source, temporary, declared_rows=declared_rows,
                    )
                    if size <= 0 or size > MAX_TENANT_CACHE_BYTES:
                        return None
                    parquet_hash = _sha256(temporary)
                    os.chmod(temporary, 0o600)
                    os.replace(temporary, artifact)
                    _write_json_atomic(manifest, {
                        "format_version": CACHE_FORMAT_VERSION,
                        "tenant_id": int(tenant_id), "user_id": int(user_id),
                        "project_id": _safe_uuid(project_id),
                        "dataset_id": _safe_uuid(dataset_id),
                        "dataset_version_id": _safe_uuid(version_id),
                        "source_filename": source.name, "source_sha256": digest,
                        "source_size_bytes": actual_size, "config": _CONFIG,
                        "config_sha256": CONFIG_HASH, "parquet_sha256": parquet_hash,
                        "parquet_size_bytes": size, "row_count": rows,
                        "polars_compatible_columns": compatible,
                        "polars_numeric_columns": numeric,
                        "conversion_peak_rss_bytes": peak_rss,
                        "conversion_peak_scratch_bytes": peak_scratch,
                        "created_at_epoch": int(time.time()),
                    })
                    bounded = cleanup_cache()
                    if not artifact.is_file() or bounded["bytes"] > MAX_CACHE_BYTES:
                        _remove_pair(manifest, artifact)
                        return None
                    return ParquetArtifact(
                        artifact, parquet_hash, size, rows, False,
                        tuple(compatible), tuple(numeric),
                    )
                finally:
                    temporary.unlink(missing_ok=True)
        finally:
            _conversion_slots.release()
    except (OSError, ValueError, RuntimeError, StorageSafetyError, TimeoutError,
            json.JSONDecodeError):
        return None


def remove_for_source(source_path: Path, *, storage_root: Path | None = None) -> int:
    """Remove cache entries before the fenced lifecycle deletes a source file."""
    source = source_path.resolve()
    upload_root = (storage_root or get_data_upload_dir()).resolve()
    root = _cache_root(upload_root, create=False)
    if not root.exists():
        return 0
    assert_path_within_root(source, upload_root)
    relative = source.relative_to(upload_root)
    if len(relative.parts) != 3 or not relative.parts[0].startswith("tenant_") \
            or not relative.parts[1].startswith("user_"):
        return 0
    scoped = root / relative.parts[0] / relative.parts[1]
    if not scoped.exists():
        return 0
    removed = 0
    for manifest in scoped.glob("project_*/dataset_*/version_*/*.json"):
        data = _read_manifest(manifest)
        if data and data.get("source_filename") == source.name:
            _remove_pair(manifest, manifest.with_suffix(".parquet"))
            removed += 1
    return removed
