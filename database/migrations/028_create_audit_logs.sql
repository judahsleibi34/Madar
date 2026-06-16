-- ============================================================
-- Create durable backend-only audit logs
-- ============================================================

begin;

create extension if not exists pgcrypto;

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer references public.tenants(tenant_id) on delete set null,
  actor_user_id integer references public.users(id) on delete set null,
  action text not null,
  target_type text not null,
  target_id text,
  metadata jsonb not null default '{}'::jsonb,
  ip text,
  user_agent text,
  created_at timestamptz not null default now(),
  constraint audit_logs_metadata_object_check check (jsonb_typeof(metadata) = 'object')
);

create index if not exists audit_logs_tenant_created_idx
on public.audit_logs (tenant_id, created_at desc);

create index if not exists audit_logs_actor_created_idx
on public.audit_logs (actor_user_id, created_at desc);

create index if not exists audit_logs_action_created_idx
on public.audit_logs (action, created_at desc);

create index if not exists audit_logs_target_idx
on public.audit_logs (target_type, target_id);

alter table public.audit_logs enable row level security;

revoke all on table public.audit_logs from anon;
revoke all on table public.audit_logs from authenticated;

grant select, insert, update, delete
on table public.audit_logs
to service_role;

do $$
begin
    if to_regclass('public.audit_logs_id_seq') is not null then
        revoke all on sequence public.audit_logs_id_seq from anon;
        revoke all on sequence public.audit_logs_id_seq from authenticated;
        grant all privileges on sequence public.audit_logs_id_seq to service_role;
    end if;
end $$;

notify pgrst, 'reload schema';

commit;
