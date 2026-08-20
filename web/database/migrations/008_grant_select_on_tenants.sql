grant select on public.tenants to anon;
grant select on public.tenants to authenticated;
grant select on public.tenants to service_role;

notify pgrst, 'reload schema';