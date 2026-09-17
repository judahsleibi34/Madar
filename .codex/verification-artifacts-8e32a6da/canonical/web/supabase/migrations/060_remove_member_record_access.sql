begin;

update public.tenant_site_project_roles
set capabilities = array_remove(capabilities, 'view_own_records'),
    updated_at = now()
where 'view_own_records' = any(capabilities);

alter table public.tenant_site_project_roles
  drop constraint if exists tenant_site_project_roles_capability_check;
alter table public.tenant_site_project_roles
  add constraint tenant_site_project_roles_capability_check
  check (capabilities <@ array[
    'view_protected_page',
    'submit_protected_form',
    'make_reservation'
  ]::text[]);

notify pgrst, 'reload schema';
commit;