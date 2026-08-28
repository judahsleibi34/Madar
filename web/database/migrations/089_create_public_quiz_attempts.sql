-- Server-authoritative, publication-pinned public quiz attempts.
begin;

create extension if not exists pgcrypto;

create table if not exists public.public_quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  form_id text not null,
  publication_version integer not null check (publication_version > 0),
  publication_hash text not null check (publication_hash ~ '^[0-9a-f]{64}$'),
  subject_hash text not null check (subject_hash ~ '^[0-9a-f]{64}$'),
  state text not null default 'active' check (state in ('active','completed','expired','invalidated')),
  started_at timestamptz not null default now(),
  deadline_at timestamptz not null,
  finalized_at timestamptz,
  question_order jsonb not null check (jsonb_typeof(question_order) = 'array'),
  private_form_snapshot jsonb not null check (jsonb_typeof(private_form_snapshot) = 'object'),
  submitted_answers jsonb check (submitted_answers is null or jsonb_typeof(submitted_answers) = 'object'),
  result jsonb check (result is null or jsonb_typeof(result) = 'object'),
  submission_id uuid references public.builder_form_submissions(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint public_quiz_attempt_deadline_check check (deadline_at > started_at),
  constraint public_quiz_attempt_final_state_check check (
    (state = 'completed' and finalized_at is not null and result is not null)
    or (state <> 'completed')
  )
);

create index if not exists public_quiz_attempt_subject_idx
  on public.public_quiz_attempts (tenant_id, project_id, form_id, subject_hash, started_at desc);
create index if not exists public_quiz_attempt_active_deadline_idx
  on public.public_quiz_attempts (deadline_at) where state = 'active';

alter table public.public_quiz_attempts enable row level security;
revoke all on public.public_quiz_attempts from public, anon, authenticated;
grant select, insert, update, delete on public.public_quiz_attempts to service_role;

create or replace function public.start_public_quiz_attempt(
  p_attempt jsonb,
  p_max_attempts integer
) returns public.public_quiz_attempts
language plpgsql security definer set search_path = public
as $$
declare
  saved public.public_quiz_attempts;
  used integer;
begin
  if jsonb_typeof(p_attempt) <> 'object' or p_max_attempts not between 1 and 100 then
    raise exception using errcode='P0001', message='quiz_attempt_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':',
    'quiz-attempt', p_attempt->>'tenant_id', p_attempt->>'project_id',
    p_attempt->>'form_id', p_attempt->>'subject_hash'), 0));
  if not exists (
    select 1 from public.builder_projects p
    where p.id=(p_attempt->>'project_id')::uuid
      and p.tenant_id=(p_attempt->>'tenant_id')::integer
      and p.status='published'
      and p.published_version=(p_attempt->>'publication_version')::integer
  ) then
    raise exception using errcode='P0002', message='quiz_publication_not_found';
  end if;
  select count(*) into used from public.public_quiz_attempts a
  where a.tenant_id=(p_attempt->>'tenant_id')::integer
    and a.project_id=(p_attempt->>'project_id')::uuid
    and a.form_id=p_attempt->>'form_id'
    and a.subject_hash=p_attempt->>'subject_hash'
    and a.state in ('active','completed');
  if used >= p_max_attempts then
    raise exception using errcode='P0001', message='quiz_attempt_limit_reached';
  end if;
  insert into public.public_quiz_attempts (
    tenant_id,project_id,form_id,publication_version,publication_hash,
    subject_hash,state,started_at,deadline_at,question_order,private_form_snapshot
  ) values (
    (p_attempt->>'tenant_id')::integer,(p_attempt->>'project_id')::uuid,
    p_attempt->>'form_id',(p_attempt->>'publication_version')::integer,
    p_attempt->>'publication_hash',p_attempt->>'subject_hash','active',
    (p_attempt->>'started_at')::timestamptz,(p_attempt->>'deadline_at')::timestamptz,
    p_attempt->'question_order',p_attempt->'private_form_snapshot'
  ) returning * into saved;
  return saved;
end;
$$;

create or replace function public.finalize_public_quiz_attempt(
  p_attempt_id uuid,
  p_tenant_id integer,
  p_project_id uuid,
  p_form_id text,
  p_publication_version integer,
  p_answers jsonb,
  p_result jsonb,
  p_submission jsonb,
  p_request_hash text
) returns jsonb
language plpgsql security definer set search_path = public
as $$
declare
  attempt public.public_quiz_attempts;
  saved jsonb;
  saved_submission_id uuid;
begin
  select * into attempt from public.public_quiz_attempts where id=p_attempt_id for update;
  if not found or attempt.tenant_id<>p_tenant_id or attempt.project_id<>p_project_id
    or attempt.form_id<>p_form_id or attempt.publication_version<>p_publication_version then
    raise exception using errcode='P0002', message='quiz_attempt_not_found';
  end if;
  if attempt.state='completed' then
    return jsonb_build_object('duplicate',true,'result',attempt.result,'submission_id',attempt.submission_id);
  end if;
  if attempt.state<>'active' then
    raise exception using errcode='P0001', message='quiz_attempt_conflict';
  end if;
  if clock_timestamp()>attempt.deadline_at then
    update public.public_quiz_attempts set state='expired',updated_at=now() where id=p_attempt_id;
    -- Return rather than raise so the expiration state is committed.  Raising
    -- would roll the update back with the surrounding statement transaction.
    return jsonb_build_object('error','quiz_attempt_expired');
  end if;
  if jsonb_typeof(p_answers)<>'object' or jsonb_typeof(p_result)<>'object' then
    raise exception using errcode='P0001', message='quiz_attempt_invalid';
  end if;
  saved := public.create_builder_form_submission_safe(
    p_submission,
    encode(digest('quiz-attempt:'||p_attempt_id::text,'sha256'),'hex'),
    p_request_hash
  );
  saved_submission_id := (saved->'submission'->>'id')::uuid;
  update public.public_quiz_attempts set
    state='completed', finalized_at=now(), submitted_answers=p_answers,
    result=p_result, submission_id=saved_submission_id, updated_at=now()
  where id=p_attempt_id;
  return jsonb_build_object('duplicate',false,'result',p_result,'submission_id',saved_submission_id);
end;
$$;

revoke all on function public.start_public_quiz_attempt(jsonb,integer) from public,anon,authenticated;
revoke all on function public.finalize_public_quiz_attempt(uuid,integer,uuid,text,integer,jsonb,jsonb,jsonb,text) from public,anon,authenticated;
grant execute on function public.start_public_quiz_attempt(jsonb,integer) to service_role;
grant execute on function public.finalize_public_quiz_attempt(uuid,integer,uuid,text,integer,jsonb,jsonb,jsonb,text) to service_role;

insert into public.application_schema_state(contract_key,schema_version,applied_at)
values('core',89,now()) on conflict(contract_key) do update
set schema_version=excluded.schema_version,applied_at=excluded.applied_at;

notify pgrst, 'reload schema';
commit;
