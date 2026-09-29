begin;

create table public.ecommerce_product_categories (
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  category_id uuid not null,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  primary key (product_id, category_id),
  constraint ecommerce_product_categories_sort_order_check
    check (sort_order between 0 and 1000000),
  constraint ecommerce_product_categories_product_tenant_fk
    foreign key (tenant_id, product_id)
    references public.ecommerce_products(tenant_id, id) on delete cascade,
  constraint ecommerce_product_categories_category_tenant_fk
    foreign key (tenant_id, category_id)
    references public.ecommerce_categories(tenant_id, id) on delete cascade
);

insert into public.ecommerce_product_categories (
  tenant_id,
  product_id,
  category_id,
  sort_order
)
select
  product.tenant_id,
  product.id,
  product.category_id,
  0
from public.ecommerce_products product
where product.category_id is not null
on conflict (product_id, category_id) do nothing;

create index ecommerce_product_categories_category_idx
  on public.ecommerce_product_categories (tenant_id, category_id, product_id);

create index ecommerce_product_categories_product_order_idx
  on public.ecommerce_product_categories (tenant_id, product_id, sort_order);

alter table public.ecommerce_product_categories enable row level security;
revoke all on table public.ecommerce_product_categories from anon, authenticated;
grant select, insert, update, delete on table public.ecommerce_product_categories to service_role;

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
    raise exception using
      errcode = 'P0001',
      message = 'migration_111_schema_state_missing';
  end if;

  if v_schema_version <> 110 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_111_expected_schema_110_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 111,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;
