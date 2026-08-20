-- Authoritative, cheap schema contract for readiness and deployment gates.
begin;

create table if not exists public.application_schema_state (
  contract_key text primary key,
  schema_version integer not null,
  applied_at timestamptz not null default now(),
  constraint application_schema_state_version_check check (schema_version > 0)
);

alter table public.application_schema_state enable row level security;
revoke all on public.application_schema_state from public, anon, authenticated;
revoke all on public.application_schema_state from service_role;
grant select on public.application_schema_state to service_role;

insert into public.application_schema_state (contract_key, schema_version, applied_at)
values ('core', 81, now())
on conflict (contract_key) do update
set schema_version = excluded.schema_version,
    applied_at = excluded.applied_at;

notify pgrst, 'reload schema';
commit;
