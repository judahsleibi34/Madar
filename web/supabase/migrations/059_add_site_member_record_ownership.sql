begin;

alter table public.builder_form_submissions
  add column if not exists site_user_id integer references public.users(id) on delete set null;
alter table public.builder_form_submissions
  add column if not exists site_membership_id bigint references public.tenant_site_memberships(id) on delete set null;
alter table public.builder_reservations
  add column if not exists site_user_id integer references public.users(id) on delete set null;
alter table public.builder_reservations
  add column if not exists site_membership_id bigint references public.tenant_site_memberships(id) on delete set null;

create index if not exists builder_form_submissions_member_idx
  on public.builder_form_submissions (site_membership_id, submitted_at desc)
  where site_membership_id is not null;
create index if not exists builder_reservations_member_idx
  on public.builder_reservations (site_membership_id, created_at desc)
  where site_membership_id is not null;

alter table public.tenant_site_project_roles
  drop constraint if exists tenant_site_project_roles_capability_check;
alter table public.tenant_site_project_roles
  add constraint tenant_site_project_roles_capability_check
  check (capabilities <@ array[
    'view_protected_page',
    'submit_protected_form',
    'make_reservation',
    'view_own_records'
  ]::text[]);

update public.tenant_site_project_roles
set capabilities = array_append(capabilities, 'view_own_records'),
    updated_at = now()
where not ('view_own_records' = any(capabilities));

notify pgrst, 'reload schema';
commit;