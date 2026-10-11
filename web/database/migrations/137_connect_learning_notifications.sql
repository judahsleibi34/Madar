begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_137_schema_state_missing'; end if;
 if v_schema_version <> 136 then raise exception 'migration_137_expected_schema_136_got_%',v_schema_version; end if;
end $$;

alter table public.notification_preferences drop constraint notification_preferences_category_check;
alter table public.notification_preferences add constraint notification_preferences_category_check check(category in ('calendar','reservations','forms','general','learning'));
alter table public.notification_preferences drop constraint notification_preferences_supported_pair_check;
alter table public.notification_preferences add constraint notification_preferences_supported_pair_check check((category in ('calendar','learning') and channel in ('in_app','push','email')) or(category in ('reservations','forms','general') and channel in ('in_app','push')));

-- One canonical Madar event per recipient. Never broadcast private grades or
-- financial updates through the legacy tenant-wide intent. Outbox and event
-- commit in the same business transaction, using the existing worker/prefs.
create function public.enqueue_learning_notification(p_tenant integer,p_user integer,p_event text,p_source text,p_id text,p_title text,p_path text default '/my-learning')
returns void language plpgsql security definer set search_path='' as $$
declare k text; e public.notification_events%rowtype; payload jsonb; channel text;
begin
 if p_user is null or not exists(select 1 from public.elearning_settings where tenant_id=p_tenant and coalesce((settings->>'learning_notifications_enabled')::boolean,false)) then return; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=p_user and status='active') then return; end if;
 k:=encode(extensions.digest(concat_ws(':','learning',p_tenant,p_user,p_event,p_source,p_id),'sha256'),'hex');
 select * into e from public.get_or_create_notification_event(p_tenant,p_event,p_source,p_id,p_title,'Open your account for details.',jsonb_build_object('action',jsonb_build_object('kind','learning','path',p_path,'tenant_id',p_tenant::text)),k);
 payload:=jsonb_build_object('event_id',e.id,'event_type',e.event_type,'source_type',e.source_type,'source_id',e.source_id,'title',e.title,'body',e.body,'data',e.data,'event_deduplication_key',k);
 foreach channel in array array['internal','email'] loop
  insert into public.notification_outbox(tenant_id,user_id,channel,template,recipient_reference,payload,status,available_at,deduplication_key,retention_until)
  values(p_tenant,p_user,channel,'tenant_event','user:'||p_user,payload,'pending',now(),k||':'||channel,now()+interval '90 days') on conflict do nothing;
 end loop;
end $$;

create function public.learning_notify_owners(p_tenant integer,p_event text,p_source text,p_id text,p_title text,p_path text default '/e-learning')
returns void language plpgsql security definer set search_path='' as $$ declare u integer; begin
 for u in select user_id from public.tenant_memberships where tenant_id=p_tenant and role in ('owner','admin') and status='active' loop
  perform public.enqueue_learning_notification(p_tenant,u,p_event,p_source,p_id,p_title,p_path);
 end loop;
end $$;

