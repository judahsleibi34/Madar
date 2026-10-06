begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception 'migration_117_schema_state_missing';
  end if;
  if v_schema_version <> 116 then
    raise exception 'migration_117_expected_schema_116_got_%', v_schema_version;
  end if;
  update public.application_schema_state
  set schema_version = 117, applied_at = now()
  where contract_key = 'core';
end;
$$;

create table public.elearning_settings (
  tenant_id integer primary key references public.tenants(tenant_id) on delete cascade,
  settings jsonb not null default '{}'::jsonb check (jsonb_typeof(settings) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger set_elearning_settings_updated_at
before update on public.elearning_settings
for each row execute function public.set_updated_at();

-- All access goes through the authenticated tenant owner/admin API.
alter table public.elearning_settings enable row level security;
revoke all on public.elearning_settings from public, anon, authenticated;
grant select, insert, update, delete on public.elearning_settings to service_role;

create function public.save_elearning_settings(p_tenant_id integer, p_settings jsonb)
returns void language sql security invoker set search_path = public as $$
  insert into public.elearning_settings as current_settings (tenant_id, settings)
  values (p_tenant_id, p_settings)
  on conflict (tenant_id) do update
  set settings = current_settings.settings || excluded.settings;
$$;
revoke all on function public.save_elearning_settings(integer, jsonb) from public, anon, authenticated;
grant execute on function public.save_elearning_settings(integer, jsonb) to service_role;

notify pgrst, 'reload schema';
commit;
