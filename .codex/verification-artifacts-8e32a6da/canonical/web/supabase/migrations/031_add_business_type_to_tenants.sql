-- ============================================================
-- Add optional business type to tenants for onboarding
-- ============================================================

begin;

alter table public.tenants
add column if not exists business_type text;

notify pgrst, 'reload schema';

commit;
