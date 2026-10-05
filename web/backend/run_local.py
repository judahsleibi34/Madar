"""Start the native development API without requiring Docker or Redis."""

import os
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def configure_local_environment(*, local_database=False):
    if os.getenv("APP_ENV", "").strip().lower() in {"prod", "production"}:
        raise RuntimeError("run_local.py is for local development only")

    web_root = Path(__file__).resolve().parents[1]
    env_path = web_root / (".env.database.local" if local_database else ".env")
    if local_database and not env_path.is_file():
        raise RuntimeError("Local database configuration is missing; run web/scripts/start_local_database.py first")
    load_dotenv(env_path, override=True)
    if os.getenv("APP_ENV", "development").strip().lower() != "development":
        raise RuntimeError("run_local.py requires APP_ENV=development")
    if local_database:
        for key in ("SUPABASE_URL", "SUPABASE_DB_URL"):
            if urlsplit(os.getenv(key, "")).hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise RuntimeError(f"Local database mode requires a loopback {key}")
        schema = json.loads((web_root / "deployment/releases/release.json").read_text())["schema"]
        minimum, maximum, target = (int(schema[key]) for key in ("compatible_min", "compatible_max", "target"))
        if not 0 < minimum <= target <= maximum:
            raise RuntimeError("Invalid local release schema compatibility contract")
        os.environ["SCHEMA_COMPATIBLE_MIN"] = str(minimum)
        os.environ["SCHEMA_COMPATIBLE_MAX"] = str(maximum)
    elif os.getenv("MADAR_TEST_AUTO_LOGIN", "").lower() == "true":
        raise RuntimeError("Test auto-login requires --local-db")

    os.environ["APP_ENV"] = "development"
    os.environ["MADAR_ENV_FILE"] = str(env_path)
    # Preserve these explicit local settings when database.py loads the env again.
    os.environ["MADAR_ENV_OVERRIDE"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    os.environ["RATE_LIMIT_FAIL_OPEN"] = "true"


def create_local_app():
    configure_local_environment(local_database=True)
    from app import app
    if os.getenv("MADAR_TEST_AUTO_LOGIN", "").lower() == "true":
        from local_dev_auth import LocalTestLoginMiddleware
        app.add_middleware(LocalTestLoginMiddleware)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-db", action="store_true", help="Use the isolated Docker-backed Supabase database")
    parser.add_argument("--local-commerce", action="store_true", help="Enable payment simulation only on the isolated local database")
    args = parser.parse_args()
    if args.local_commerce and not args.local_db:
        parser.error("--local-commerce requires --local-db")
    configure_local_environment(local_database=args.local_db)
    if args.local_commerce:
        os.environ["MADAR_LOCAL_COMMERCE_ADAPTER"] = "true"
    import uvicorn

    print("Local API: Redis is optional; in-memory rate limiting is enabled on outage.")
    uvicorn.run(
        "run_local:create_local_app" if args.local_db else "app:app",
        factory=args.local_db,
        host="127.0.0.1",
        port=8000,
        reload=True,
        app_dir=str(Path(__file__).resolve().parent),
        reload_dirs=[str(Path(__file__).resolve().parent)],
    )
