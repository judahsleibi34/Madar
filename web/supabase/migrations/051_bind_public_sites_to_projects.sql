begin;

alter table public.website_settings
  add column if not exists published_project_id uuid;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'website_settings_published_project_id_fkey'
      and conrelid = 'public.website_settings'::regclass
  ) then
    alter table public.website_settings
      add constraint website_settings_published_project_id_fkey
      foreign key (published_project_id)
      references public.builder_projects(id)
      on delete restrict;
  end if;
end
$$;

create index if not exists website_settings_published_project_id_idx
on public.website_settings (published_project_id)
where published_project_id is not null;

create or replace function public.validate_website_settings_published_project()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  bound_project public.builder_projects;
begin
  if new.published_project_id is null then
    return new;
  end if;

  select * into bound_project
  from public.builder_projects
  where id = new.published_project_id;

  if not found
    or bound_project.tenant_id is distinct from new.tenant_id
    or bound_project.status <> 'published'
    or bound_project.published_schema is null
  then
    raise exception using
      errcode = 'P0001',
      message = 'public_project_binding_invalid';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_website_settings_published_project()
from public, anon, authenticated;
grant execute on function public.validate_website_settings_published_project()
to service_role;

drop trigger if exists validate_website_settings_published_project_trigger
on public.website_settings;
create trigger validate_website_settings_published_project_trigger
before insert or update of tenant_id, published_project_id
on public.website_settings
for each row
execute function public.validate_website_settings_published_project();

-- Preserve existing behavior only where the result is unambiguous. Tenants with
-- multiple published projects remain unbound until an explicit selection.
with single_published_project as (
  select
    tenant_id,
    (array_agg(id order by id))[1] as project_id
  from public.builder_projects
  where status = 'published'
    and published_schema is not null
  group by tenant_id
  having count(*) = 1
)
update public.website_settings settings
set published_project_id = candidate.project_id
from single_published_project candidate
where settings.tenant_id = candidate.tenant_id
  and settings.published_project_id is null;

notify pgrst, 'reload schema';

commit;
