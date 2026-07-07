import os
import re
from pathlib import Path


DEFAULT_PUBLIC_UPLOADS_DIR = "uploads"
DEFAULT_DATA_UPLOAD_DIR = "private_uploads"
DEFAULT_PRIVATE_CHARTS_DIR = "private_generated_charts"
SAFE_FILENAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
SAFE_SCOPE_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


def get_public_uploads_dir() -> Path:
    return Path(
        os.getenv(
            "PUBLIC_UPLOADS_DIR",
            os.getenv("UPLOADS_DIR", DEFAULT_PUBLIC_UPLOADS_DIR),
        )
    ).resolve()


def get_data_upload_dir() -> Path:
    return Path(os.getenv("DATA_UPLOAD_DIR", DEFAULT_DATA_UPLOAD_DIR)).resolve()


def get_private_charts_dir() -> Path:
    return Path(
        os.getenv(
            "PRIVATE_CHARTS_DIR",
            os.getenv("GENERATED_CHARTS_DIR", DEFAULT_PRIVATE_CHARTS_DIR),
        )
    ).resolve()


def _validate_private_dir_not_publicly_mounted(
    *,
    public_uploads_dir: Path,
    private_dir: Path,
    env_name: str,
) -> None:
    public_root = public_uploads_dir.resolve()
    private_root = private_dir.resolve()

    if public_root == private_root or public_root in private_root.parents:
        raise RuntimeError(
            f"{env_name} must not be the same as, or nested under, "
            "PUBLIC_UPLOADS_DIR/UPLOADS_DIR because /uploads is publicly served."
        )


def validate_safe_filename(
    filename: str,
    *,
    allowed_extensions: set[str] | frozenset[str] | None = None,
    error_type: type[Exception] = ValueError,
    error_message: str = "Invalid file name",
) -> str:
    clean_filename = (filename or "").strip()

    if (
        not clean_filename
        or "\x00" in clean_filename
        or "/" in clean_filename
        or "\\" in clean_filename
        or Path(clean_filename).name != clean_filename
        or ".." in Path(clean_filename).parts
        or not SAFE_FILENAME_PATTERN.fullmatch(clean_filename)
    ):
        raise error_type(error_message)

    if allowed_extensions is not None and Path(clean_filename).suffix.lower() not in allowed_extensions:
        raise error_type(error_message)

    return clean_filename


def safe_scope_part(prefix: str, value: str | int) -> str:
    text = str(value).strip()

    if not SAFE_SCOPE_PATTERN.fullmatch(text):
        raise ValueError("Invalid storage scope")

    return f"{prefix}_{text}"


def assert_path_within_root(path: Path, root: Path, *, error: Exception | None = None) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()

    if resolved_root != resolved_path and resolved_root not in resolved_path.parents:
        if error is not None:
            raise error
        raise PermissionError("Path is outside the expected storage root")

    return resolved_path


def resolve_private_user_file_path(
    file_path: str,
    *,
    storage_root: Path,
    tenant_id: str | int,
    user_id: str | int,
    allowed_extensions: set[str] | frozenset[str] | None = None,
) -> Path:
    requested = Path(file_path)
    resolved = (Path.cwd() / requested).resolve() if not requested.is_absolute() else requested.resolve()
    scoped_root = (
        storage_root.resolve()
        / safe_scope_part("tenant", tenant_id)
        / safe_scope_part("user", user_id)
    ).resolve()

    assert_path_within_root(resolved, scoped_root)

    if allowed_extensions is not None and resolved.suffix.lower() not in allowed_extensions:
        raise PermissionError("File type is not allowed")

    if not resolved.is_file():
        raise FileNotFoundError("Private user file was not found")

    return resolved


def validate_private_uploads_not_publicly_mounted(
    *,
    public_uploads_dir: Path,
    data_upload_dir: Path,
) -> None:
    _validate_private_dir_not_publicly_mounted(
        public_uploads_dir=public_uploads_dir,
        private_dir=data_upload_dir,
        env_name="DATA_UPLOAD_DIR",
    )


def validate_private_charts_not_publicly_mounted(
    *,
    public_uploads_dir: Path,
    private_charts_dir: Path,
) -> None:
    _validate_private_dir_not_publicly_mounted(
        public_uploads_dir=public_uploads_dir,
        private_dir=private_charts_dir,
        env_name="PRIVATE_CHARTS_DIR/GENERATED_CHARTS_DIR",
    )
