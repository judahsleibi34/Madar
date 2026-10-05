begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_129_schema_state_missing'; end if;
 if v_schema_version <> 128 then raise exception 'migration_129_expected_schema_128_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version = 129,applied_at=now() where contract_key = 'core';
end $$;

-- Design is plain validated text and server-snapshotted managed images, never executable templates.
create table public.elearning_certificate_templates (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
 design jsonb not null check(jsonb_typeof(design)='object'), revision integer not null default 1,
 status text not null default 'active' check(status in ('active','archived')),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(tenant_id,id)
);
create table public.elearning_course_certificates (
 tenant_id integer not null, course_id uuid primary key, enabled boolean not null default false,
 template_id uuid, title_override text not null default '', issuer_override text not null default '',
 updated_at timestamptz not null default now(),
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id) on delete cascade,
 foreign key(tenant_id,template_id) references public.elearning_certificate_templates(tenant_id,id) on delete restrict,
 check(not enabled or template_id is not null)
);
alter table public.elearning_completion_events add unique(tenant_id,course_id,id);
create table public.elearning_credentials (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null,
 learner_id uuid not null, user_id integer not null, course_id uuid not null, completion_id uuid not null,
 credential_type text not null default 'course_completion' check(credential_type='course_completion'),
 credential_number text not null unique default ('MDR-'||upper(replace(gen_random_uuid()::text,'-',''))),
 verification_token text not null unique default (replace(gen_random_uuid()::text,'-','')||replace(gen_random_uuid()::text,'-','')),
 snapshot jsonb not null check(jsonb_typeof(snapshot)='object'), completed_at timestamptz not null, issued_at timestamptz not null default now(),
 status text not null default 'active' check(status in ('active','revoked')), revoked_at timestamptz, revocation_reason text,
 unique(tenant_id,learner_id,course_id,completion_id,credential_type),
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id) on delete restrict,
 foreign key(tenant_id,course_id,completion_id) references public.elearning_completion_events(tenant_id,course_id,id) on delete restrict,
 check((status='active' and revoked_at is null and revocation_reason is null) or(status='revoked' and revoked_at is not null and length(btrim(revocation_reason)) between 1 and 1000))
);
create index elearning_credentials_owner on public.elearning_credentials(tenant_id,user_id,issued_at desc,id);
create index elearning_credentials_course on public.elearning_credentials(tenant_id,course_id,issued_at desc,id);

create function public.elearning_validate_certificate_design(p_design jsonb) returns void language plpgsql set search_path='' as $$
declare k text;v text;variable text;begin
 if jsonb_typeof(p_design)<>'object' or octet_length(p_design::text)>3000000 then raise exception using errcode='22023',message='certificate_invalid_design';end if;
 for k,v in select key,value from jsonb_each_text(p_design) loop
 if k not in ('name','title','subtitle','body','issuer_name','signer_name','signer_title','logo_url','signature_url','logo_image','signature_image') then raise exception using errcode='22023',message='certificate_invalid_field';end if;
 if k not in ('logo_image','signature_image') and length(v)>2000 then raise exception using errcode='22023',message='certificate_text_too_long';end if;
 for variable in select x[1] from regexp_matches(v,'\{\{\s*([^{}]+?)\s*\}\}','g') x loop
 if btrim(variable) not in ('learner_name','course_name','completion_date','issue_date','issuer_name','credential_id') then raise exception using errcode='22023',message='certificate_unknown_placeholder';end if;
 end loop;
 if regexp_replace(v,'\{\{\s*(learner_name|course_name|completion_date|issue_date|issuer_name|credential_id)\s*\}\}','','g') ~ '\{\{|\}\}' then raise exception using errcode='22023',message='certificate_unknown_placeholder';end if;
 end loop;
 if coalesce(btrim(p_design->>'name'),'')='' or coalesce(btrim(p_design->>'title'),'')='' or coalesce(btrim(p_design->>'issuer_name'),'')='' then raise exception using errcode='22023',message='certificate_required_fields';end if;
