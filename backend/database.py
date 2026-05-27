import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Missing Supabase environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
service_supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY,
)
