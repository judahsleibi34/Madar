-- Atomic tenant/user storage reservations and durable object accounting.
begin;
create extension if not exists pgcrypto;
create table if not exists public.storage_accounts (
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  scope_key text not null,
  user_id integer references public.users(id) on delete cascade,
  used_bytes bigint not null default 0,
  reserved_bytes bigint not null default 0,
  quota_bytes bigint not null,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, scope_key),
  constraint storage_accounts_nonnegative_check check (used_bytes >= 0 and reserved_bytes >= 0 and quota_bytes > 0),
  constraint storage_accounts_scope_check check (scope_key = 'tenant' or scope_key ~ '^user:[1-9][0-9]*$')
);
create table if not exists public.storage_reservations (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer references public.users(id) on delete cascade,
  category text not null,
  bytes bigint not null check (bytes > 0),
  status text not null default 'reserved' check (status in ('reserved', 'committed', 'released', 'expired')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '1 hour',
  finished_at timestamptz
);
create table if not exists public.storage_objects (
  id uuid primary key default gen_random_uuid(),
  reservation_id uuid unique references public.storage_reservations(id) on delete set null,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer references public.users(id) on delete set null,
  category text not null,
  storage_key text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  sha256 text check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),
  status text not null default 'active' check (status in ('active', 'deleted')),
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  retention_until timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (tenant_id, category, storage_key)
);
create index if not exists storage_reservations_pending_idx on public.storage_reservations (status, expires_at);
create index if not exists storage_objects_retention_idx on public.storage_objects (category, status, retention_until);

create or replace function public.reserve_storage_bytes(p_tenant_id integer, p_user_id integer, p_category text, p_bytes bigint, p_tenant_quota bigint, p_user_quota bigint default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare reservation_id uuid; tenant_row public.storage_accounts; user_row public.storage_accounts;
begin
  if p_bytes <= 0 or p_tenant_quota <= 0 or p_category !~ '^[a-z][a-z0-9_]{1,49}$' then raise exception using errcode='P0001', message='storage_reservation_invalid'; end if;
  insert into public.storage_accounts(tenant_id,scope_key,quota_bytes) values(p_tenant_id,'tenant',p_tenant_quota)
  on conflict(tenant_id,scope_key) do update set quota_bytes=excluded.quota_bytes returning * into tenant_row;
  if tenant_row.used_bytes + tenant_row.reserved_bytes + p_bytes > tenant_row.quota_bytes then raise exception using errcode='P0001', message='tenant_storage_quota_exceeded'; end if;
  update public.storage_accounts set reserved_bytes=reserved_bytes+p_bytes, updated_at=now() where tenant_id=p_tenant_id and scope_key='tenant';
  if p_user_id is not null and p_user_quota is not null and p_user_quota > 0 then
    insert into public.storage_accounts(tenant_id,scope_key,user_id,quota_bytes) values(p_tenant_id,'user:'||p_user_id,p_user_id,p_user_quota)
    on conflict(tenant_id,scope_key) do update set quota_bytes=excluded.quota_bytes returning * into user_row;
    if user_row.used_bytes + user_row.reserved_bytes + p_bytes > user_row.quota_bytes then raise exception using errcode='P0001', message='user_storage_quota_exceeded'; end if;
    update public.storage_accounts set reserved_bytes=reserved_bytes+p_bytes, updated_at=now() where tenant_id=p_tenant_id and scope_key='user:'||p_user_id;
  end if;
  insert into public.storage_reservations(tenant_id,user_id,category,bytes) values(p_tenant_id,p_user_id,p_category,p_bytes) returning id into reservation_id;
  return reservation_id;
end; $$;

create or replace function public.finish_storage_reservation(p_reservation_id uuid, p_succeeded boolean, p_storage_key text default null, p_sha256 text default null, p_retention_until timestamptz default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare item public.storage_reservations; object_id uuid;
begin
  select * into item from public.storage_reservations where id=p_reservation_id for update;
  if not found or item.status <> 'reserved' then raise exception using errcode='P0001', message='storage_reservation_state_conflict'; end if;
  update public.storage_accounts set reserved_bytes=greatest(0,reserved_bytes-item.bytes), used_bytes=used_bytes+case when p_succeeded then item.bytes else 0 end, updated_at=now() where tenant_id=item.tenant_id and scope_key in ('tenant', 'user:'||coalesce(item.user_id::text,''));
  update public.storage_reservations set status=case when p_succeeded then 'committed' else 'released' end, finished_at=now() where id=item.id;
  if p_succeeded then
    if p_storage_key is null then raise exception using errcode='P0001', message='storage_key_required'; end if;
    insert into public.storage_objects(reservation_id,tenant_id,user_id,category,storage_key,size_bytes,sha256,retention_until) values(item.id,item.tenant_id,item.user_id,item.category,p_storage_key,item.bytes,p_sha256,p_retention_until) returning id into object_id;
  end if;
  return object_id;
end; $$;

create or replace function public.release_storage_object(p_tenant_id integer, p_category text, p_storage_key text)
returns boolean language plpgsql security definer set search_path = public as $$
declare item public.storage_objects;
begin
  select * into item from public.storage_objects where tenant_id=p_tenant_id and category=p_category and storage_key=p_storage_key and status='active' for update;
  if not found then return false; end if;
  update public.storage_accounts set used_bytes=greatest(0,used_bytes-item.size_bytes), updated_at=now() where tenant_id=item.tenant_id and scope_key in ('tenant','user:'||coalesce(item.user_id::text,''));
  update public.storage_objects set status='deleted',deleted_at=now() where id=item.id;
  return true;
end; $$;

alter table public.storage_accounts enable row level security; alter table public.storage_reservations enable row level security; alter table public.storage_objects enable row level security;
revoke all on public.storage_accounts, public.storage_reservations, public.storage_objects from anon, authenticated;
grant select,insert,update,delete on public.storage_accounts, public.storage_reservations, public.storage_objects to service_role;
revoke all on function public.reserve_storage_bytes(integer,integer,text,bigint,bigint,bigint) from public,anon,authenticated;
revoke all on function public.finish_storage_reservation(uuid,boolean,text,text,timestamptz) from public,anon,authenticated;
revoke all on function public.release_storage_object(integer,text,text) from public,anon,authenticated;
grant execute on function public.reserve_storage_bytes(integer,integer,text,bigint,bigint,bigint) to service_role;
grant execute on function public.finish_storage_reservation(uuid,boolean,text,text,timestamptz) to service_role;
grant execute on function public.release_storage_object(integer,text,text) to service_role;
notify pgrst,'reload schema'; commit;
