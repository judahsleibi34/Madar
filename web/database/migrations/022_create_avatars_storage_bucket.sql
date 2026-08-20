/* ============================================================
   022_create_avatars_storage_bucket.sql

   Purpose:
   - Create public Supabase Storage bucket for profile avatars.
   - Backend uploads using service role.
   - Public read is allowed for avatar images.
   ============================================================ */

begin;

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'avatars',
  'avatars',
  true,
  5242880,
  array['image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Public avatars are readable" on storage.objects;

create policy "Public avatars are readable"
on storage.objects
for select
using (bucket_id = 'avatars');

commit;