end $$;

create function public.elearning_credential_immutable() returns trigger language plpgsql set search_path='' as $$ begin
 if (to_jsonb(new)-array['status','revoked_at','revocation_reason']) is distinct from (to_jsonb(old)-array['status','revoked_at','revocation_reason']) or old.status='revoked' or new.status<>'revoked' then
 raise exception using errcode='42501',message='credential_immutable';end if;
 return new;
end $$;
create trigger elearning_credential_immutable before update on public.elearning_credentials for each row execute function public.elearning_credential_immutable();

-- This private hook consumes an existing formal event. There is no learner issuance RPC.
create function public.elearning_issue_credential(p_completion_id uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare e public.elearning_completion_events%rowtype;cfg public.elearning_course_certificates%rowtype;t public.elearning_certificate_templates%rowtype;l public.elearning_learners%rowtype;d jsonb;issued uuid;begin
 select * into e from public.elearning_completion_events where id=p_completion_id and scope='course';if not found then return null;end if;
 select * into cfg from public.elearning_course_certificates where tenant_id=e.tenant_id and course_id=e.course_id and enabled; if not found then return null;end if;
 select * into t from public.elearning_certificate_templates where tenant_id=e.tenant_id and id=cfg.template_id and status='active';if not found then return null;end if;
 select l0.* into l from public.elearning_enrollments n join public.elearning_learners l0 on(l0.tenant_id,l0.id)=(n.tenant_id,n.learner_id) where n.tenant_id=e.tenant_id and n.course_id=e.course_id and n.id=e.enrollment_id;
 if l.user_id is null then return null;end if;
 d:=t.design||jsonb_build_object('title',coalesce(nullif(cfg.title_override,''),t.design->>'title'),'issuer_name',coalesce(nullif(cfg.issuer_override,''),t.design->>'issuer_name'));
 insert into public.elearning_credentials(tenant_id,learner_id,user_id,course_id,completion_id,completed_at,snapshot)
 values(e.tenant_id,l.id,l.user_id,e.course_id,e.id,e.completed_at,jsonb_build_object('schema',129,'design',d,'learner_name',coalesce(nullif((select btrim(concat_ws(' ',first_name,last_name)) from public.users where id=l.user_id),''),l.name),'course_name',coalesce(e.completion_snapshot->>'course_name',(select name from public.elearning_courses where id=e.course_id)),'template_revision',t.revision))
 on conflict(tenant_id,learner_id,course_id,completion_id,credential_type) do nothing returning id into issued;
 if issued is not null then insert into public.audit_logs(tenant_id,action,target_type,target_id,metadata) values(e.tenant_id,'elearning.credential.issued','elearning_credential',issued::text,jsonb_build_object('course_id',e.course_id,'completion_id',e.id));end if;
 return coalesce(issued,(select id from public.elearning_credentials where completion_id=e.id));
end $$;
create function public.elearning_completion_credential_hook() returns trigger language plpgsql security definer set search_path='' as $$ begin
 if new.scope='course' then perform public.elearning_issue_credential(new.id);end if;return new;
end $$;
create trigger elearning_completion_credential_hook after insert on public.elearning_completion_events for each row execute function public.elearning_completion_credential_hook();

create function public.manage_elearning_certificates(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_action text,p_id uuid,p_payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare saved uuid;event record;total integer:=0;current_revision integer;begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id,true);
 perform pg_advisory_xact_lock(125,p_tenant_id);
 if p_course_id is not null then
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='certificate_course_not_found';end if;
 end if;
 if p_action='template' then
 perform public.elearning_validate_certificate_design(p_payload->'design');
 if p_id is null then insert into public.elearning_certificate_templates(tenant_id,design,status) values(p_tenant_id,p_payload->'design',coalesce(p_payload->>'status','active')) returning id into saved;
 else
 select revision into current_revision from public.elearning_certificate_templates where tenant_id=p_tenant_id and id=p_id for update;
 if not found then raise exception using errcode='P0002',message='certificate_template_not_found';end if;
 if current_revision is distinct from (p_payload->>'expected_revision')::integer then raise exception using errcode='40001',message='certificate_conflict';end if;
 update public.elearning_certificate_templates set design=p_payload->'design',status=coalesce(p_payload->>'status','active'),revision=revision+1,updated_at=now() where tenant_id=p_tenant_id and id=p_id returning id into saved;
 end if;
 elsif p_action='configure' then
 if p_course_id is null then raise exception using errcode='22023',message='certificate_course_required';end if;
 if (p_payload->>'enabled')::boolean and not exists(select 1 from public.elearning_certificate_templates where tenant_id=p_tenant_id and id=(p_payload->>'template_id')::uuid and status='active') then raise exception using errcode='22023',message='certificate_template_unavailable';end if;
 -- Validate overrides with the same plain-text placeholder contract.
 perform public.elearning_validate_certificate_design(jsonb_build_object('name','Override','title',coalesce(nullif(p_payload->>'title_override',''),'Certificate'),'issuer_name',coalesce(nullif(p_payload->>'issuer_override',''),'Issuer')));
 insert into public.elearning_course_certificates(tenant_id,course_id,enabled,template_id,title_override,issuer_override)
 values(p_tenant_id,p_course_id,(p_payload->>'enabled')::boolean,(p_payload->>'template_id')::uuid,coalesce(p_payload->>'title_override',''),coalesce(p_payload->>'issuer_override',''))
 on conflict(course_id) do update set enabled=excluded.enabled,template_id=excluded.template_id,title_override=excluded.title_override,issuer_override=excluded.issuer_override,updated_at=now();
 elsif p_action='backfill' then
 if p_course_id is null or p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode='22023',message='certificate_confirmation_required';end if;
 for event in select id from public.elearning_completion_events where tenant_id=p_tenant_id and course_id=p_course_id and scope='course' loop
 if not exists(select 1 from public.elearning_credentials where completion_id=event.id) and public.elearning_issue_credential(event.id) is not null then total:=total+1;end if;end loop;
 elsif p_action='revoke' then
 if p_course_id is null or p_payload->'confirmed' is distinct from 'true'::jsonb or coalesce(length(btrim(p_payload->>'reason')),0) not between 1 and 1000 then raise exception using errcode='22023',message='certificate_revocation_reason_required';end if;
 perform 1 from public.elearning_credentials where tenant_id=p_tenant_id and course_id=p_course_id and id=p_id for update;
 if not found then raise exception using errcode='P0002',message='credential_not_found';end if;
 update public.elearning_credentials set status='revoked',revoked_at=now(),revocation_reason=btrim(p_payload->>'reason') where tenant_id=p_tenant_id and id=p_id and status='active';saved:=p_id;
 elsif p_action='view' then
 if not exists(select 1 from public.elearning_credentials where tenant_id=p_tenant_id and course_id=p_course_id and id=p_id) then raise exception using errcode='P0002',message='credential_not_found';end if;
 return (select to_jsonb(c) from public.elearning_credentials c where c.tenant_id=p_tenant_id and c.id=p_id);
 elsif p_action<>'list' then raise exception using errcode='22023',message='certificate_invalid_action';end if;
 if p_action<>'list' then insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata) values(p_tenant_id,p_user_id,'elearning.certificate.'||p_action,'elearning_certificate',coalesce(saved,p_course_id)::text,jsonb_build_object('course_id',p_course_id,'issued_count',total));end if;
 return jsonb_build_object('saved_id',saved,'issued_count',total,
 'templates',coalesce((select jsonb_agg(to_jsonb(t)-'design'||jsonb_build_object('design',t.design-array['logo_image','signature_image']) order by t.created_at desc) from public.elearning_certificate_templates t where t.tenant_id=p_tenant_id),'[]'),
 'configuration',coalesce((select to_jsonb(c) from public.elearning_course_certificates c where c.tenant_id=p_tenant_id and c.course_id=p_course_id),jsonb_build_object('enabled',false,'template_id',null,'title_override','','issuer_override','')),
 'counts',(select jsonb_build_object('total',count(*),'active',count(*) filter(where status='active'),'revoked',count(*) filter(where status='revoked')) from public.elearning_credentials where tenant_id=p_tenant_id and course_id=p_course_id),
 'credentials',coalesce((select jsonb_agg(to_jsonb(c)-array['snapshot','verification_token','user_id','learner_id','completion_id','tenant_id']||jsonb_build_object('snapshot',c.snapshot-'design') order by c.issued_at desc,c.id) from public.elearning_credentials c where c.tenant_id=p_tenant_id and c.course_id=p_course_id),'[]'));
