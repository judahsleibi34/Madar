-- Normalize sensitive public-schema ACLs to the backend-mediated access model.
-- This migration changes catalog privileges only; it does not rewrite table data.

begin;

do $acl$
declare
  table_name text;
  object_owner text;
  row_security_enabled boolean;
  sensitive_tables constant text[] := array[
    'users', 'contacts', 'tenants', 'tenant_memberships',
    'tenant_site_memberships', 'tenant_site_project_roles',
    'tenant_site_project_role_assignments', 'website_settings', 'features',
    'user_security_settings', 'builder_projects', 'builder_form_submissions',
    'builder_reservations', 'builder_assets', 'builder_asset_references',
    'storage_accounts', 'storage_reservations', 'storage_objects', 'audit_logs',
    'admin_account_access_requests', 'admin_account_access_sessions',
    'notification_events', 'user_notifications', 'web_push_subscriptions',
    'notification_outbox', 'ai_usage_daily', 'billing_webhook_events',
    'email_verification_attempts', 'pending_account_onboarding',
    'password_reset_requests', 'calendars', 'calendar_memberships',
    'calendar_events', 'calendar_event_attendees', 'calendar_event_reminders',
    'calendar_event_changes', 'calendar_tasks', 'calendar_task_dependencies',
    'calendar_task_reminders', 'calendar_sync_connections',
    'calendar_sync_conflicts', 'calendar_invitation_reviews',
    'calendar_oauth_states'
  ];
begin
  foreach table_name in array sensitive_tables loop
    select pg_get_userbyid(c.relowner), c.relrowsecurity
      into object_owner, row_security_enabled
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public'
       and c.relname = table_name
       and c.relkind in ('r', 'p');

    if object_owner is null then
      raise exception 'Required sensitive table public.% is missing', table_name;
    end if;
    if object_owner <> 'postgres' then
      raise exception 'Unexpected owner for public.%: %', table_name, object_owner;
    end if;
    if not row_security_enabled then
      raise exception 'Row-level security is disabled for public.%', table_name;
    end if;

    execute format(
      'revoke all privileges on table public.%I from public, anon, authenticated, service_role',
      table_name
    );
    execute format(
      'grant select, insert, update, delete on table public.%I to service_role',
      table_name
    );
  end loop;
end
$acl$;

-- These reads are intentionally retained for existing RLS-filtered browser paths.
grant select on table
  public.users,
  public.tenants,
  public.tenant_memberships,
  public.website_settings,
  public.builder_projects,
  public.builder_form_submissions,
  public.features
to authenticated;

-- Normalize only sequences owned by columns of the sensitive tables above.
do $sequences$
declare
  sequence_record record;
begin
  for sequence_record in
    select distinct
      ns.nspname as schema_name,
      seq.relname as sequence_name,
      pg_get_userbyid(seq.relowner) as owner_name
    from pg_class seq
    join pg_namespace ns on ns.oid = seq.relnamespace
    join pg_depend dependency
      on dependency.objid = seq.oid
     and dependency.deptype in ('a', 'i')
    join pg_class parent on parent.oid = dependency.refobjid
    join pg_namespace parent_ns on parent_ns.oid = parent.relnamespace
    where seq.relkind = 'S'
      and ns.nspname = 'public'
      and parent_ns.nspname = 'public'
      and parent.relname = any (array[
        'users', 'contacts', 'tenants', 'tenant_memberships',
        'tenant_site_memberships', 'tenant_site_project_roles',
        'tenant_site_project_role_assignments', 'website_settings', 'features',
        'user_security_settings', 'builder_projects', 'builder_form_submissions',
        'builder_reservations', 'builder_assets', 'builder_asset_references',
        'storage_accounts', 'storage_reservations', 'storage_objects', 'audit_logs',
        'admin_account_access_requests', 'admin_account_access_sessions',
        'notification_events', 'user_notifications', 'web_push_subscriptions',
        'notification_outbox', 'ai_usage_daily', 'billing_webhook_events',
        'email_verification_attempts', 'pending_account_onboarding',
        'password_reset_requests', 'calendars', 'calendar_memberships',
        'calendar_events', 'calendar_event_attendees', 'calendar_event_reminders',
        'calendar_event_changes', 'calendar_tasks', 'calendar_task_dependencies',
        'calendar_task_reminders', 'calendar_sync_connections',
        'calendar_sync_conflicts', 'calendar_invitation_reviews',
        'calendar_oauth_states'
      ]::text[])
  loop
    if sequence_record.owner_name <> 'postgres' then
      raise exception 'Unexpected owner for %.%: %',
        sequence_record.schema_name, sequence_record.sequence_name, sequence_record.owner_name;
    end if;
    execute format(
      'revoke all privileges on sequence %I.%I from public, anon, authenticated, service_role',
      sequence_record.schema_name,
      sequence_record.sequence_name
    );
    execute format(
      'grant usage, select on sequence %I.%I to service_role',
      sequence_record.schema_name,
      sequence_record.sequence_name
    );
  end loop;
end
$sequences$;

-- Protected functions are backend-only. Trigger functions are included so their
-- direct invocation cannot become a browser-facing API. The retired publish RPC
-- intentionally receives no replacement service-role EXECUTE grant.
do $functions$
declare
  function_record record;
  protected_names constant text[] := array[
    'set_updated_at', 'get_tables', 'get_columns',
    'touch_ai_usage_daily_updated_at', 'increment_ai_usage_daily',
    'reserve_ai_usage_daily', 'publish_builder_project_atomic',
    'publish_validated_builder_project_atomic', 'apply_billing_webhook_event',
    'protect_last_system_admin', 'admin_update_user_type_safely',
    'provision_verified_account', 'claim_password_reset_request',
    'finish_password_reset_request', 'validate_website_settings_published_project',
    'claim_notification_outbox', 'finish_notification_outbox',
    'create_builder_reservation_safe', 'cancel_builder_reservation_safe',
    'create_builder_form_submission_safe', 'reserve_storage_bytes',
    'finish_storage_reservation', 'release_storage_object',
    'assign_tenant_site_project_role', 'consume_calendar_oauth_state'
  ];
begin
  for function_record in
    select
      p.oid::regprocedure::text as signature,
      p.proname,
      pg_get_userbyid(p.proowner) as owner_name
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname = any (protected_names)
    order by p.oid
  loop
    if function_record.owner_name <> 'postgres' then
      raise exception 'Unexpected owner for function %: %',
        function_record.signature, function_record.owner_name;
    end if;
    execute format(
      'revoke all privileges on function %s from public, anon, authenticated, service_role',
      function_record.signature
    );
    execute format('alter function %s set search_path = public', function_record.signature);
    if function_record.proname <> 'publish_builder_project_atomic' then
      execute format('grant execute on function %s to service_role', function_record.signature);
    end if;
  end loop;

  if not exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname = 'consume_calendar_oauth_state'
  ) then
    raise exception 'Migration 065 function public.consume_calendar_oauth_state is missing';
  end if;
end
$functions$;

-- Supabase production objects are owned by postgres. Correct that owner's
-- future-object defaults so broad platform defaults cannot recreate ACL drift.
alter default privileges for role postgres in schema public
  revoke all privileges on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant select, insert, update, delete on tables to service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on sequences from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant usage, select on sequences to service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on functions from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  grant execute on functions to service_role;

notify pgrst, 'reload schema';

commit;
