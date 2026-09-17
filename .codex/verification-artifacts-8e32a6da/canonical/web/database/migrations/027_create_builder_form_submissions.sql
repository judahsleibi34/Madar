/* ============================================================
   025_create_builder_form_submissions.sql

   Purpose:
   - Store public submissions for forms embedded in published builder projects.
   - Keep forms/pages inside published_schema for now; tie submissions to tenant/project/form ids.
   ============================================================ */

begin;

create extension if not exists pgcrypto;

create table if not exists public.builder_form_submissions (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  form_id text not null,
  form_title text,
  form_version integer,
  status text not null default 'new',
  answers jsonb not null default '{}'::jsonb,
  quiz_result jsonb,
  field_snapshot jsonb not null default '[]'::jsonb,
  submitted_at timestamptz not null default now(),
  submitter_ip text,
  user_agent text,
  created_at timestamptz not null default now(),
  constraint builder_form_submissions_status_check check (status in ('new', 'reviewed', 'archived', 'spam')),
  constraint builder_form_submissions_answers_object_check check (jsonb_typeof(answers) = 'object'),
  constraint builder_form_submissions_field_snapshot_array_check check (jsonb_typeof(field_snapshot) = 'array')
);

create index if not exists builder_form_submissions_tenant_project_idx
on public.builder_form_submissions (tenant_id, project_id);

create index if not exists builder_form_submissions_tenant_form_idx
on public.builder_form_submissions (tenant_id, form_id);

create index if not exists builder_form_submissions_project_form_submitted_idx
on public.builder_form_submissions (project_id, form_id, submitted_at desc);

create index if not exists builder_form_submissions_status_idx
on public.builder_form_submissions (status);

grant select
on table public.builder_form_submissions
to authenticated;

grant select, insert, update, delete
on table public.builder_form_submissions
to service_role;

alter table public.builder_form_submissions enable row level security;

drop policy if exists builder_form_submissions_select_tenant_member on public.builder_form_submissions;

create policy builder_form_submissions_select_tenant_member
on public.builder_form_submissions
for select
to authenticated
using (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_form_submissions.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
  )
);

notify pgrst, 'reload schema';

commit;