end $$;

create function public.get_elearning_my_certificates(p_tenant_id integer,p_user_id integer,p_id uuid default null) returns jsonb language plpgsql stable security definer set search_path='' as $$ begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 if p_id is not null then
 if not exists(select 1 from public.elearning_credentials where tenant_id=p_tenant_id and user_id=p_user_id and id=p_id) then raise exception using errcode='P0002',message='credential_not_found';end if;
 return (select to_jsonb(c) from public.elearning_credentials c where tenant_id=p_tenant_id and user_id=p_user_id and id=p_id);
 end if;
 return jsonb_build_object('credentials',coalesce((select jsonb_agg(to_jsonb(c)-array['snapshot','verification_token','user_id','learner_id','completion_id','tenant_id']||jsonb_build_object('snapshot',c.snapshot-'design') order by c.issued_at desc,c.id) from public.elearning_credentials c where tenant_id=p_tenant_id and user_id=p_user_id),'[]'));
end $$;
create function public.verify_elearning_credential(p_token text) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('learner_name',snapshot->>'learner_name','course_name',snapshot->>'course_name','issuer_name',snapshot->'design'->>'issuer_name','completed_at',completed_at,'issued_at',issued_at,'credential_number',credential_number,'status',status)
 from public.elearning_credentials where verification_token=p_token and length(p_token)=64;
