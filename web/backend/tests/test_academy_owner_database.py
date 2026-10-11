"""Owner tools and private metadata on the marked disposable learning database."""
import json
from uuid import uuid4
from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests


class AcademyOwnerDatabaseTests(AcademyProgrammeDatabaseTests):
    def opportunity(self, identifier=None, revision=1, status='draft'):
        data={'title':'Exchange test','status':status,'capacity':1,'requirements':'Active course access'}
        return self.db.execute('select manage_academy_opportunity(%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.user,identifier,revision,json.dumps(data))).fetchone()[0]

    def test_opportunity_lifecycle_revision_tenant_and_capacity(self):
        row=self.opportunity();self.assertEqual(row['status'],'draft')
        def visible():return self.db.execute('select get_academy_open_opportunities(%s,%s)',(self.tenant,self.user)).fetchone()[0]
        self.assertEqual(visible(),[])
        row=self.opportunity(row['id'],1,'published');self.assertEqual(row['revision'],2)
        self.rejected(lambda:self.opportunity(row['id'],1,'closed'),'40001')
        self.assertEqual(visible(),[])
        self.purchase();self.assertEqual([item['id'] for item in visible()],[row['id']]);original=self.apply('exchange')
        details=self.db.execute('select details from academy_applications where id=%s',(original,)).fetchone()[0]
        details['opportunity_id']=row['id'];key=uuid4()
        application=self.db.execute("select academy_submit_application(%s,%s,'exchange',%s::jsonb,%s)",(self.tenant,self.user,json.dumps(details),key)).fetchone()[0]
        self.assertEqual(str(self.db.execute('select opportunity_id from academy_applications where id=%s',(application,)).fetchone()[0]),row['id'])
        self.review('application',application,'approved',1)
        self.assertEqual(visible(),[])
        row=self.opportunity(row['id'],2,'closed')
        self.assertEqual(self.db.execute("select academy_submit_application(%s,%s,'exchange',%s::jsonb,%s)",(self.tenant,self.user,json.dumps(details),key)).fetchone()[0],application)
        self.rejected(lambda:self.db.execute("select academy_submit_application(%s,%s,'exchange',%s::jsonb,%s)",(self.tenant,self.user,json.dumps(details),uuid4())),'42501')
        self.opportunity(row['id'],3,'archived');self.rejected(lambda:self.opportunity(row['id'],4,'published'),'22023')
        self.rejected(lambda:self.db.execute("select manage_academy_opportunity(%s,%s,%s,1,'{}')",(self.tenant+999,self.user,row['id'])),'42501')

    def test_private_document_metadata_ownership_and_review_lock(self):
        self.db.execute("update elearning_settings set settings=settings||'{\"support_eligibility\":\"active_learner\"}' where tenant_id=%s",(self.tenant,));self.purchase();app=self.apply('tuition')
        identifier=uuid4();data={'storage_key':f'academy-private/tenant_{self.tenant}/application_{app}/{identifier}','filename':'document.pdf','mime_type':'application/pdf','size_bytes':100,'sha256':'a'*64}
        def save(tenant=None):return self.db.execute('select manage_academy_document(%s,%s,%s,%s,%s::jsonb)',(tenant or self.tenant,self.user,app,identifier,json.dumps(data))).fetchone()[0]
        self.rejected(lambda:save(self.tenant+999),'42501');self.assertEqual(save()['filename'],'document.pdf')
        self.rejected(lambda:self.db.execute("insert into academy_application_documents(id,tenant_id,application_id,uploaded_by,storage_key,filename,mime_type,size_bytes,sha256) values(%s,%s,%s,%s,'bad','bad.pdf','application/pdf',1,%s)",(uuid4(),self.tenant,app,self.user,'a'*64)),'23514')
        self.db.execute('select manage_academy_document(%s,%s,%s,%s,null)',(self.tenant,self.user,app,identifier))
        self.assertIsNotNone(self.db.execute('select removed_at from academy_application_documents where id=%s',(identifier,)).fetchone()[0])
        self.review('application',app,'approved',1);self.rejected(save,'42501')

    def test_verified_institution_uses_canonical_linked_identity(self):
        self.purchase()
        self.db.execute("update elearning_settings set settings=settings||'{\"institution_enabled\":true,\"institution_email_domains\":[\"example.com\"],\"institution_student_label\":\"Test Institution Student\"}' where tenant_id=%s",(self.tenant,))
        result=self.db.execute('select academy_classified_students(%s,%s)',(self.tenant,self.user)).fetchone()[0]
        linked=[row for row in result['learners'] if row.get('user_id')==self.user]
        self.assertTrue(linked[0]['institution_verified']);self.assertEqual(linked[0]['classification'],'Test Institution Student')
        self.db.execute('update users set email_verified=false where id=%s',(self.user,))
        self.assertEqual(self.db.execute("select academy_classified_students(%s,%s,'institution')",(self.tenant,self.user)).fetchone()[0]['learners'],[])
        self.rejected(lambda:self.db.execute('select academy_classified_students(%s,%s)',(self.tenant+999,self.user)),'42501')

    def test_dashboard_and_contacts_keep_tenant_project_ownership(self):
        self.purchase();self.assertEqual(self.db.execute('select academy_owner_dashboard(%s,%s)',(self.tenant,self.user)).fetchone()[0]['purchases'],1)
        self.rejected(lambda:self.db.execute('select academy_owner_dashboard(%s,%s)',(self.tenant+999,self.user)),'42501')
        schema=json.dumps({'pages':[{'id':'home','slug':'/','sections':[]}]})
        project=self.db.execute("insert into builder_projects(tenant_id,owner_user_id,name,slug,usage_profile,draft_schema) values(%s,%s,'Academy test',%s,'academy',%s::jsonb) returning id",(self.tenant,self.user,'owner-'+uuid4().hex,schema)).fetchone()[0]
        self.db.execute("insert into contacts(tenant_id,project_id,name,email,subject,message) values(%s,%s,'Student','student@example.com','Question','Help')",(self.tenant,project))
        other=self.db.execute("insert into tenants(brand_name,owner_name) values('Other','Test') returning tenant_id").fetchone()[0]
        self.rejected(lambda:self.db.execute("insert into contacts(tenant_id,project_id,name,message) values(%s,%s,'Cross tenant','Help')",(other,project)),'23503')
        self.assertEqual(self.db.execute('select count(*) from contacts where tenant_id=%s',(other,)).fetchone()[0],0)
