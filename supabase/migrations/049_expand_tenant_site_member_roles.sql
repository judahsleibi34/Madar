alter table public.tenant_site_memberships
  drop constraint if exists tenant_site_memberships_role_check;

alter table public.tenant_site_memberships
  add constraint tenant_site_memberships_role_check
  check (char_length(btrim(role)) between 1 and 160);

alter table public.tenant_site_memberships
  add column if not exists source text not null default 'registered';

alter table public.tenant_site_memberships
  drop constraint if exists tenant_site_memberships_source_check;

alter table public.tenant_site_memberships
  add constraint tenant_site_memberships_source_check
  check (source in ('registered', 'admin'));
