-- Durable, concurrency-safe idempotency for public builder forms.
begin;

alter table public.builder_form_submissions
  add column if not exists idempotency_key_hash text;
alter table public.builder_form_submissions
  add column if not exists request_hash text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_form_submissions_idempotency_hash_check'
      and conrelid = 'public.builder_form_submissions'::regclass
  ) then
    alter table public.builder_form_submissions
      add constraint builder_form_submissions_idempotency_hash_check
      check (idempotency_key_hash is null or idempotency_key_hash ~ '^[0-9a-f]{64}$') not valid;
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_form_submissions_request_hash_check'
      and conrelid = 'public.builder_form_submissions'::regclass
  ) then
    alter table public.builder_form_submissions
      add constraint builder_form_submissions_request_hash_check
      check (request_hash is null or request_hash ~ '^[0-9a-f]{64}$') not valid;
  end if;
end $$;

create unique index if not exists builder_form_submissions_idempotency_unique_idx
on public.builder_form_submissions (
  tenant_id, project_id, form_id, idempotency_key_hash
)
where idempotency_key_hash is not null;

create or replace function public.create_builder_form_submission_safe(
  p_submission jsonb,
  p_idempotency_key_hash text,
  p_request_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  p_tenant_id integer;
  p_project_id uuid;
  p_form_id text;
  existing_row public.builder_form_submissions;
  saved_row public.builder_form_submissions;
begin
  if jsonb_typeof(p_submission) <> 'object' then
    raise exception using errcode = 'P0001', message = 'form_submission_payload_invalid';
  end if;
  p_tenant_id := nullif(p_submission ->> 'tenant_id', '')::integer;
  p_project_id := nullif(p_submission ->> 'project_id', '')::uuid;
  p_form_id := nullif(p_submission ->> 'form_id', '');
  if p_tenant_id is null or p_project_id is null or p_form_id is null then
    raise exception using errcode = 'P0001', message = 'form_submission_payload_invalid';
  end if;
  if p_request_hash is null or p_request_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'form_submission_payload_invalid';
  end if;
  if p_idempotency_key_hash is not null
     and p_idempotency_key_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'idempotency_key_invalid';
  end if;
  if not exists (
    select 1 from public.builder_projects
    where id = p_project_id and tenant_id = p_tenant_id and status = 'published'
  ) then
    raise exception using errcode = 'P0002', message = 'builder_project_not_found';
  end if;

  perform pg_advisory_xact_lock(hashtext(concat_ws(
    ':', 'builder-form', p_tenant_id, p_project_id, p_form_id,
    coalesce(p_idempotency_key_hash, gen_random_uuid()::text)
  )));

  if p_idempotency_key_hash is not null then
    select * into existing_row
    from public.builder_form_submissions
    where tenant_id = p_tenant_id
      and project_id = p_project_id
      and form_id = p_form_id
      and idempotency_key_hash = p_idempotency_key_hash
    for update;
    if found then
      if existing_row.request_hash is distinct from p_request_hash then
        raise exception using errcode = 'P0001', message = 'idempotency_conflict';
      end if;
      return jsonb_build_object('duplicate', true, 'submission', to_jsonb(existing_row));
    end if;
  end if;

  insert into public.builder_form_submissions (
    tenant_id, project_id, form_id, form_title, form_version, status,
    answers, quiz_result, field_snapshot, submitter_ip, user_agent,
    idempotency_key_hash, request_hash
  ) values (
    p_tenant_id,
    p_project_id,
    p_form_id,
    nullif(p_submission ->> 'form_title', ''),
    nullif(p_submission ->> 'form_version', '')::integer,
    coalesce(nullif(p_submission ->> 'status', ''), 'new'),
    coalesce(p_submission -> 'answers', '{}'::jsonb),
    p_submission -> 'quiz_result',
    coalesce(p_submission -> 'field_snapshot', '[]'::jsonb),
    nullif(p_submission ->> 'submitter_ip', ''),
    nullif(p_submission ->> 'user_agent', ''),
    p_idempotency_key_hash,
    p_request_hash
  ) returning * into saved_row;

  return jsonb_build_object('duplicate', false, 'submission', to_jsonb(saved_row));
end;
$$;

revoke all on function public.create_builder_form_submission_safe(jsonb, text, text)
from public, anon, authenticated;
grant execute on function public.create_builder_form_submission_safe(jsonb, text, text)
to service_role;

notify pgrst, 'reload schema';
commit;