$$;

-- Decorate the existing authorized player snapshot without a second access/progress engine.
alter function public.get_elearning_learner_course(integer,integer,uuid,uuid) rename to get_elearning_learner_course_schema127;
create function public.get_elearning_learner_course(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid default null) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare data jsonb;credential jsonb;begin
 data:=public.get_elearning_learner_course_schema127(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
 select jsonb_build_object('id',id,'credential_number',credential_number,'status',status) into credential from public.elearning_credentials where tenant_id=p_tenant_id and user_id=p_user_id and course_id=p_course_id order by issued_at desc,id limit 1;
 return data||jsonb_build_object('credential',credential);
end $$;
revoke all on function public.get_elearning_learner_course_schema127(integer,integer,uuid,uuid),public.get_elearning_learner_course(integer,integer,uuid,uuid) from public,anon,authenticated,service_role;
grant execute on function public.get_elearning_learner_course(integer,integer,uuid,uuid) to service_role;

do $$ declare n text;f record;begin
 foreach n in array array['elearning_certificate_templates','elearning_course_certificates','elearning_credentials'] loop
 execute format('alter table public.%I enable row level security',n);
 execute format('revoke all on public.%I from anon,authenticated,service_role',n);
 end loop;
 for f in select oid::regprocedure signature from pg_proc where pronamespace='public'::regnamespace and proname in ('elearning_validate_certificate_design','elearning_credential_immutable','elearning_issue_credential','elearning_completion_credential_hook','manage_elearning_certificates','get_elearning_my_certificates','verify_elearning_credential') loop
 execute format('revoke all on function %s from public,anon,authenticated,service_role',f.signature);
 end loop;
end $$;
grant execute on function public.manage_elearning_certificates(integer,integer,uuid,text,uuid,jsonb),public.get_elearning_my_certificates(integer,integer,uuid),public.verify_elearning_credential(text) to service_role;
notify pgrst,'reload schema';
commit;
