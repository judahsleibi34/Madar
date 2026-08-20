-- ============================================================
-- Grant API permissions for features table
-- ============================================================

grant select, insert, update, delete
on table public.features
to service_role;

grant usage, select
on sequence public.features_id_seq
to service_role;

-- Optional:
-- Only keep this if authenticated users will access the table directly.
-- If all access goes through FastAPI using service_supabase, you can remove it.

grant select
on table public.features
to authenticated;

grant usage, select
on sequence public.features_id_seq
to authenticated;