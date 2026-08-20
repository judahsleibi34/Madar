begin;

insert into public.tenant_site_project_roles (tenant_id, project_id, role_key)
select distinct project.tenant_id, project.id, 'customer'
from public.builder_projects project
join public.tenant_site_memberships membership
  on membership.tenant_id = project.tenant_id
on conflict (project_id, role_key) do update
set deleted_at = null,
    updated_at = now();

insert into public.tenant_site_project_role_assignments (membership_id, project_id, role_id)
select membership.id, project.id, role.id
from public.tenant_site_memberships membership
join public.builder_projects project
  on project.tenant_id = membership.tenant_id
join public.tenant_site_project_roles role
  on role.project_id = project.id
 and role.role_key = case
   when coalesce(membership.role, '') ~ '^[A-Za-z0-9_-]{1,160}$' then membership.role
   else 'customer'
 end
where role.deleted_at is null
on conflict (membership_id, project_id) do nothing;

notify pgrst, 'reload schema';
commit;