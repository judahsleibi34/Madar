alter table public.ecommerce_tags
  drop constraint if exists ecommerce_tags_status_check;
alter table public.ecommerce_tags
  add constraint ecommerce_tags_status_check
  check (status in ('draft', 'active', 'inactive', 'archived'));

alter table public.ecommerce_categories
  drop constraint if exists ecommerce_categories_status_check;
alter table public.ecommerce_categories
  add constraint ecommerce_categories_status_check
  check (status in ('draft', 'active', 'inactive', 'archived'));

alter table public.ecommerce_products
  drop constraint if exists ecommerce_products_status_check;
alter table public.ecommerce_products
  add constraint ecommerce_products_status_check
  check (status in ('draft', 'active', 'inactive', 'archived'));
