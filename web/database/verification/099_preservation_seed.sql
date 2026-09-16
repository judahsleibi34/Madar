create table public.rehearsal_099_snapshot as
select 'variants' as kind, coalesce(jsonb_agg(to_jsonb(t) order by id),'[]') as data from public.ecommerce_product_variants t
union all select 'items',coalesce(jsonb_agg(to_jsonb(t) order by id),'[]') from public.ecommerce_order_items t
union all select 'movements',coalesce(jsonb_agg(to_jsonb(t) order by id),'[]') from public.ecommerce_inventory_movements t
union all select 'products',coalesce(jsonb_agg(to_jsonb(t) order by id),'[]') from public.ecommerce_products t;
