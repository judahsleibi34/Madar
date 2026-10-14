begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_146_schema_state_missing';
  end if;
  if v_schema_version <> 145 then
    raise exception using errcode = 'P0001',
      message = format('migration_146_expected_schema_145_got_%s', v_schema_version);
  end if;
end;
$$;

-- launch_2026 was prepared but never opened for sales. Its Commerce amount is
-- superseded, so it may not be opened if any sales window was ever recorded.
do $$
begin
  if not exists(select 1 from public.commercial_price_books where id='launch_2026') then
    raise exception using errcode='P0001',message='migration_146_launch_2026_missing';
  end if;
  if exists(select 1 from public.commercial_price_books
            where id='launch_2026' and sales_start_at is not null) then
    raise exception using errcode='P0001',message='migration_146_launch_2026_already_activated';
  end if;
end;
$$;

-- Approved revised launch price book. Prepared only: a governed launch records
-- sales_start_at; this migration opens nothing for new sales.
insert into public.commercial_price_books(
  id,version,effective_from,currency,billing_interval,standalone_minor,bundle_minor
) values (
  'launch_2026_v2','2026-10-14','2026-10-14T00:00:00Z','USD','month',
  '{"forms":1500,"website":2000,"ecommerce":2500}','{"2":3000,"3":4000}'
);

-- The superseded book stays readable for any historical module_basis evidence
-- but can never become available for sales.
create function public.guard_retired_price_book146()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.id='launch_2026' and new.sales_start_at is not null then
    raise exception using errcode='42501',message='commercial_price_book_retired';
  end if;
  return new;
end;
$$;

create trigger retired_price_book146
before update on public.commercial_price_books
for each row execute function public.guard_retired_price_book146();

revoke all on function public.guard_retired_price_book146()
  from public,anon,authenticated,service_role;

update public.application_schema_state
set schema_version=146,applied_at=now()
where contract_key='core';

notify pgrst,'reload schema';
commit;
