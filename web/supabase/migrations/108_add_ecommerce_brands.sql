begin;

create table public.ecommerce_brands (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  name text not null,
  slug text not null,
  image_url text,
  status text not null default 'active',
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_brands_name_check check (name = btrim(name) and char_length(name) between 1 and 160),
  constraint ecommerce_brands_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint ecommerce_brands_status_check check (status in ('active', 'inactive')),
  constraint ecommerce_brands_image_url_check check (
    image_url is null
    or (
      image_url = btrim(image_url)
      and char_length(image_url) between 1 and 2048
      and (
        image_url ~ '^/uploads/tenant_[1-9][0-9]*/builder_assets/[a-f0-9]{32}[.](png|jpg|webp)$'
        or image_url ~* '^https://'
      )
    )
  ),
  unique (tenant_id, slug),
  unique (tenant_id, id)
);

alter table public.ecommerce_products
  add column brand_id uuid;

alter table public.ecommerce_products
  add constraint ecommerce_products_brand_tenant_fk foreign key (tenant_id, brand_id)
    references public.ecommerce_brands(tenant_id, id) on delete restrict;

insert into public.ecommerce_brands (tenant_id, name, slug)
select distinct
  product.tenant_id,
  btrim(product.brand),
  case
    when btrim(regexp_replace(lower(btrim(product.brand)), '[^a-z0-9]+', '-', 'g'), '-') = ''
      then 'brand-' || substr(md5(product.tenant_id::text || ':' || lower(btrim(product.brand))), 1, 8)
    else left(btrim(regexp_replace(lower(btrim(product.brand)), '[^a-z0-9]+', '-', 'g'), '-'), 70)
      || '-' || substr(md5(product.tenant_id::text || ':' || lower(btrim(product.brand))), 1, 8)
  end
from public.ecommerce_products product
where btrim(product.brand) <> ''
on conflict (tenant_id, slug) do nothing;

update public.ecommerce_products product
set brand_id = brand.id
from public.ecommerce_brands brand
where brand.tenant_id = product.tenant_id
  and lower(brand.name) = lower(btrim(product.brand))
  and product.brand_id is null;

create index ecommerce_brands_tenant_idx on public.ecommerce_brands (tenant_id, name, created_at);
create index ecommerce_products_brand_idx on public.ecommerce_products (tenant_id, brand_id);

alter table public.ecommerce_brands enable row level security;
revoke all on table public.ecommerce_brands from anon, authenticated;
grant select, insert, update, delete on table public.ecommerce_brands to service_role;

create trigger set_ecommerce_brands_updated_at before update on public.ecommerce_brands
for each row execute function public.set_updated_at();

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
      message = 'migration_108_schema_state_missing';
  end if;

  if v_schema_version <> 107 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_108_expected_schema_107_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 108,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;