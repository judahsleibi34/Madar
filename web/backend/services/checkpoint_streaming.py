"""Private disk-backed state and deterministic streaming checkpoint output."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException


MAX_CHECKPOINT_RECORDS = 100_000
MAX_CHECKPOINT_CHANGES = 1_000_000
# One reserved identifier column keeps generated CSV within the 500-column reader cap.
MAX_CHECKPOINT_COLUMNS = 499
MAX_CHECKPOINT_BYTES = 100 * 1024 * 1024
DEFAULT_SCRATCH_LIMIT_BYTES = 1024 * 1024 * 1024
STALE_SCRATCH_SECONDS = 24 * 60 * 60
SCRATCH_PREFIX = "checkpoint-"


def _scratch_root() -> Path:
    configured = os.getenv("DATA_CHECKPOINT_SCRATCH_DIR", "").strip()
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "madar-checkpoints"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root.resolve()


def cleanup_stale_workspaces(*, now: float | None = None) -> int:
    """Remove only expired worker scratch directories beneath the fixed private root."""
    root = _scratch_root()
    current = time.time() if now is None else now
    removed = 0
    for candidate in root.iterdir():
        if not candidate.name.startswith(SCRATCH_PREFIX) or not candidate.is_dir() \
                or candidate.is_symlink():
            continue
        try:
            if current - candidate.stat().st_mtime < STALE_SCRATCH_SECONDS:
                continue
            shutil.rmtree(candidate)
            removed += 1
        except FileNotFoundError:
            continue
    return removed


def create_workspace(checkpoint_id: str | None = None) -> Path:
    cleanup_stale_workspaces()
    token = str(checkpoint_id or "adhoc").lower()
    if not re.fullmatch(r"[0-9a-f-]{1,64}", token):
        token = "adhoc"
    path = Path(tempfile.mkdtemp(
        prefix=f"{SCRATCH_PREFIX}{token[:36]}-", dir=_scratch_root(),
    )).resolve()
    os.chmod(path, 0o700)
    return path


def workspace_bytes(workspace: Path) -> int:
    return sum(item.stat().st_size for item in workspace.rglob("*") if item.is_file())


def enforce_scratch_limit(workspace: Path) -> None:
    maximum = int(os.getenv("DATA_CHECKPOINT_SCRATCH_MAX_BYTES", str(DEFAULT_SCRATCH_LIMIT_BYTES)))
    used = workspace_bytes(workspace)
    free = shutil.disk_usage(workspace).free
    floor = int(os.getenv("STORAGE_DISK_FREE_FLOOR_BYTES", str(256 * 1024 * 1024)))
    if used > maximum or free < floor:
        raise HTTPException(status_code=507, detail={
            "code": "checkpoint_scratch_capacity",
            "message": "Checkpoint scratch capacity is unavailable.",
        })


class HashingTextWriter:
    """Minimal text writer for csv.writer with incremental byte hashing."""

    def __init__(self, path: Path):
        self._file = path.open("xb")
        os.chmod(path, 0o600)
        self.digest = hashlib.sha256()
        self.size_bytes = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        self.size_bytes += len(encoded)
        if self.size_bytes > MAX_CHECKPOINT_BYTES:
            raise HTTPException(status_code=413, detail={
                "code": "checkpoint_artifact_limit",
                "message": "This checkpoint exceeds the immutable object limit.",
            })
        self._file.write(encoded)
        self.digest.update(encoded)
        return len(value)

    def close(self) -> None:
        if not self._file.closed:
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


@dataclass
class ReconstructionArtifact:
    workspace: Path
    csv_path: Path
    record_count: int
    change_count: int
    state_hash: str
    checkpoint_sha256: str
    checkpoint_size_bytes: int
    resource_key: str
    latest_committed_revision: int
    database_reads: int
    database_writes: int
    immutable_bytes_read: int
    columns: tuple[str, ...] = ()

    def __getitem__(self, key: str):
        return getattr(self, key)

    def cleanup(self) -> None:
        root = _scratch_root()
        resolved = self.workspace.resolve()
        if resolved.parent == root and resolved.name.startswith(SCRATCH_PREFIX):
            shutil.rmtree(resolved, ignore_errors=True)


class DiskBackedState:
    def __init__(self, workspace: Path):
        self.path = workspace / "state.sqlite3"
        self.connection = sqlite3.connect(self.path)
        os.chmod(self.path, 0o600)
        self.connection.execute("pragma journal_mode=delete")
        self.connection.execute("pragma synchronous=full")
        self.connection.execute("pragma temp_store=file")
        self.connection.executescript("""
            create table records (
              record_id text primary key,
              payload_json text not null
            ) without rowid;
            create table columns (
              name text primary key
            ) without rowid;
        """)
        self.writes = 0

    def apply(self, *, record_id: str, outcome: str, payload: dict | None) -> None:
        if outcome == "deleted":
            self.connection.execute("delete from records where record_id=?", (record_id,))
            self.writes += 1
            return
        if outcome in {"duplicate", "stale_ignored"}:
            return
        if not isinstance(payload, dict):
            raise RuntimeError("incremental_history_payload_invalid")
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        self.connection.execute(
            "insert into records(record_id,payload_json) values(?,?) "
            "on conflict(record_id) do update set payload_json=excluded.payload_json",
            (record_id, encoded),
        )
        self.connection.executemany(
            "insert or ignore into columns(name) values(?)",
            ((str(column),) for column in payload),
        )
        self.writes += 1 + len(payload)

    def commit_and_validate(self, workspace: Path) -> None:
        self.connection.commit()
        record_count = int(self.connection.execute(
            "select count(*) from records"
        ).fetchone()[0])
        column_count = int(self.connection.execute(
            "select count(*) from columns"
        ).fetchone()[0])
        if record_count > MAX_CHECKPOINT_RECORDS:
            raise HTTPException(status_code=413, detail={
                "code": "checkpoint_record_limit",
                "message": "This checkpoint exceeds the current bounded record limit.",
            })
        if column_count > MAX_CHECKPOINT_COLUMNS:
            raise HTTPException(status_code=413, detail={
                "code": "checkpoint_column_limit",
                "message": "This checkpoint exceeds the current bounded column limit.",
            })
        enforce_scratch_limit(workspace)

    def finalize(self, *, workspace: Path) -> tuple[Path, int, str, str, int, tuple[str, ...]]:
        record_count = int(self.connection.execute(
            "select count(*) from records"
        ).fetchone()[0])
        columns = [row[0] for row in self.connection.execute(
            "select name from columns order by name"
        )]

        state_digest = hashlib.sha256()
        state_digest.update(b"{")
        first = True
        for record_id, payload_json in self.connection.execute(
            "select record_id,payload_json from records order by record_id"
        ):
            if not first:
                state_digest.update(b",")
            first = False
            state_digest.update(json.dumps(
                record_id, ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8"))
            state_digest.update(b":")
            state_digest.update(payload_json.encode("utf-8"))
        state_digest.update(b"}")

        output_path = workspace / "checkpoint.csv"
        with HashingTextWriter(output_path) as output:
            writer = csv.DictWriter(
                output, fieldnames=["_source_record_id", *columns],
                lineterminator="\n", extrasaction="ignore",
            )
            writer.writeheader()
            for record_id, payload_json in self.connection.execute(
                "select record_id,payload_json from records order by record_id"
            ):
                writer.writerow({
                    "_source_record_id": record_id, **json.loads(payload_json),
                })
        enforce_scratch_limit(workspace)
        return (
            output_path, record_count, state_digest.hexdigest(),
            output.digest.hexdigest(), output.size_bytes, tuple(columns),
        )

    def close(self) -> None:
        self.connection.close()
