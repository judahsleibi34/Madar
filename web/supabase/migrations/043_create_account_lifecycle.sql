-- Account verification, pending onboarding, and reset request lifecycle.
begin;

create extension if not exists pgcrypto;

alter table public.users add column if not exists account_kind text;
alter table public.users add column if not exists account_status text;
alter table public.users add column if not exists pending_email text;
alter table public.users add column if not exists pending_email_requested_at timestamptz;
alter table public.users add column if not exists email_change_completed_at timestamptz;
alter table public.users add column if not exists verification_required_at timestamptz;
alter table public.users add column if not exists email_verification_sent_at timestamptz;
alter table public.users add column if not exists email_verification_resend_count integer not null default 0;
alter table public.users add column if not exists pending_account_expires_at timestamptz;

-- Historical migrations require every user to have a tenant. Pending platform
-- accounts and public-site visitors intentionally have no platform tenant until
-- provider verification/provisioning, so the lifecycle requires this column to
-- be nullable. Existing tenant references and the foreign key are preserved.
alter table public.users alter column tenant_id drop not null;

-- Public-site customers share public.users with SaaS owners. They must never be
-- passed through platform tenant provisioning merely because tenant_id is null.
update public.users local_user
set account_kind = 'site_visitor'
where local_user.account_kind is null
  and local_user.tenant_id is null
  and exists (
    select 1 from public.tenant_site_memberships site_membership
    where site_membership.user_id = local_user.id
  )
  and not exists (
    select 1 from public.tenant_memberships staff_membership
    where staff_membership.user_id = local_user.id
  );

update public.users
set account_kind = 'platform'
where account_kind is null;

-- Preserve existing provider-confirmed accounts even if an older application
-- version did not synchronize the local verification flags. Supabase Auth is
-- the canonical verification authority; the local columns are a cache.
update public.users local_user
set email_verified = true,
    email_verified_at = coalesce(local_user.email_verified_at, auth_user.email_confirmed_at)
from auth.users auth_user
where local_user.auth_id = auth_user.id
  and auth_user.email_confirmed_at is not null
  and (
    not coalesce(local_user.email_verified, false)
    or local_user.email_verified_at is null
  );

update public.users local_user
set account_status = case
  when coalesce(local_user.email_verified, false) then 'active'
  else 'pending_verification'
end
where local_user.account_status is null;

alter table public.users alter column account_status set default 'pending_verification';
alter table public.users alter column account_status set not null;
alter table public.users alter column account_kind set default 'platform';
alter table public.users alter column account_kind set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'users_account_kind_check'
  ) then
    alter table public.users add constraint users_account_kind_check
      check (account_kind in ('platform', 'site_visitor'));
  end if;
  if not exists (
    select 1 from pg_constraint where conname = 'users_account_status_check'
  ) then
    alter table public.users add constraint users_account_status_check
      check (account_status in ('pending_verification', 'active', 'disabled', 'expired_pending'));
  end if;
  if not exists (
    select 1 from pg_constraint where conname = 'users_email_verification_resend_count_check'
  ) then
    alter table public.users add constraint users_email_verification_resend_count_check
      check (email_verification_resend_count >= 0);
  end if;
end $$;

create index if not exists users_account_status_idx
on public.users (account_status);

create index if not exists users_pending_account_expiry_idx
on public.users (pending_account_expires_at)
where account_status = 'pending_verification';

create table if not exists public.email_verification_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id integer references public.users(id) on delete set null,
  auth_id uuid references auth.users(id) on delete set null,
  email_hash text not null,
  requested_at timestamptz not null default now(),
  provider text not null default 'supabase',
  provider_message_id text,
  status text not null,
  failure_code text,
  requester_ip_hash text,
  created_at timestamptz not null default now(),
  constraint email_verification_attempts_status_check
    check (status in ('requested', 'sent', 'limited', 'failed', 'verified'))
);

create index if not exists email_verification_attempts_email_requested_idx
on public.email_verification_attempts (email_hash, requested_at desc);

create index if not exists email_verification_attempts_auth_requested_idx
on public.email_verification_attempts (auth_id, requested_at desc);