-- Rows are authoritative business evidence. State/version is part of the event
-- identity, so replaying a command cannot create duplicate inbox records.
create function public.learning_business_notification() returns trigger language plpgsql security definer set search_path='' as $$
declare n jsonb:=to_jsonb(new); o jsonb; t integer; u integer; key text; event text; title text; path text:='/my-learning'; owners boolean:=false;
begin
 if TG_OP='UPDATE' then o:=to_jsonb(old); end if;
 t:=(n->>'tenant_id')::integer; u:=(n->>'user_id')::integer; key:=coalesce(n->>'id',n->>'referral_id',n->>'enrollment_id');
 if TG_TABLE_NAME='elearning_learners' then
  if TG_OP='UPDATE' and n->>'user_id' is not distinct from o->>'user_id' then return new; end if;
  event:='learning_registration'; title:='Welcome to your learning account';
 elsif TG_TABLE_NAME in ('elearning_enrollments','elearning_lesson_completions','elearning_completion_events') then
  select l.user_id into u from public.elearning_enrollments e join public.elearning_learners l on(l.tenant_id,l.id)=(e.tenant_id,e.learner_id) where e.tenant_id=t and e.id=coalesce((n->>'enrollment_id')::uuid,(n->>'id')::uuid);
  if TG_TABLE_NAME='elearning_enrollments' then
   if TG_OP='UPDATE' and n->>'status' is not distinct from o->>'status' then return new; end if;
   event:='learning_enrollment_'||(n->>'status'); title:='Course enrollment updated'; key:=key||':'||(n->>'updated_at'); owners:=true;
  elsif TG_TABLE_NAME='elearning_lesson_completions' then event:='learning_topic_completed'; title:='Topic completed'; key:=key||':'||(n->>'lesson_id');
  else event:='learning_'||(n->>'scope')||'_completed'; title:='Learning milestone completed'; owners:=true; end if;
  path:='/my-learning/courses/'||(n->>'course_id');
 elsif TG_TABLE_NAME='elearning_access_grants' then
  if TG_OP='UPDATE' and n->>'revoked_at' is not distinct from o->>'revoked_at' then return new;end if;
  select l.user_id into u from public.elearning_enrollments e join public.elearning_learners l on(l.tenant_id,l.id)=(e.tenant_id,e.learner_id) where e.tenant_id=t and e.id=(n->>'enrollment_id')::uuid;
  event:='learning_access_'||case when n->>'revoked_at' is null then 'granted' else 'revoked' end;title:='Course access updated';key:=key||':'||coalesce(n->>'revoked_at','granted');path:='/my-learning/courses/'||(n->>'course_id');
 elsif TG_TABLE_NAME='elearning_content_blocks' then
  if n->>'archived_at' is not null or not exists(select 1 from public.elearning_lessons where tenant_id=t and id=(n->>'lesson_id')::uuid and status='published') then return new;end if;
  event:='learning_material_published';title:='Learning material updated';key:=key||':'||coalesce(n->>'updated_at','created');owners:=true;
 elsif TG_TABLE_NAME='elearning_assessment_attempts' then
  if n->>'status'<>'submitted' or o->>'status'='submitted' then return new; end if;
  perform public.enqueue_learning_notification(t,u,'learning_exam_submitted',TG_TABLE_NAME,key,'Exam submitted','/my-learning/courses/'||(n->>'course_id'));
  event:='learning_exam_result'; title:='Your exam result is available'; path:='/my-learning/courses/'||(n->>'course_id');
 elsif TG_TABLE_NAME='elearning_credentials' then
  if TG_OP='UPDATE' and n->>'status' is not distinct from o->>'status' then return new; end if;
  event:='learning_certificate_'||case when n->>'status'='revoked' then 'revoked' else 'issued' end; title:='Certificate updated'; path:='/my-learning/certificates/'||key;
 elsif TG_TABLE_NAME='ecommerce_checkouts' then
  if n->>'state' is not distinct from o->>'state' then return new; end if;
  event:='learning_payment_'||(n->>'state'); title:='Payment status updated'; key:=key||':'||(n->>'event_sequence'); path:='/my-learning/plans'; owners:=true;
 elsif TG_TABLE_NAME='ecommerce_entitlements' then
  if TG_OP='UPDATE' and n->>'status' is not distinct from o->>'status' then return new; end if;
  event:='learning_access_'||(n->>'status'); title:='Course access updated'; key:=key||':'||coalesce(n->>'expires_at','lifetime');
 elsif TG_TABLE_NAME='academy_referrals' then
  u:=(n->>'sender_id')::integer; event:='learning_referral_attributed'; title:='Referral registered'; path:='/my-learning/account';
 elsif TG_TABLE_NAME='academy_referral_rewards' then
  select sender_id into u from public.academy_referrals where tenant_id=t and id=(n->>'referral_id')::uuid;
  if TG_OP='UPDATE' and n->>'status' is not distinct from o->>'status' then return new; end if;
  event:='learning_reward_'||(n->>'status'); title:='Referral reward updated'; path:='/my-learning/account'; owners:=true;
 elsif TG_TABLE_NAME in ('elearning_courses','elearning_assessments','elearning_lessons') then
  if n->>'status'<>'published' or o->>'status'='published' then return new; end if;
  event:='learning_'||TG_TABLE_NAME||'_published'; title:='Learning content published'; key:=key||':'||coalesce(n->>'revision',n->>'updated_at','1'); owners:=true; u:=null;
 else return new; end if;
 perform public.enqueue_learning_notification(t,u,event,TG_TABLE_NAME,key,title,path);
 if owners then perform public.learning_notify_owners(t,event||'_owner',TG_TABLE_NAME,key,title); end if;
 return new;
end $$;
create trigger learning_notification after insert or update of user_id on public.elearning_learners for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.elearning_enrollments for each row execute function public.learning_business_notification();
create trigger learning_notification after insert on public.elearning_lesson_completions for each row execute function public.learning_business_notification();
create trigger learning_notification after insert on public.elearning_completion_events for each row execute function public.learning_business_notification();
create trigger learning_notification after update of status on public.elearning_assessment_attempts for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.elearning_credentials for each row execute function public.learning_business_notification();
create trigger learning_notification after update of state on public.ecommerce_checkouts for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.ecommerce_entitlements for each row execute function public.learning_business_notification();
create trigger learning_notification after insert on public.academy_referrals for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.academy_referral_rewards for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.elearning_courses for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.elearning_assessments for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of status on public.elearning_lessons for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of revoked_at on public.elearning_access_grants for each row execute function public.learning_business_notification();
create trigger learning_notification after insert or update of content on public.elearning_content_blocks for each row execute function public.learning_business_notification();
revoke all on function public.enqueue_learning_notification(integer,integer,text,text,text,text,text),public.learning_notify_owners(integer,text,text,text,text,text),public.learning_business_notification() from public,anon,authenticated;
update public.application_schema_state set schema_version=137,applied_at=now() where contract_key='core';
notify pgrst,'reload schema';
commit;
