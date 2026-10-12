"""Independent forms on the marked disposable database only."""
import json
from uuid import uuid4
from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests
from tests.test_elearning_forms import schema

class LearningFormsDatabaseTests(AcademyProgrammeDatabaseTests):
    def form(self,identifier=None,version=1,status='active',definition=None):
        return self.db.execute('select manage_elearning_form(%s,%s,%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.user,identifier,version,'Feedback',status,json.dumps(definition or schema()))).fetchone()[0]
    def submit(self,f,user=None,key=None,hash_value='a'*64):
        return self.db.execute('select submit_elearning_form(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',(self.tenant,user,f['id'],f['version'],uuid4(),key or uuid4(),hash_value,json.dumps({'student':'No'}),'[]')).fetchone()[0]
    def test_version_archive_restore_duplicate_preserves_historical_response(self):
        f=self.form();r=self.submit(f)
        new=schema();new['title']='Changed title';self.form(f['id'],1,'archived',new)
        self.assertEqual(self.db.execute('select schema->>\'title\' from elearning_form_versions where tenant_id=%s and form_id=%s and version=1',(self.tenant,f['id'])).fetchone()[0],'Student feedback')
        self.assertEqual(self.db.execute('select version from elearning_form_responses where id=%s',(r['id'],)).fetchone()[0],1)
        self.rejected(lambda:self.submit(f),'40001')
        restored=self.form(f['id'],2,'inactive',new);self.assertEqual(restored['version'],3)
        duplicate=self.form(definition=new,status='inactive');self.assertNotEqual(duplicate['id'],f['id'])
        self.rejected(lambda:self.form(f['id'],1),'40001')
        self.rejected(lambda:self.db.execute('delete from elearning_forms where id=%s',(f['id'],)),'23503')
        self.rejected(lambda:self.db.execute('update elearning_form_versions set schema=\'{}\' where form_id=%s',(f['id'],)),'42501')
        self.rejected(lambda:self.db.execute('update elearning_form_responses set answers=\'{}\' where id=%s',(r['id'],)),'42501')
    def test_guest_authenticated_enrolled_and_idempotency(self):
        f=self.form();key=uuid4();r=self.submit(f,key=key);self.assertTrue(self.submit(f,key=key)['duplicate'])
        self.rejected(lambda:self.submit(f,key=key,hash_value='b'*64),'40001')
        s=schema();s['access']='authenticated';auth=self.form(definition=s)
        self.rejected(lambda:self.submit(auth),'42501');self.submit(auth,self.user)
        s['access']='enrolled';enrolled=self.form(definition=s)
        self.rejected(lambda:self.submit(enrolled,self.user),'42501')
        self.purchase();self.enroll();self.submit(enrolled,self.user)
    def test_builder_submission_storage_remains_independent(self):
        before=self.db.execute('select count(*) from builder_form_submissions').fetchone()[0]
        f=self.form();self.submit(f)
        self.assertEqual(self.db.execute('select count(*) from builder_form_submissions').fetchone()[0],before)
        self.assertEqual(self.db.execute('select count(*) from elearning_form_responses where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        project=self.db.execute("insert into builder_projects(tenant_id,owner_user_id,name,slug) values(%s,%s,'Builder independent',%s) returning id",(self.tenant,self.user,uuid4().hex)).fetchone()[0]
        self.db.execute("insert into builder_form_submissions(tenant_id,project_id,form_id,answers) values(%s,%s,'builder-form','{}')",(self.tenant,project))
        self.assertEqual(self.db.execute('select count(*) from elearning_form_responses where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
    def test_project_reference_and_response_tenant_constraints(self):
        f=self.form();other=self.db.execute("insert into tenants(brand_name,owner_name) values('Other','Test') returning tenant_id").fetchone()[0]
        project={'pages':[{'id':'home','slug':'/','sections':[{'elements':[{'type':'academyForm','academy':{'formId':f['id']}}]}]}]}
        self.assertTrue(self.db.execute('select validate_academy_builder_schema(%s::jsonb)',(json.dumps(project),)).fetchone()[0])
        self.rejected(lambda:self.db.execute("insert into builder_projects(tenant_id,owner_user_id,name,slug,usage_profile,draft_schema) values(%s,%s,'Other form',%s,'academy',%s::jsonb)",(other,self.user,uuid4().hex,json.dumps(project))),'23503')
        self.rejected(lambda:self.db.execute('insert into elearning_form_responses(id,tenant_id,form_id,version,answers,idempotency_key,request_hash) values(%s,%s,%s,1,\'{}\',%s,%s)',(uuid4(),other,f['id'],uuid4(),'a'*64)),'23503')
    def test_notifications_counts_and_owner_notes(self):
        f=self.form();r=self.submit(f,self.user)
        counts=self.db.execute('select elearning_form_counts(%s,%s)',(self.tenant,self.user)).fetchone()[0]
        self.assertEqual(counts[f['id']],{'responses':1,'unread':1})
        self.db.execute('select manage_elearning_form_response(%s,%s,%s,true,\'Reviewed\')',(self.tenant,self.user,r['id']))
        self.assertEqual(self.db.execute('select elearning_form_counts(%s,%s)',(self.tenant,self.user)).fetchone()[0][f['id']]['unread'],0)
        self.assertTrue(self.db.execute("select count(*) from notification_events where tenant_id=%s and event_type='learning_form_response'",(self.tenant,)).fetchone()[0])
        self.rejected(lambda:self.db.execute('select manage_elearning_form_response(%s,%s,%s,true,\'Cross tenant\')',(self.tenant+999,self.user,r['id'])),'42501')
    def test_private_file_metadata_is_response_owned_and_immutable(self):
        f=self.form();r=self.submit(f);identifier=uuid4()
        key=f'elearning-private/tenant_{self.tenant}/response_{r["id"]}/{identifier}'
        self.db.execute("insert into elearning_form_files(id,tenant_id,response_id,field_id,storage_key,filename,mime_type,size_bytes,sha256) values(%s,%s,%s,'proof',%s,'document-12345678.pdf','application/pdf',10,%s)",(identifier,self.tenant,r['id'],key,'b'*64))
        self.rejected(lambda:self.db.execute("update elearning_form_files set filename='document-87654321.pdf' where id=%s",(identifier,)),'42501')
        other_id=uuid4();other_key=f'elearning-private/tenant_{self.tenant+999}/response_{r["id"]}/{other_id}'
        self.rejected(lambda:self.db.execute("insert into elearning_form_files(id,tenant_id,response_id,field_id,storage_key,filename,mime_type,size_bytes,sha256) values(%s,%s,%s,'other',%s,'document-12345678.pdf','application/pdf',10,%s)",(other_id,self.tenant+999,r['id'],other_key,'b'*64)),'23503')
        with self.db.transaction(force_rollback=True):
            self.db.execute('set local role authenticated')
            self.rejected(lambda:self.db.execute('select * from elearning_form_files'),'42501')
    def test_configured_confirmation_uses_learning_notifications_for_signed_members_only(self):
        s=schema();s['notifyOwner']=False;s['confirmSubmitter']=True;f=self.form(definition=s)
        self.submit(f);self.submit(f,self.user)
        events=self.db.execute("select event_type from notification_events where tenant_id=%s and event_type in ('learning_form_confirmation','learning_form_response')",(self.tenant,)).fetchall()
        self.assertEqual(events,[('learning_form_confirmation',)])