create table if not exists public.pending_account_onboarding (
  id uuid primary key default gen_random_uuid(),
  auth_id uuid not null references auth.users(id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  tenant_id integer unique references public.tenants(tenant_id) on delete set null,
  business_name text,
  business_type text,
  requested_subdomain text,
  selected_plan jsonb,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '14 days'),
  provisioned_at timestamptz,
  last_error_code text,
  constraint pending_account_onboarding_auth_unique unique (auth_id),
  constraint pending_account_onboarding_user_unique unique (user_id),
  constraint pending_account_onboarding_status_check
    check (status in ('pending', 'provisioning', 'provisioned', 'failed', 'expired')),
  constraint pending_account_onboarding_plan_object_check
    check (selected_plan is null or jsonb_typeof(selected_plan) = 'object')
);

create index if not exists pending_account_onboarding_status_expiry_idx
on public.pending_account_onboarding (status, expires_at);

create table if not exists public.password_reset_requests (
  id uuid primary key default gen_random_uuid(),
  user_id integer not null references public.users(id) on delete cascade,
  auth_id uuid not null references auth.users(id) on delete cascade,
  nonce_hash text not null unique,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz,
  processing_started_at timestamptz,
  constraint password_reset_requests_status_check
    check (status in ('pending', 'processing', 'consumed', 'expired', 'revoked')),
  constraint password_reset_requests_expiry_check check (expires_at > created_at)
);

create index if not exists password_reset_requests_user_created_idx
on public.password_reset_requests (user_id, created_at desc);

create index if not exists password_reset_requests_pending_expiry_idx
on public.password_reset_requests (expires_at)
where status = 'pending';

alter table public.email_verification_attempts enable row level security;
alter table public.pending_account_onboarding enable row level security;
alter table public.password_reset_requests enable row level security;

revoke all on public.email_verification_attempts from anon, authenticated;
revoke all on public.pending_account_onboarding from anon, authenticated;
revoke all on public.password_reset_requests from anon, authenticated;
grant select, insert, update, delete on public.email_verification_attempts to service_role;
grant select, insert, update, delete on public.pending_account_onboarding to service_role;
grant select, insert, update, delete on public.password_reset_requests to service_role;

create or replace function public.provision_verified_account(p_auth_id uuid)
returns public.users
language plpgsql
security definer
set search_path = public
as $$
declare
  account_row public.users;
  pending_row public.pending_account_onboarding;
  provisioned_tenant_id integer;
  display_name text;
  subdomain_conflict boolean := false;
begin
  select * into account_row from public.users where auth_id = p_auth_id for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'user_not_found';
  end if;
  if not coalesce(account_row.email_verified, false) then
    raise exception using errcode = 'P0001', message = 'email_verification_required';
  end if;

  if account_row.account_kind = 'site_visitor' then
    update public.users
    set account_status = 'active', pending_account_expires_at = null
    where id = account_row.id
    returning * into account_row;
    return account_row;
  end if;

  select * into pending_row
  from public.pending_account_onboarding
  where auth_id = p_auth_id
  for update;

  provisioned_tenant_id := account_row.tenant_id;
  if provisioned_tenant_id is null and pending_row.tenant_id is not null then
    provisioned_tenant_id := pending_row.tenant_id;
  end if;

  if provisioned_tenant_id is null then
    display_name := trim(concat_ws(' ', account_row.first_name, account_row.last_name));
    insert into public.tenants (brand_name, owner_name, business_type)
    values (
      coalesce(pending_row.business_name, ''),
      coalesce(display_name, ''),
      pending_row.business_type
    )
    returning tenant_id into provisioned_tenant_id;

    if pending_row.id is not null then
      update public.pending_account_onboarding
      set tenant_id = provisioned_tenant_id, status = 'provisioning', last_error_code = null
      where id = pending_row.id;
    end if;
  end if;

  update public.users
  set tenant_id = provisioned_tenant_id,
      account_status = 'active',
      pending_account_expires_at = null
  where id = account_row.id
  returning * into account_row;

  insert into public.tenant_memberships (tenant_id, user_id, auth_id, role, status)
  values (provisioned_tenant_id, account_row.id, p_auth_id, 'owner', 'active')
  on conflict (user_id, tenant_id) do update
    set auth_id = excluded.auth_id, role = 'owner', status = 'active';

  begin
    insert into public.website_settings (user_id, tenant_id, subdomain, brand)
    values (
      account_row.id,
      provisioned_tenant_id,
      nullif(pending_row.requested_subdomain, ''),
      nullif(pending_row.business_name, '')
    )
    on conflict (user_id) do update
      set tenant_id = coalesce(public.website_settings.tenant_id, excluded.tenant_id);
  exception when unique_violation then
    -- A requested public subdomain may have been claimed while verification was
    -- pending. Account activation must still succeed; the user can choose a new
    -- subdomain after login.
    subdomain_conflict := true;
    insert into public.website_settings (user_id, tenant_id, subdomain, brand)
    values (
      account_row.id,
      provisioned_tenant_id,
      null,
      nullif(pending_row.business_name, '')
    )
    on conflict (user_id) do update
      set tenant_id = coalesce(public.website_settings.tenant_id, excluded.tenant_id);
  end;

  if pending_row.id is not null then
    update public.pending_account_onboarding
    set tenant_id = provisioned_tenant_id,
        status = 'provisioned',
        provisioned_at = coalesce(provisioned_at, now()),
        last_error_code = case
          when subdomain_conflict then 'subdomain_unavailable'
          else null
        end
    where id = pending_row.id;
  end if;

  return account_row;
