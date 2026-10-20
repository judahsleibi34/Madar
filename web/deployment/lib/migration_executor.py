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
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
if __package__:
    from .learning_migration_path import authorize_manifest as authorize_learning_manifest
else:
    # The isolated privileged controller imports from its trusted lib directory.
    from learning_migration_path import authorize_manifest as authorize_learning_manifest


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_directory(path: Path) -> None:
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def atomic_json(path: Path, payload: dict[str, Any], *, exclusive: bool=False) -> None:
    # Persist newly created directory entries as well as the final receipt.
    # fsync(file) alone cannot preserve a rename or a new attempt directory.
    missing=[];parent=path.parent
    while not parent.exists():
        missing.append(parent);parent=parent.parent
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for directory in reversed(missing):_sync_directory(directory.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        if exclusive:
            # Atomic no-replace publication of a fully written/fsynced inode.
            # The early exists() check is only a fast refusal, not a claim.
            try:os.link(temporary,path,follow_symlinks=False)
            except FileExistsError:
                raise RuntimeError('coordinated_migration_attempt_consumed') from None
            os.unlink(temporary)
        else:os.replace(temporary, path)
        _sync_directory(path.parent)
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
    excluded_schemas: tuple[int, ...] = ()
    coordinated: bool = False

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
        learning_branch = False
        # A skipped version is a reviewed branch, never a general gap allowance.
        for entry in raw.get("migrations") or []:
            if int(entry["from_schema"]) + 1 != int(entry["to_schema"]):
                if (int(entry["from_schema"]), int(entry["to_schema"])) != (141, 143):
                    raise ValueError("migration schema transition is invalid")
                authorize_learning_manifest(repository_root, path, raw)
                learning_branch = True
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
            if migration.to_schema != migration.number or (
                migration.from_schema + 1 != migration.to_schema and not learning_branch
            ):
                raise ValueError("migration schema transition is invalid")
            if previous is not None and migration.from_schema != previous:
                raise ValueError("migration manifest is not contiguous")
            previous = migration.to_schema
            migrations.append(migration)
        if not migrations:
            raise ValueError("migration manifest is empty")
        return cls(release_sha=release_sha, migrations=tuple(migrations),
                   excluded_schemas=(142,) if learning_branch else ())

    def accepts_schema(self, schema: int) -> bool:
        return (self.migrations[0].from_schema <= schema <= self.migrations[-1].to_schema
                and schema not in self.excluded_schemas)


class LockedMigrationExecutor:
    """Execute a contiguous manifest while holding one PostgreSQL session lock."""

    LOCK_KEY = 487_062_024_082_083
    MAX_MIGRATION_BYTES = 16 * 1024 * 1024
    MAX_BATCH_BYTES = 64 * 1024 * 1024

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        manifest: MigrationManifest,
        state_file: Path,
        backup_dir: Path,
        backup_verifier: Callable[[Path], None],
        failure_formatter: Callable[[Exception], str] | None = None,
        migration_guard: Callable[[Any, Migration], None] | None = None,
        completion_guard: Callable[[Any], None] | None = None,
        expected_origin: int | None = None,
    ):
        self.connection_factory = connection_factory
        self.manifest = manifest
        self.state_file = state_file
        self.backup_dir = backup_dir
        self.backup_verifier = backup_verifier
        self.failure_formatter = failure_formatter or (lambda error: str(error)[:160])
        if manifest.coordinated and not callable(migration_guard):
            raise RuntimeError('coordinated_migration_guard_required')
        self.migration_guard = migration_guard
        if completion_guard is not None and not callable(completion_guard):
            raise RuntimeError('migration_completion_guard_invalid')
        self.completion_guard = completion_guard
        if expected_origin is not None and (type(expected_origin) is not int or not manifest.accepts_schema(expected_origin)):
            raise RuntimeError('migration_expected_origin_invalid')
        self.expected_origin = expected_origin

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

    def verify_migrations(self) -> tuple[str, ...]:
        """Capture exact verified SQL before backup creation or DB access.

        Release worktrees can be operator owned. Never reopen a verified path
        for execution after backup verification or a live admission callback:
        the pathname could then name different bytes. Only these immutable,
        checksum-bound strings may reach the migration connection.
        """
        statements = []
        total = 0
        for migration in self.manifest.migrations:
            try:
                descriptor = os.open(migration.path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            except FileNotFoundError:
                raise RuntimeError(f"migration_missing:{migration.number}")
            except OSError:
                raise RuntimeError(f"migration_source_invalid:{migration.number}") from None
            with os.fdopen(descriptor, "rb") as handle:
                metadata = os.fstat(handle.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    raise RuntimeError(f"migration_source_not_regular:{migration.number}")
                if metadata.st_size > self.MAX_MIGRATION_BYTES:
                    raise RuntimeError(f"migration_size_exceeded:{migration.number}")
                data = handle.read(self.MAX_MIGRATION_BYTES + 1)
            if len(data) > self.MAX_MIGRATION_BYTES:
                raise RuntimeError(f"migration_size_exceeded:{migration.number}")
            total += len(data)
            if total > self.MAX_BATCH_BYTES:
                raise RuntimeError("migration_batch_size_exceeded")
            if hashlib.sha256(data).hexdigest() != migration.sha256:
                raise RuntimeError(f"migration_checksum_mismatch:{migration.number}")
            try:
                statements.append(data.decode("utf-8"))
            except UnicodeDecodeError:
                raise RuntimeError(f"migration_encoding_invalid:{migration.number}") from None
        return tuple(statements)

    def run(self) -> dict[str, Any]:
        if self.manifest.coordinated and self.state_file.exists():
            raise RuntimeError('coordinated_migration_attempt_consumed')
        statements = self.verify_migrations()
        self.backup_verifier(self.backup_dir)

        state: dict[str, Any] = {
            "release_sha": self.manifest.release_sha,
            "backup": {"path": str(self.backup_dir), "verified": True},
            "started_at": utc_now(),
            "phase": "acquiring_lock",
            "status": "running",
            "migrations": [],
        }
        atomic_json(self.state_file, state,exclusive=self.manifest.coordinated)
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
                target = self.manifest.migrations[-1].to_schema
                if not self.manifest.accepts_schema(current):
                    raise RuntimeError(f"unexpected_schema:{current}")
                if self.expected_origin is not None and current!=self.expected_origin:
                    raise RuntimeError('migration_origin_changed')
                for migration, statement in zip(self.manifest.migrations, statements):
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
                    if self.migration_guard is not None:
                        self.migration_guard(cursor, migration)
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
                    cursor.execute(statement)
                    current = self._schema(cursor)
                    if current != migration.to_schema:
                        raise RuntimeError(f"migration_schema_not_advanced:{migration.number}")
                    record.update(status="applied", completed_at=utc_now())
                    state["observed_schema"] = current
                    atomic_json(self.state_file, state)
                if current != target:
                    raise RuntimeError(f"target_schema_not_reached:{current}")
                # Final live protocols/quiescence must be observed on the same
                # advisory-locked session before a completed receipt is sealed.
                # Failure after a SQL COMMIT is a forward-repair state, never
                # permission to replay the already advanced database.
                if self.completion_guard is not None:
                    self.completion_guard(cursor)
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
                failure_code=self.failure_formatter(error),
                failed_at=utc_now(),
            )

            if rollback_error is not None:
                state["rollback_failure_code"] = self.failure_formatter(rollback_error)

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
