import os
from dotenv import load_dotenv
from supabase import create_client, Client

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

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
service_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

