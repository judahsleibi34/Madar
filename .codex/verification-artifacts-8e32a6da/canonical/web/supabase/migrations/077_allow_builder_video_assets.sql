-- Allow securely managed MP4 and WebM files in the builder asset registry.
begin;

alter table public.builder_assets
  drop constraint if exists builder_assets_storage_key_check;
alter table public.builder_assets
  add constraint builder_assets_storage_key_check
  check (storage_key ~ '^tenant_[1-9][0-9]*/builder_assets/[a-f0-9]{32}[.](png|jpg|webp|mp4|webm)$');

alter table public.builder_assets
  drop constraint if exists builder_assets_managed_filename_check;
alter table public.builder_assets
  add constraint builder_assets_managed_filename_check
  check (managed_filename ~ '^[a-f0-9]{32}[.](png|jpg|webp|mp4|webm)$');

notify pgrst, 'reload schema';
commit;
