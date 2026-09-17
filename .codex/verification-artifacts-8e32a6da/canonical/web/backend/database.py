import os
import logging
from pathlib import Path

import httpx
import dotenv
from supabase import Client, ClientOptions

from services.supabase_api_key import create_api_key_compatible_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
PRODUCTION_ENVIRONMENTS = {"prod", "production"}


def _environment_name() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("FASTAPI_ENV")
        or "development"
    ).strip().lower()


def _env_override_enabled(environment_name: str) -> bool:
    configured = os.getenv("MADAR_ENV_OVERRIDE")

    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}

    return environment_name not in PRODUCTION_ENVIRONMENTS


def load_backend_environment() -> Path:
    configured_path = os.getenv("MADAR_ENV_FILE", "").strip()
    env_path = (
        Path(configured_path).expanduser()
        if configured_path
        else DEFAULT_ENV_PATH
    )

    if not env_path.is_absolute():
        env_path = PROJECT_ROOT / env_path

    env_path = env_path.resolve()
    environment_name = _environment_name()
    override = _env_override_enabled(environment_name)

    dotenv.load_dotenv(env_path, override=override)
    logger.info(
        "backend.environment_loaded",
        extra={
            "environment": environment_name,
            "env_file": str(env_path),
            "env_file_exists": env_path.is_file(),
            "override": override,
        },
    )
    return env_path


BACKEND_ENV_PATH = load_backend_environment()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Missing Supabase environment variables")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_SERVICE_KEY; privileged backend operations require a service role key"
    )

if SUPABASE_SERVICE_KEY == SUPABASE_ANON_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_KEY must not be the anon key; privileged backend operations require a service role key"
    )


def get_config_readiness() -> dict[str, bool]:
    return {
        "supabase_url": bool(SUPABASE_URL),
        "supabase_anon_key": bool(SUPABASE_ANON_KEY),
        "supabase_service_key": bool(SUPABASE_SERVICE_KEY),
        "service_key_is_distinct": bool(
            SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_KEY != SUPABASE_ANON_KEY
        ),
    }


def create_supabase_client(supabase_key: str) -> Client:
    """Create a thread-safe backend client without HTTP/2 multiplexing.

    The synchronous Supabase client is shared by FastAPI worker threads.
    On Windows, concurrent HTTP/2 streams can fail with WinError 10035 and
    poison the pooled connection for unrelated requests. HTTP/1.1 keeps the
    pool concurrent without sharing a single multiplexed socket.
    """
    timeout_seconds = float(os.getenv("SUPABASE_HTTP_TIMEOUT_SECONDS", "30"))
    transport = httpx.HTTPTransport(
        http2=False,
        retries=2,
    )
    http_client = httpx.Client(
        transport=transport,
        timeout=httpx.Timeout(timeout_seconds, connect=10.0),
        limits=httpx.Limits(
            max_connections=50,
            max_keepalive_connections=20,
            keepalive_expiry=15.0,
        ),
    )
    return create_api_key_compatible_client(
        SUPABASE_URL,
        supabase_key,
        options=ClientOptions(
            postgrest_client_timeout=timeout_seconds,
            storage_client_timeout=int(timeout_seconds),
            function_client_timeout=int(timeout_seconds),
            httpx_client=http_client,
        ),
    )


supabase: Client = create_supabase_client(SUPABASE_ANON_KEY)
service_supabase: Client = create_supabase_client(SUPABASE_SERVICE_KEY)
