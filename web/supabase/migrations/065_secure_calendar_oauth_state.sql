-- Single-use, tenant-bound calendar OAuth state with service-role-only access.
begin;

create table if not exists public.calendar_oauth_states (
  nonce_hash text primary key,
  connection_id uuid not null references public.calendar_sync_connections(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  calendar_id uuid not null references public.calendars(id) on delete cascade,
  provider text not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint calendar_oauth_state_provider_check check (provider in ('google','microsoft')),
  constraint calendar_oauth_state_nonce_hash_check check (nonce_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists calendar_oauth_states_expiry_idx
  on public.calendar_oauth_states (expires_at)
  where consumed_at is null;

alter table public.calendar_oauth_states enable row level security;
revoke all on table public.calendar_oauth_states from public, anon, authenticated;
grant select, insert, update, delete on table public.calendar_oauth_states to service_role;

create or replace function public.consume_calendar_oauth_state(
  target_nonce_hash text,
  target_connection_id uuid,
  target_tenant_id integer,
  target_user_id integer,
  target_calendar_id uuid,
  target_provider text
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  changed_rows integer;
begin
  update public.calendar_oauth_states
  set consumed_at = now()
  where nonce_hash = target_nonce_hash
    and connection_id = target_connection_id
    and tenant_id = target_tenant_id
    and user_id = target_user_id
    and calendar_id = target_calendar_id
    and provider = target_provider
    and consumed_at is null
    and expires_at >= now();

  get diagnostics changed_rows = row_count;
  return changed_rows = 1;
end;
$$;

revoke all on function public.consume_calendar_oauth_state(text, uuid, integer, integer, uuid, text)
  from public, anon, authenticated;
grant execute on function public.consume_calendar_oauth_state(text, uuid, integer, integer, uuid, text)
  to service_role;

notify pgrst, 'reload schema';
commit;
