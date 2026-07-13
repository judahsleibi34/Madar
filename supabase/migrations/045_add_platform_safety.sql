-- Project concurrency, billing event idempotency, and last-admin protection.
begin;

create extension if not exists pgcrypto;

alter table public.builder_projects add column if not exists draft_revision bigint not null default 0;
alter table public.builder_projects add column if not exists published_revision bigint;
alter table public.builder_projects add column if not exists schema_version integer not null default 1;
alter table public.features add column if not exists billing_state_changed_at timestamptz;

-- Existing published snapshots predate explicit draft/published revisions. A
-- revision of zero is the safe baseline for those snapshots and avoids a null
-- published revision after upgrading a live project.
update public.builder_projects
set published_revision = draft_revision
where published_schema is not null
  and published_revision is null;

update public.features
set billing_state_changed_at = coalesce(updated_at, created_at, now())
where billing_state_changed_at is null;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'builder_projects_draft_revision_check') then
    alter table public.builder_projects add constraint builder_projects_draft_revision_check check (draft_revision >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'builder_projects_published_revision_check') then
    alter table public.builder_projects add constraint builder_projects_published_revision_check
      check (published_revision is null or published_revision >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'builder_projects_schema_version_check') then
    alter table public.builder_projects add constraint builder_projects_schema_version_check check (schema_version >= 1);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'users_user_type_check') then
    alter table public.users add constraint users_user_type_check check (user_type in ('admin', 'user'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'features_payment_status_check_v2') then
    alter table public.features add constraint features_payment_status_check_v2
      check (payment_status in ('pending', 'active', 'past_due', 'canceled', 'expired')) not valid;
  end if;
end $$;

create table if not exists public.billing_webhook_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  provider_event_id text not null,
  -- Keep replay protection even if a tenant is later removed. Feature writes
  -- still enforce tenant existence through public.features.
  tenant_id integer not null,
  event_type text not null,
  status text not null default 'received',
  payload_hash text not null,
  provider_occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  failure_code text,
  retry_count integer not null default 0,
  constraint billing_webhook_events_provider_event_unique unique (provider, provider_event_id),
  constraint billing_webhook_events_status_check check (status in ('received', 'processed', 'failed', 'ignored')),
  constraint billing_webhook_events_retry_count_check check (retry_count >= 0)
);

create index if not exists billing_webhook_events_status_received_idx
on public.billing_webhook_events (status, received_at);

create index if not exists features_billing_state_changed_idx
on public.features (tenant_id, billing_state_changed_at desc);

alter table public.billing_webhook_events enable row level security;
revoke all on public.billing_webhook_events from anon, authenticated;
grant select, insert, update, delete on public.billing_webhook_events to service_role;

create or replace function public.publish_builder_project_atomic(
  p_project_id uuid,
  p_tenant_id integer,
  p_expected_revision bigint,
  p_published_at timestamptz,
  p_schema_version integer default 1,
  p_require_active_entitlement boolean default false
)
returns public.builder_projects
language plpgsql
security definer
set search_path = public
as $$
declare
  current_project public.builder_projects;
begin
  select * into current_project
  from public.builder_projects
  where id = p_project_id and tenant_id = p_tenant_id
  for update;

  if not found or current_project.status = 'archived' then
    raise exception using errcode = 'P0002', message = 'builder_project_not_found';
  end if;
  if current_project.draft_revision <> p_expected_revision then
    raise exception using errcode = 'P0001', message = 'project_revision_conflict';
  end if;
  if jsonb_typeof(current_project.draft_schema) <> 'object' then
    raise exception using errcode = 'P0001', message = 'publish_validation_failed';
  end if;
  if p_require_active_entitlement and not exists (
    select 1
    from public.features feature
    where feature.tenant_id = p_tenant_id
      and feature.payment_status = 'active'
      and (
        feature.subscription_type = 'full_platform'
        or (
          feature.subscription_type = 'individual_builder'
          and feature.builder_type = 'website'
        )
      )
  ) then
    raise exception using errcode = 'P0001', message = 'entitlement_inactive';
  end if;

  update public.builder_projects
  set published_schema = current_project.draft_schema,
      published_version = current_project.published_version + 1,
      published_revision = current_project.draft_revision,
      schema_version = p_schema_version,
      last_published_at = p_published_at,
      status = 'published'
  where id = p_project_id and tenant_id = p_tenant_id
  returning * into current_project;

  return current_project;
end;
$$;

revoke all on function public.publish_builder_project_atomic(uuid, integer, bigint, timestamptz, integer, boolean) from public, anon, authenticated;
grant execute on function public.publish_builder_project_atomic(uuid, integer, bigint, timestamptz, integer, boolean) to service_role;

alter table public.features drop constraint if exists features_full_platform_plan_check;
alter table public.features add constraint features_full_platform_plan_check
  check (
    subscription_type <> 'full_platform'
    or plan in ('starter', 'pro', 'business', 'cms', 'forms_data', 'cms_plus', 'complete')
  ) not valid;

