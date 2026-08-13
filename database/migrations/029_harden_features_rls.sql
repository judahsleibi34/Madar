-- ============================================================
-- Harden features RLS and direct grants
-- ============================================================

begin;

alter table public.features enable row level security;

-- Remove any existing direct-access policies on features before installing
-- the tenant-scoped policy. Current application access uses the backend
-- service role, so direct authenticated writes are intentionally not exposed.
do $$
declare
    policy_record record;
begin
    for policy_record in
        select policyname
        from pg_policies
        where schemaname = 'public'
          and tablename = 'features'
    loop
        execute format(
            'drop policy if exists %I on public.features',
            policy_record.policyname
        );
    end loop;
end $$;

revoke all on table public.features from anon;
revoke all on table public.features from authenticated;

grant select on table public.features to authenticated;
grant all privileges on table public.features to service_role;

-- The id sequence is only needed by privileged backend writes.
do $$
begin
    if to_regclass('public.features_id_seq') is not null then
        revoke all on sequence public.features_id_seq from anon;
        revoke all on sequence public.features_id_seq from authenticated;
        grant all privileges on sequence public.features_id_seq to service_role;
    end if;
end $$;

create policy features_select_tenant_member
on public.features
for select
to authenticated
using (
    exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = features.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
    )
);

-- Public app flows resolve tenants through the backend. Direct anon access to
-- tenants is unnecessary and RLS already blocks it without an anon policy.
revoke select on table public.tenants from anon;

notify pgrst, 'reload schema';

commit;
