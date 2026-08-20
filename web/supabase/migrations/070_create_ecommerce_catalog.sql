-- Tenant-scoped ecommerce catalog with translations and category hierarchy.
begin;

create extension if not exists pgcrypto;

create table if not exists public.ecommerce_tags (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  slug text not null,
  translations jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_tags_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint ecommerce_tags_translations_check check (jsonb_typeof(translations) = 'object'),
  constraint ecommerce_tags_status_check check (status in ('draft', 'active', 'archived')),
  unique (tenant_id, slug),
  unique (tenant_id, id)
);

create table if not exists public.ecommerce_categories (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  parent_id uuid,
  slug text not null,
  translations jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  sort_order integer not null default 0,
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_categories_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint ecommerce_categories_translations_check check (jsonb_typeof(translations) = 'object'),
  constraint ecommerce_categories_status_check check (status in ('draft', 'active', 'archived')),
  constraint ecommerce_categories_sort_order_check check (sort_order >= 0),
  unique (tenant_id, slug),
  unique (tenant_id, id),
  constraint ecommerce_categories_parent_tenant_fk foreign key (tenant_id, parent_id)
    references public.ecommerce_categories(tenant_id, id) on delete restrict
);

create table if not exists public.ecommerce_products (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  category_id uuid,
  sku text not null,
  barcode text,
  slug text not null,
  translations jsonb not null default '{}'::jsonb,
  status text not null default 'draft',
  product_type text not null default 'physical',
  brand text not null default '',
  price numeric(14, 2) not null default 0,
  compare_at_price numeric(14, 2),
  cost_price numeric(14, 2),
  currency text not null default 'USD',
  track_inventory boolean not null default true,
  inventory_quantity integer not null default 0,
  low_stock_threshold integer not null default 5,
  allow_backorder boolean not null default false,
  images jsonb not null default '[]'::jsonb,
  weight numeric(12, 3),
  weight_unit text not null default 'kg',
  requires_shipping boolean not null default true,
  taxable boolean not null default true,
  seo_title text not null default '',
  seo_description text not null default '',
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_products_sku_check check (char_length(trim(sku)) between 1 and 120),
  constraint ecommerce_products_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint ecommerce_products_translations_check check (jsonb_typeof(translations) = 'object'),
  constraint ecommerce_products_status_check check (status in ('draft', 'active', 'archived')),
  constraint ecommerce_products_type_check check (product_type in ('physical', 'digital', 'service')),
  constraint ecommerce_products_price_check check (price >= 0 and (compare_at_price is null or compare_at_price >= 0) and (cost_price is null or cost_price >= 0)),
  constraint ecommerce_products_currency_check check (currency ~ '^[A-Z]{3}$'),
  constraint ecommerce_products_inventory_check check (inventory_quantity >= 0 and low_stock_threshold >= 0),
  constraint ecommerce_products_images_check check (jsonb_typeof(images) = 'array'),
  constraint ecommerce_products_weight_check check (weight is null or weight >= 0),
  constraint ecommerce_products_weight_unit_check check (weight_unit in ('g', 'kg', 'lb', 'oz')),
  unique (tenant_id, sku),
  unique (tenant_id, slug),
  unique (tenant_id, id),
  constraint ecommerce_products_category_tenant_fk foreign key (tenant_id, category_id)
    references public.ecommerce_categories(tenant_id, id) on delete restrict
);

create table if not exists public.ecommerce_product_tags (
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  tag_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (product_id, tag_id),
  constraint ecommerce_product_tags_product_tenant_fk foreign key (tenant_id, product_id)
    references public.ecommerce_products(tenant_id, id) on delete cascade,
  constraint ecommerce_product_tags_tag_tenant_fk foreign key (tenant_id, tag_id)
    references public.ecommerce_tags(tenant_id, id) on delete cascade
);

create index if not exists ecommerce_tags_tenant_idx on public.ecommerce_tags (tenant_id, status, created_at desc);
create index if not exists ecommerce_categories_tenant_idx on public.ecommerce_categories (tenant_id, parent_id, sort_order, created_at);
create index if not exists ecommerce_products_tenant_idx on public.ecommerce_products (tenant_id, status, created_at desc);
create index if not exists ecommerce_products_category_idx on public.ecommerce_products (tenant_id, category_id);
create index if not exists ecommerce_product_tags_tag_idx on public.ecommerce_product_tags (tenant_id, tag_id);

do $$
declare table_name text;
begin
  foreach table_name in array array[
    'ecommerce_tags', 'ecommerce_categories', 'ecommerce_products', 'ecommerce_product_tags'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on table public.%I from anon, authenticated', table_name);
    execute format('grant select, insert, update, delete on table public.%I to service_role', table_name);
  end loop;
end $$;

drop trigger if exists set_ecommerce_tags_updated_at on public.ecommerce_tags;
create trigger set_ecommerce_tags_updated_at before update on public.ecommerce_tags
for each row execute function public.set_updated_at();
drop trigger if exists set_ecommerce_categories_updated_at on public.ecommerce_categories;
create trigger set_ecommerce_categories_updated_at before update on public.ecommerce_categories
for each row execute function public.set_updated_at();
drop trigger if exists set_ecommerce_products_updated_at on public.ecommerce_products;
create trigger set_ecommerce_products_updated_at before update on public.ecommerce_products
for each row execute function public.set_updated_at();

notify pgrst, 'reload schema';
commit;