create or replace function public.apply_billing_webhook_event(
  p_provider text,
  p_provider_event_id text,
  p_event_type text,
  p_tenant_id integer,
  p_subscription_type text,
  p_plan text,
  p_builder_type text,
  p_payment_status text,
  p_payload_hash text,
  p_provider_occurred_at timestamptz
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  existing_event public.billing_webhook_events;
  event_row public.billing_webhook_events;
  feature_row public.features;
begin
  -- Serialize all events that mutate one tenant/feature slot. This makes two
  -- different concurrently-delivered event IDs obey provider occurrence order
  -- and prevents a create race against the partial feature uniqueness indexes.
  perform pg_advisory_xact_lock(hashtext(concat_ws(
    ':', 'madar-billing-feature', p_tenant_id, p_subscription_type,
    coalesce(p_builder_type, 'full-platform')
  )));

  insert into public.billing_webhook_events (
    provider, provider_event_id, tenant_id, event_type, status, payload_hash,
    provider_occurred_at
  ) values (
    p_provider, p_provider_event_id, p_tenant_id, p_event_type, 'received',
    p_payload_hash, p_provider_occurred_at
  )
  on conflict (provider, provider_event_id) do nothing
  returning * into event_row;

  if not found then
    select * into existing_event
    from public.billing_webhook_events
    where provider = p_provider and provider_event_id = p_provider_event_id
    for update;

    if not found
      or existing_event.payload_hash <> p_payload_hash
      or existing_event.tenant_id <> p_tenant_id
    then
      raise exception using errcode = 'P0001', message = 'idempotency_conflict';
    end if;
    select * into feature_row
    from public.features
    where tenant_id = existing_event.tenant_id
      and subscription_type = p_subscription_type
      and builder_type is not distinct from p_builder_type
    order by updated_at desc, id desc
    limit 1;
    return jsonb_build_object(
      'duplicate', true,
      'event_id', existing_event.id,
      'status', existing_event.status,
      'feature', to_jsonb(feature_row)
    );
  end if;

  select * into feature_row
  from public.features
  where tenant_id = p_tenant_id
    and subscription_type = p_subscription_type
    and builder_type is not distinct from p_builder_type
  order by updated_at desc, id desc
  limit 1
  for update;

  if found
    and feature_row.billing_state_changed_at is not null
    and feature_row.billing_state_changed_at > p_provider_occurred_at
  then
    update public.billing_webhook_events
    set status = 'ignored',
        processed_at = now(),
        failure_code = 'stale_event'
    where id = event_row.id;
    return jsonb_build_object(
      'duplicate', false,
      'ignored', true,
      'event_id', event_row.id,
      'status', 'ignored',
      'feature', to_jsonb(feature_row)
    );
  end if;

  if found then
    update public.features
    set plan = p_plan,
        payment_status = p_payment_status,
        billing_state_changed_at = p_provider_occurred_at,
        updated_at = now()
    where id = feature_row.id
    returning * into feature_row;
  else
    insert into public.features (
      tenant_id, subscription_type, plan, builder_type, payment_status, billing_state_changed_at
    ) values (
      p_tenant_id, p_subscription_type, p_plan, p_builder_type, p_payment_status, p_provider_occurred_at
    ) returning * into feature_row;
  end if;

  update public.billing_webhook_events
  set status = 'processed', processed_at = now()
  where id = event_row.id;

  return jsonb_build_object(
    'duplicate', false,
    'event_id', event_row.id,
    'status', 'processed',
    'feature', to_jsonb(feature_row)
  );
end;
$$;

revoke all on function public.apply_billing_webhook_event(text, text, text, integer, text, text, text, text, text, timestamptz) from public, anon, authenticated;
grant execute on function public.apply_billing_webhook_event(text, text, text, integer, text, text, text, text, text, timestamptz) to service_role;

create or replace function public.protect_last_system_admin()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  other_admins integer;
begin
  if old.user_type <> 'admin' or old.account_status <> 'active' then
    if tg_op = 'DELETE' then return old; end if;
    return new;
  end if;
  if tg_op = 'UPDATE'
    and new.user_type = 'admin'
    and new.account_status = 'active'
  then
    return new;
  end if;

  perform pg_advisory_xact_lock(hashtext('madar:last-system-admin'));
  select count(*) into other_admins
  from public.users
  where user_type = 'admin'
    and account_status = 'active'
    and id <> old.id;
  if other_admins = 0 then
    raise exception using errcode = 'P0001', message = 'last_system_admin_required';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;

create or replace function public.admin_update_user_type_safely(
  p_user_id integer,
  p_new_user_type text,
  p_required_at timestamptz default now()
)
returns public.users
language plpgsql
security definer
set search_path = public
as $$
declare
  target_user public.users;
begin
  if p_new_user_type not in ('admin', 'user') then
    raise exception using errcode = 'P0001', message = 'invalid_user_type';
  end if;
  select * into target_user from public.users where id = p_user_id for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'user_not_found';
  end if;
  if p_new_user_type = 'admin' then
    if target_user.account_status <> 'active' then
      raise exception using errcode = 'P0001', message = 'account_inactive';
    end if;
    if not coalesce(target_user.email_verified, false)
      or not exists (
        select 1 from auth.users auth_user
        where auth_user.id = target_user.auth_id
          and auth_user.email_confirmed_at is not null
      )
    then
      raise exception using errcode = 'P0001', message = 'email_verification_required';
    end if;
    if target_user.auth_id is null then
      raise exception using errcode = 'P0001', message = 'user_auth_identity_required';
    end if;
    insert into public.user_security_settings (
      user_id, auth_id, mfa_required, mfa_required_at
    ) values (
      target_user.id, target_user.auth_id, true, p_required_at
    )
    on conflict (user_id) do update
      set auth_id = excluded.auth_id,
          mfa_required = true,
          mfa_required_at = excluded.mfa_required_at,
          updated_at = now();
  end if;
  update public.users set user_type = p_new_user_type where id = p_user_id returning * into target_user;
  return target_user;
end;
$$;

revoke all on function public.admin_update_user_type_safely(integer, text, timestamptz) from public, anon, authenticated;
grant execute on function public.admin_update_user_type_safely(integer, text, timestamptz) to service_role;

drop trigger if exists protect_last_system_admin_trigger on public.users;
create trigger protect_last_system_admin_trigger
before update of user_type, account_status or delete on public.users
for each row execute function public.protect_last_system_admin();

notify pgrst, 'reload schema';
commit;