end;
$$;

revoke all on function public.provision_verified_account(uuid) from public, anon, authenticated;
grant execute on function public.provision_verified_account(uuid) to service_role;

create or replace function public.claim_password_reset_request(
  p_auth_id uuid,
  p_nonce_hash text,
  p_now timestamptz default now()
)
returns public.password_reset_requests
language plpgsql
security definer
set search_path = public
as $$
declare
  request_row public.password_reset_requests;
begin
  select * into request_row
  from public.password_reset_requests
  where auth_id = p_auth_id and nonce_hash = p_nonce_hash
  for update;

  if not found then
    raise exception using errcode = 'P0002', message = 'password_reset_invalid';
  end if;
  if request_row.status = 'consumed' or request_row.consumed_at is not null then
    raise exception using errcode = 'P0001', message = 'password_reset_replayed';
  end if;
  if request_row.expires_at <= p_now then
    update public.password_reset_requests
    set status = 'expired', processing_started_at = null
    where id = request_row.id
    returning * into request_row;
    return request_row;
  end if;
  if request_row.status = 'processing' then
    raise exception using errcode = 'P0001', message = 'password_reset_in_progress';
  end if;
  if request_row.status <> 'pending' then
    raise exception using errcode = 'P0002', message = 'password_reset_invalid';
  end if;

  update public.password_reset_requests
  set status = 'processing', processing_started_at = p_now
  where id = request_row.id
  returning * into request_row;
  return request_row;
end;
$$;

revoke all on function public.claim_password_reset_request(uuid, text, timestamptz)
from public, anon, authenticated;
grant execute on function public.claim_password_reset_request(uuid, text, timestamptz)
to service_role;

create or replace function public.finish_password_reset_request(
  p_request_id uuid,
  p_succeeded boolean,
  p_finished_at timestamptz default now()
)
returns public.password_reset_requests
language plpgsql
security definer
set search_path = public
as $$
declare
  request_row public.password_reset_requests;
begin
  select * into request_row
  from public.password_reset_requests
  where id = p_request_id
  for update;

  if not found or request_row.status <> 'processing' then
    raise exception using errcode = 'P0001', message = 'password_reset_state_conflict';
  end if;

  update public.password_reset_requests
  set status = case when p_succeeded then 'consumed' else 'revoked' end,
      consumed_at = case when p_succeeded then p_finished_at else null end,
      processing_started_at = null
  where id = p_request_id
  returning * into request_row;
  return request_row;
end;
$$;

revoke all on function public.finish_password_reset_request(uuid, boolean, timestamptz)
from public, anon, authenticated;
grant execute on function public.finish_password_reset_request(uuid, boolean, timestamptz)
to service_role;

notify pgrst, 'reload schema';
commit;
