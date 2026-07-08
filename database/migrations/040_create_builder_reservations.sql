-- ============================================================
-- Durable builder reservations from public published sites
-- ============================================================

begin;

create extension if not exists pgcrypto;

create table if not exists public.builder_reservations (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  site_subdomain text,
  block_id text,
  block_type text,
  reservation_title text,
  customer_name text,
  customer_email text,
  customer_phone text,
  starts_at timestamptz,
  ends_at timestamptz,
  timezone text,
  status text not null default 'new',
  payload jsonb not null default '{}'::jsonb,
  field_snapshot jsonb not null default '[]'::jsonb,
  submitter_ip text,
  user_agent text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint builder_reservations_status_check
    check (status in ('new', 'confirmed', 'cancelled', 'completed', 'rejected'))
);

drop trigger if exists set_builder_reservations_updated_at on public.builder_reservations;

create trigger set_builder_reservations_updated_at
before update on public.builder_reservations
for each row
execute function public.set_updated_at();

create index if not exists builder_reservations_tenant_status_created_idx
on public.builder_reservations (tenant_id, status, created_at desc);

create index if not exists builder_reservations_tenant_project_created_idx
on public.builder_reservations (tenant_id, project_id, created_at desc);

create index if not exists builder_reservations_tenant_starts_at_idx
on public.builder_reservations (tenant_id, starts_at);

create index if not exists builder_reservations_project_block_idx
on public.builder_reservations (project_id, block_id);

alter table public.builder_reservations enable row level security;

revoke all on table public.builder_reservations from anon;
revoke all on table public.builder_reservations from authenticated;

grant select, insert, update, delete
on table public.builder_reservations
to service_role;

notify pgrst, 'reload schema';

commit;
