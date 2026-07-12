import os
import httpx
from dotenv import load_dotenv
from supabase import create_client, Client, ClientOptions

load_dotenv()

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
    return create_client(
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

