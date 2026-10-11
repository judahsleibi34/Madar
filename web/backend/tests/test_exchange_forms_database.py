"""Schema142 Exchange authority on a marked disposable database."""
import json
from uuid import uuid4
from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests
from tests.test_elearning_forms import schema


class ExchangeFormsDatabaseTests(AcademyProgrammeDatabaseTests):
    def setUp(self):
        super().setUp()
        if self.db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0] < 142:
            self.skipTest('Schema142 rehearsal required')
        self.db.execute("update elearning_settings set settings=settings||'{\"programmes_enabled\":true}' where tenant_id=%s", (self.tenant,))

    def form(self, status='active'):
        return self.db.execute('select manage_elearning_form(%s,%s,null,1,\'Exchange answers\',%s,%s::jsonb)',(self.tenant,self.user,status,json.dumps(schema()))).fetchone()[0]

    def opportunity(self, form=None, identifier=None, revision=1, **changes):
        data={'title':'Synthetic Exchange','status':'published','capacity':1,'application_form_id':form['id'] if form else None,**changes}
        return self.db.execute('select manage_academy_opportunity(%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.user,identifier,revision,json.dumps(data))).fetchone()[0]

    def submit_exchange(self, form, opportunity, user=None, key=None):
        return self.db.execute('select submit_elearning_form(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,\'[]\',%s)',(self.tenant,user or self.user,form['id'],form['version'],uuid4(),key or uuid4(),'a'*64,json.dumps({'student':'No'}),opportunity['id'])).fetchone()[0]

    def decide(self, response, status='approved', revision=1, actor=None):
        return self.db.execute('select review_exchange_response(%s,%s,%s,%s,%s,\'Domain review\')',(self.tenant,actor or self.user,response['id'],revision,status)).fetchone()[0]

    def test_exchange_response_context_single_answer_store_and_single_notification(self):
        f=self.form();o=self.opportunity(f);self.purchase();before=self.db.execute('select count(*) from academy_applications').fetchone()[0]
        key=uuid4();r=self.submit_exchange(f,o,key=key)
        self.assertTrue(self.submit_exchange(f,o,key=key)['duplicate'])
        stored=self.db.execute('select form_id,version,opportunity_id,user_id,answers from elearning_form_responses where id=%s',(r['id'],)).fetchone()
        self.assertEqual(str(stored[0]),f['id']);self.assertEqual(stored[1],1);self.assertEqual(str(stored[2]),o['id']);self.assertEqual(stored[3],self.user);self.assertEqual(stored[4],{'student':'No'})
        self.assertEqual(self.db.execute('select count(*) from academy_applications').fetchone()[0],before)
        self.assertEqual(self.db.execute('select count(*) from elearning_form_responses where tenant_id=%s and form_id=%s and opportunity_id=%s',(self.tenant,f['id'],o['id'])).fetchone()[0],1)
        self.assertEqual(self.db.execute('select elearning_form_counts(%s,%s)',(self.tenant,self.user)).fetchone()[0][f['id']]['responses'],1)
        event=self.db.execute("select title,data from notification_events where tenant_id=%s and event_type='learning_form_response'",(self.tenant,)).fetchall()
        self.assertEqual(len(event),1);self.assertIn('Synthetic Exchange',json.dumps(event))
        self.rejected(lambda:self.db.execute('update elearning_form_responses set opportunity_id=null where id=%s',(r['id'],)),'42501')
        self.rejected(lambda:self.opportunity(self.form(),o['id'],1),'40001')

    def test_exchange_association_missing_archived_foreign_and_inactive_form(self):
        self.rejected(lambda:self.opportunity(),'22023')
        f=self.form('inactive');self.rejected(lambda:self.opportunity(f),'22023')
        archived=self.form('archived');self.rejected(lambda:self.opportunity(archived,status='draft'),'23503')
        other=self.db.execute("insert into tenants(brand_name,owner_name) values('Other','Test') returning tenant_id").fetchone()[0]
        f=self.form()
        self.rejected(lambda:self.db.execute("insert into academy_exchange_opportunities(tenant_id,created_by,title,application_form_id) values(%s,%s,'Foreign',%s)",(other,self.user,f['id'])),'23503')
        self.rejected(lambda:self.opportunity({'id':str(uuid4())}),'23503')

    def test_exchange_closed_archived_expired_full_and_ineligible_reject(self):
        f=self.form();o=self.opportunity(f)
        self.rejected(lambda:self.submit_exchange(f,o),'42501')
        self.purchase()
        for status in ['draft','closed','archived']:
            unavailable=self.opportunity(f,status=status)
            self.rejected(lambda:self.submit_exchange(f,unavailable),'42501')
        expired=self.opportunity(f,deadline='2020-01-01T00:00:00Z');self.rejected(lambda:self.submit_exchange(f,expired),'42501')
        self.rejected(lambda:self.submit_exchange(f,{'id':str(uuid4())}),'P0002')
        r=self.submit_exchange(f,o);self.decide(r)
        self.rejected(lambda:self.submit_exchange(f,o,key=uuid4()),'42501')
        self.assertFalse(self.db.execute('select exchange_opportunity_available(%s,%s,%s)',(self.tenant,self.user,o['id'])).fetchone()[0])

    def test_exchange_approval_is_distinct_from_forms_read_and_has_immutable_history(self):
        f=self.form();o=self.opportunity(f);self.purchase();r=self.submit_exchange(f,o)
        self.db.execute("select manage_elearning_form_response(%s,%s,%s,true,'Owner notes')",(self.tenant,self.user,r['id']))
        self.assertEqual(self.db.execute('select exchange_approved_places(%s,%s)',(self.tenant,o['id'])).fetchone()[0],0)
        self.decide(r,'under_review');self.rejected(lambda:self.decide(r,revision=1),'40001')
        self.decide(r,revision=2)
        self.assertEqual(self.db.execute('select exchange_approved_places(%s,%s)',(self.tenant,o['id'])).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from academy_exchange_decision_history where response_id=%s',(r['id'],)).fetchone()[0],3)
        self.rejected(lambda:self.db.execute("update academy_exchange_decision_history set note='Rewrite' where response_id=%s",(r['id'],)),'42501')
        self.rejected(lambda:self.decide(r,revision=3),'22023')
        self.assertTrue(self.db.execute("select count(*) from notification_events where tenant_id=%s and event_type='learning_exchange_approved'",(self.tenant,)).fetchone()[0])

    def test_exchange_pending_does_not_reserve_and_legacy_approvals_share_capacity(self):
        f=self.form();o=self.opportunity(f);self.purchase();r=self.submit_exchange(f,o)
        # Historical answers are inserted only as an upgrade fixture, never through
        # the new submission endpoint. Their established approval remains authoritative.
        legacy=self.db.execute("insert into academy_applications(tenant_id,user_id,kind,details,terms_snapshot,idempotency_key,opportunity_id,status) values(%s,%s,'exchange','{}','Historical',%s,%s,'submitted') returning id",(self.tenant,self.user,uuid4(),o['id'])).fetchone()[0]
        self.review('application',legacy,'approved',1)
        self.rejected(lambda:self.decide(r),'42501')
        self.rejected(lambda:self.opportunity(f,o['id'],1,capacity=0),'22023')
        self.assertEqual(self.db.execute('select status from academy_exchange_decisions where response_id=%s',(r['id'],)).fetchone()[0],'submitted')

    def test_exchange_new_legacy_submit_denied_historical_replay_review_retained(self):
        self.rejected(lambda:self.apply('exchange'),'42501')
        key=uuid4();details={'historical':'Retained'}
        row=self.db.execute("insert into academy_applications(tenant_id,user_id,kind,details,terms_snapshot,idempotency_key) values(%s,%s,'exchange',%s::jsonb,'Historical',%s) returning id",(self.tenant,self.user,json.dumps(details),key)).fetchone()[0]
        replay=self.db.execute("select academy_submit_application(%s,%s,'exchange',%s::jsonb,%s)",(self.tenant,self.user,json.dumps(details),key)).fetchone()[0]
        self.assertEqual(row,replay);self.review('application',row,'under_review',1)
        self.assertEqual(self.db.execute('select details from academy_applications where id=%s',(row,)).fetchone()[0],details)
        # Unchanged Affiliate and Support authority is checked on142 as well.
        self.apply('affiliate')

    def test_exchange_foreign_context_and_review_are_denied(self):
        f=self.form();o=self.opportunity(f);self.purchase();r=self.submit_exchange(f,o)
        self.rejected(lambda:self.db.execute("select review_exchange_response(%s,%s,%s,1,'approved','Foreign')",(self.tenant+999,self.user,r['id'])),'42501')
        self.rejected(lambda:self.db.execute("select submit_elearning_form(%s,%s,%s,1,%s,%s,%s,'{}','[]',%s)",(self.tenant+999,self.user,f['id'],uuid4(),uuid4(),'a'*64,o['id'])),'42501')
        with self.db.transaction(force_rollback=True):
            self.db.execute('set local role service_role')
            self.rejected(lambda:self.db.execute("update academy_exchange_decisions set status='approved' where response_id=%s",(r['id'],)),'42501')

    def test_exchange_two_pending_requests_and_concurrent_approvals_serialize_capacity(self):
        import psycopg
        from concurrent.futures import ThreadPoolExecutor
        from tests.test_elearning_content_database import DSN
        f=self.form();o=self.opportunity(f);self.purchase();first=self.submit_exchange(f,o)
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        candidate=self.db.execute("insert into users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Exchange','Candidate',%s,%s,'active',true) returning id",(auth,email,self.tenant)).fetchone()[0]
        self.db.execute("insert into tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'learner','active')",(self.tenant,candidate,auth))
        self.purchase(candidate);second=self.submit_exchange(f,o,user=candidate)
        self.rejected(lambda:self.decide(second,actor=candidate),'42501')
        # Only this marked disposable database permits committed concurrency fixtures.
        self.db.commit()
        def approve(identifier):
            try:
                with psycopg.connect(DSN) as db:
                    db.execute("select review_exchange_response(%s,%s,%s,1,'approved','Concurrent review')",(self.tenant,self.user,identifier))
                return 'approved'
            except psycopg.Error as error:return error.sqlstate
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(approve,[first['id'],second['id']]))
        self.assertCountEqual(results,['approved','42501'])
        self.assertEqual(self.db.execute('select exchange_approved_places(%s,%s)',(self.tenant,o['id'])).fetchone()[0],1)


def load_tests(loader, tests, pattern):
    # Retained141 submission assertions run separately on their original contract.
    import unittest
    return unittest.TestSuite(ExchangeFormsDatabaseTests(name) for name in ExchangeFormsDatabaseTests.__dict__ if name.startswith('test_'))
