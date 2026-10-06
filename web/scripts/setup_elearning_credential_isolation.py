"""Bounded local fixtures exercising real completion/issuance for foreign identities."""
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from dotenv import dotenv_values
import json,psycopg
root=Path(__file__).resolve().parents[1];path=Path('/tmp/madar-credential-browser-fixtures.json');fixture=json.loads(path.read_text());dsn=dotenv_values(root/'.env.database.local')['SUPABASE_DB_URL'];url=urlsplit(dsn);assert url.hostname in ('localhost','127.0.0.1') and url.port==54322
assert fixture['tenant_id']==3 and fixture['user_id']==1 and fixture.get('arabic_course') in fixture['courses']
assert 'security' not in fixture
with psycopg.connect(dsn) as db:
 assert db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]==130
 foreign_tenant=db.execute("insert into tenants(brand_name,owner_name) values('Credential Isolation Fixture','Local Fixture') returning tenant_id").fetchone()[0]
 def user(tenant,role):
  auth=uuid4();email=f'credential-fixture-{auth}@example.com';db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email));uid=db.execute("insert into users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Credential','Fixture',%s,%s,'active',true) returning id",(auth,email,tenant)).fetchone()[0];db.execute("insert into tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,%s,'active')",(tenant,uid,auth,role));return uid,str(auth)
 other,other_auth=user(3,'member');foreign,foreign_auth=user(foreign_tenant,'owner')
 db.execute("select public.manage_elearning_enrollments(3,%s,1,'enroll_users',%s,null,null,'manual',false)",(fixture['arabic_course'],[other]));db.execute('select public.complete_elearning_learner_lesson(3,%s,%s,%s)',(other,fixture['arabic_course'],fixture['arabic_lesson']))
 same_credential=str(db.execute('select id from elearning_credentials where tenant_id=3 and user_id=%s and course_id=%s',(other,fixture['arabic_course'])).fetchone()[0])
 course=str(db.execute("insert into elearning_courses(tenant_id,name,description,status,access_type) values(%s,'Credential Isolation Fixture','Local credential isolation','published','private') returning id",(foreign_tenant,)).fetchone()[0]);section=db.execute("select public.manage_elearning_structure(%s,%s,%s,1,'create_section',null,'{\"name\":\"Isolation section\",\"status\":\"published\"}')",(foreign_tenant,course,foreign)).fetchone()[0]['sections'][0]['id'];lesson=db.execute("select public.manage_elearning_structure(%s,%s,%s,2,'create_lesson',null,%s::jsonb)",(foreign_tenant,course,foreign,json.dumps({'name':'Isolation lesson','section_id':section,'status':'published'}))).fetchone()[0]['sections'][0]['lessons'][0]['id']
 def admin(action,identifier=None,payload=None):return db.execute('select public.manage_elearning_certificates(%s,%s,%s,%s,%s,%s::jsonb)',(foreign_tenant,foreign,course,action,identifier,json.dumps(payload or {}))).fetchone()[0]
 template=admin('template',payload={'design':{'name':'Isolation template','title':'Certificate','issuer_name':'Isolation Academy','body':'{{learner_name}}'}})['saved_id'];admin('configure',payload={'enabled':True,'template_id':template});db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'enroll_users',%s,null,null,'manual',false)",(foreign_tenant,course,foreign,[foreign]));db.execute('select public.complete_elearning_learner_lesson(%s,%s,%s,%s)',(foreign_tenant,foreign,course,lesson));foreign_credential=str(db.execute('select id from elearning_credentials where tenant_id=%s and course_id=%s',(foreign_tenant,course)).fetchone()[0])
 fixture['security']={'same_tenant_user':other,'same_tenant_auth':other_auth,'same_tenant_credential':same_credential,'foreign_tenant':foreign_tenant,'foreign_user':foreign,'foreign_auth':foreign_auth,'foreign_course':course,'foreign_template':template,'foreign_credential':foreign_credential}
path.write_text(json.dumps(fixture,indent=2));print('Created bounded local identity fixtures through existing enrollment/completion/credential engines.')
