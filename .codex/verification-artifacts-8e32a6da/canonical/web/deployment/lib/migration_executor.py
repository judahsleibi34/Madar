"""Backup-gated, checksum-verified PostgreSQL migration execution.

The executor is deliberately independent from traffic promotion. Madar uses a
compatibility bridge release first, then applies expand migrations while that
known-good bridge is serving. A failed migration is resumed or forward-repaired;
it is never automatically reversed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass(frozen=True)
class Migration:
    number: int
    path: Path
    sha256: str
    from_schema: int
    to_schema: int
    compatibility: str


@dataclass(frozen=True)
class MigrationManifest:
    release_sha: str
    migrations: tuple[Migration, ...]

    @classmethod
    def load(cls, path: Path, repository_root: Path) -> "MigrationManifest":
        raw = json.loads(path.read_text(encoding="utf-8"))
        release_sha = str(raw.get("release_sha") or "").strip()
        if release_sha not in {"CURRENT", "STAGING"} and (
            len(release_sha) != 40 or any(char not in "0123456789abcdef" for char in release_sha)
        ):
            raise ValueError("migration manifest release_sha is invalid")
        migrations: list[Migration] = []
        previous = None
        for entry in raw.get("migrations") or []:
            relative = Path(str(entry["path"]))
            migration_path = (repository_root / relative).resolve()
            if repository_root.resolve() not in migration_path.parents:
                raise ValueError("migration path escapes repository")
            migration = Migration(
                number=int(entry["number"]),
                path=migration_path,
                sha256=str(entry["sha256"]).lower(),
                from_schema=int(entry["from_schema"]),
                to_schema=int(entry["to_schema"]),
                compatibility=str(entry["compatibility"]),
            )
            if migration.compatibility not in {"expand-only", "forward-compatible"}:
                raise ValueError("automatic executor accepts expand/forward-compatible migrations only")
            if migration.to_schema != migration.number or migration.from_schema + 1 != migration.to_schema:
                raise ValueError("migration schema transition is invalid")
            if previous is not None and migration.from_schema != previous:
                raise ValueError("migration manifest is not contiguous")
            previous = migration.to_schema
            migrations.append(migration)
        if not migrations:
            raise ValueError("migration manifest is empty")
        return cls(release_sha=release_sha, migrations=tuple(migrations))


class LockedMigrationExecutor:
    """Execute a contiguous manifest while holding one PostgreSQL session lock."""

    LOCK_KEY = 487_062_024_082_083

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        manifest: MigrationManifest,
        state_file: Path,
        backup_dir: Path,
        backup_verifier: Callable[[Path], None],
    ):
        self.connection_factory = connection_factory
        self.manifest = manifest
        self.state_file = state_file
        self.backup_dir = backup_dir
        self.backup_verifier = backup_verifier

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _schema(cursor: Any) -> int:
        cursor.execute(
            "select schema_version from public.application_schema_state "
            "where contract_key='core'"
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("application_schema_state_missing")
        return int(row[0])

    def verify_migrations(self) -> None:
        """Verify every pinned input before backup creation or DB access."""
        for migration in self.manifest.migrations:
            if not migration.path.is_file():
                raise RuntimeError(f"migration_missing:{migration.number}")
            if self._checksum(migration.path) != migration.sha256:
                raise RuntimeError(f"migration_checksum_mismatch:{migration.number}")

    def run(self) -> dict[str, Any]:
        self.verify_migrations()
        self.backup_verifier(self.backup_dir)

        state: dict[str, Any] = {
            "release_sha": self.manifest.release_sha,
            "backup": {"path": str(self.backup_dir), "verified": True},
            "started_at": utc_now(),
            "phase": "acquiring_lock",
            "status": "running",
            "migrations": [],
        }
        atomic_json(self.state_file, state)
        connection = self.connection_factory()
        connection.autocommit = True
        lock_acquired = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("select pg_try_advisory_lock(%s)", (self.LOCK_KEY,))
                if not bool(cursor.fetchone()[0]):
                    raise RuntimeError("migration_lock_held")
                lock_acquired = True
                state["phase"] = "schema_validation"
                current = self._schema(cursor)
                state["observed_schema"] = current
                atomic_json(self.state_file, state)
                minimum = self.manifest.migrations[0].from_schema
                target = self.manifest.migrations[-1].to_schema
                if current < minimum or current > target:
                    raise RuntimeError(f"unexpected_schema:{current}")
                for migration in self.manifest.migrations:
                    if current >= migration.to_schema:
                        state["migrations"].append({
                            "number": migration.number, "status": "already_applied",
                            "checksum": migration.sha256,
                        })
                        continue
                    if current != migration.from_schema:
                        raise RuntimeError(
                            f"migration_transition_mismatch:{current}->{migration.to_schema}"
                        )
                    record = {
                        "number": migration.number,
                        "from_schema": migration.from_schema,
                        "to_schema": migration.to_schema,
                        "checksum": migration.sha256,
                        "compatibility": migration.compatibility,
                        "started_at": utc_now(),
                        "status": "applying",
                    }
                    state["phase"] = f"migration_{migration.number}"
                    state["migrations"].append(record)
                    atomic_json(self.state_file, state)
                    cursor.execute(migration.path.read_text(encoding="utf-8"))
                    current = self._schema(cursor)
                    if current != migration.to_schema:
                        raise RuntimeError(f"migration_schema_not_advanced:{migration.number}")
                    record.update(status="applied", completed_at=utc_now())
                    state["observed_schema"] = current
                    atomic_json(self.state_file, state)
                if current != target:
                    raise RuntimeError(f"target_schema_not_reached:{current}")
                state.update(status="completed", phase="complete", completed_at=utc_now())
                atomic_json(self.state_file, state)
                return state
        except Exception as error:
            rollback_error = None

            try:
                connection.rollback()
            except Exception as failure:
                rollback_error = failure

            state.update(
                status="failed",
                failure_code=str(error)[:160],
                failed_at=utc_now(),
            )

            if rollback_error is not None:
                state["rollback_failure_code"] = str(
                    rollback_error
                )[:160]

            atomic_json(self.state_file, state)
            raise

        finally:
            try:
                if lock_acquired:
                    # A failed explicit migration transaction may leave the
                    # connection in an aborted state. Clear it before issuing
                    # any cleanup SQL. The session lock is released by close()
                    # regardless, so cleanup errors must never mask the
                    # original migration exception.
                    try:
                        connection.rollback()
                    except Exception:
                        pass

                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "select pg_advisory_unlock(%s)",
                                (self.LOCK_KEY,),
                            )
                    except Exception:
                        pass
            finally:
                connection.close()
