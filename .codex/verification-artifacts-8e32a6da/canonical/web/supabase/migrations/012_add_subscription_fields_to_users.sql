alter table public.users
add column if not exists subscription_type text not null default '';

alter table public.users
add column if not exists payment_status text not null default '';

notify pgrst, 'reload schema';