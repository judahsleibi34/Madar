begin;

create extension if not exists pgcrypto;

create table if not exists public.builder_form_drafts (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  form_id text not null,
  form_title text,
  form_version integer,
  answers jsonb not null default '{}'::jsonb,
  field_snapshot jsonb not null default '[]'::jsonb,
  form_element_id text,
  page_index integer not null default 0 check (page_index >= 0),
  language text not null default 'en',
  site_user_id integer references public.users(id) on delete set null,
  site_membership_id bigint references public.tenant_site_memberships(id) on delete set null,
  submitter_ip text,
  user_agent text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint builder_form_drafts_answers_object_check check (jsonb_typeof(answers) = 'object'),
  constraint builder_form_drafts_field_snapshot_array_check check (jsonb_typeof(field_snapshot) = 'array')
);

create index if not exists builder_form_drafts_tenant_project_form_idx
  on public.builder_form_drafts (tenant_id, project_id, form_id, updated_at desc);
create index if not exists builder_form_drafts_member_idx
  on public.builder_form_drafts (site_membership_id, updated_at desc)
  where site_membership_id is not null;

grant select on table public.builder_form_drafts to authenticated;
grant select, insert, update, delete on table public.builder_form_drafts to service_role;

alter table public.builder_form_drafts enable row level security;

drop policy if exists builder_form_drafts_select_tenant_member on public.builder_form_drafts;
create policy builder_form_drafts_select_tenant_member
on public.builder_form_drafts
for select
to authenticated
using (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_form_drafts.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
  )
);

notify pgrst, 'reload schema';
commit;
