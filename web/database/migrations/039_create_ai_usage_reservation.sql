-- ============================================================
-- Atomic AI daily usage reservation
-- ============================================================

begin;

create or replace function public.reserve_ai_usage_daily(
  p_user_id integer,
  p_tenant_id integer default null,
  p_usage_date date default current_date,
  p_message_limit integer default 0,
  p_code_generation_limit integer default 0,
  p_message_delta integer default 1,
  p_code_generation_delta integer default 0
)
returns table (
  accepted boolean,
  message_count integer,
  code_generation_count integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_usage_date date := coalesce(p_usage_date, current_date);
  v_message_delta integer := greatest(coalesce(p_message_delta, 0), 0);
  v_code_generation_delta integer := greatest(coalesce(p_code_generation_delta, 0), 0);
  v_message_limit integer := coalesce(p_message_limit, 0);
  v_code_generation_limit integer := coalesce(p_code_generation_limit, 0);
begin
  insert into public.ai_usage_daily (
    user_id,
    tenant_id,
    usage_date,
    message_count,
    code_generation_count
  )
  values (
    p_user_id,
    p_tenant_id,
    v_usage_date,
    0,
    0
  )
  on conflict (user_id, usage_date) do nothing;

  return query
  update public.ai_usage_daily
  set
    tenant_id = coalesce(p_tenant_id, public.ai_usage_daily.tenant_id),
    message_count = public.ai_usage_daily.message_count + v_message_delta,
    code_generation_count = public.ai_usage_daily.code_generation_count + v_code_generation_delta
  where
    public.ai_usage_daily.user_id = p_user_id
    and public.ai_usage_daily.usage_date = v_usage_date
    and public.ai_usage_daily.message_count + v_message_delta <= v_message_limit
    and public.ai_usage_daily.code_generation_count + v_code_generation_delta <= v_code_generation_limit
  returning
    true,
    public.ai_usage_daily.message_count,
    public.ai_usage_daily.code_generation_count;

  if not found then
    return query
    select
      false,
      public.ai_usage_daily.message_count,
      public.ai_usage_daily.code_generation_count
    from public.ai_usage_daily
    where
      public.ai_usage_daily.user_id = p_user_id
      and public.ai_usage_daily.usage_date = v_usage_date
    limit 1;
  end if;
end;
$$;

revoke all on function public.reserve_ai_usage_daily(integer, integer, date, integer, integer, integer, integer) from anon;
revoke all on function public.reserve_ai_usage_daily(integer, integer, date, integer, integer, integer, integer) from authenticated;
grant execute on function public.reserve_ai_usage_daily(integer, integer, date, integer, integer, integer, integer) to service_role;

notify pgrst, 'reload schema';

commit;
