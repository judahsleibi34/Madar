-- Tenant-owned builder asset registry and project reference lifecycle.
begin;
create extension if not exists pgcrypto;
create table if not exists public.builder_assets (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid references public.builder_projects(id) on delete set null,
  uploader_user_id integer references public.users(id) on delete set null,
  storage_key text not null unique,
  original_filename text,
  managed_filename text not null,
  mime_type text not null,
  size_bytes bigint not null,
  sha256 text not null,
  status text not null default 'unreferenced',
  reference_count integer not null default 0,
  created_at timestamptz not null default now(),
  last_referenced_at timestamptz,
  deleted_at timestamptz,
  retention_until timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  constraint builder_assets_status_check check (status in ('unreferenced', 'active', 'soft_deleted')),
  constraint builder_assets_size_check check (size_bytes >= 0),
  constraint builder_assets_reference_count_check check (reference_count >= 0),
  constraint builder_assets_sha256_check check (sha256 ~ '^[0-9a-f]{64}$'),
  constraint builder_assets_storage_key_check check (storage_key ~ '^tenant_[1-9][0-9]*/builder_assets/[a-f0-9]{32}\.(png|jpg|webp)$'),
  constraint builder_assets_managed_filename_check check (managed_filename ~ '^[a-f0-9]{32}\.(png|jpg|webp)$')
);
create table if not exists public.builder_asset_references (
  asset_id uuid not null references public.builder_assets(id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  reference_path text not null,
  created_at timestamptz not null default now(),
  primary key (asset_id, project_id, reference_path)
);
create index if not exists builder_assets_tenant_status_retention_idx on public.builder_assets (tenant_id, status, retention_until);
create index if not exists builder_asset_references_project_idx on public.builder_asset_references (project_id, asset_id);
alter table public.builder_assets enable row level security;
alter table public.builder_asset_references enable row level security;
revoke all on public.builder_assets from anon, authenticated;
revoke all on public.builder_asset_references from anon, authenticated;
grant select, insert, update, delete on public.builder_assets to service_role;
grant select, insert, update, delete on public.builder_asset_references to service_role;
notify pgrst, 'reload schema';
commit;
