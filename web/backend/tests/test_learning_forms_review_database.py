"""Generic independent Forms decisions in the marked disposable144 rehearsal."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
import psycopg
from uuid import uuid4
from tests.test_elearning_forms_database import LearningFormsDatabaseTests


class LearningFormReviewDatabaseTests(LearningFormsDatabaseTests):
    def setUp(self):
        super().setUp()
        self.db.execute("update elearning_settings set settings=settings||'{\"programmes_enabled\":true,\"referral_eligibility\":\"purchase_or_affiliate\"}'::jsonb where tenant_id=%s",(self.tenant,))
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        self.applicant=self.db.execute("insert into users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Applicant','Test',%s,%s,'active',true) returning id",(auth,email,self.tenant)).fetchone()[0]
        self.db.execute("insert into tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'member','active')",(self.tenant,self.applicant,auth))

    def application_form(self,kind='none'):
        value={'title':'Arbitrary application','access':'public' if kind=='none' else 'authenticated','sections':[{'id':'page','fields':[{'id':'custom_question','type':'paragraph','label':'Describe your own plan','required':True},{'id':'consent','type':'checkboxes','label':'Terms','required':True,'options':['I accept']}]}]}
        if kind!='none':value['workflow']={'kind':kind,'termsFieldId':'consent'}
        return self.form(definition=value)

    def send(self,form,user=None,answers=None,key=None):
        return self.db.execute('select submit_elearning_form(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',(self.tenant,user or self.applicant,form['id'],form['version'],uuid4(),key or uuid4(),'b'*64,json.dumps(answers or {'custom_question':'A personally authored plan','consent':['I accept']}),'[]')).fetchone()[0]

    def decide(self,response,status='approved',revision=1,actor=None,note='Authorized decision'):
        return self.db.execute('select review_elearning_form_response(%s,%s,%s,%s,%s,%s)',(self.tenant,actor or self.user,response['id'],status,revision,note)).fetchone()[0]

    def test_arbitrary_form_decision_history_idempotency_and_applicant_privacy(self):
        form=self.application_form();response=self.send(form)
        before=self.db.execute('select answers from elearning_form_responses where id=%s',(response['id'],)).fetchone()[0]
        self.decide(response,'under_review')
        first=self.decide(response,'approved',2,note='Private review note')
        retry=self.decide(response,'approved',2,note='Private review note')
        self.assertEqual(first['revision'],3);self.assertTrue(retry['duplicate'])
        self.assertEqual(self.db.execute('select count(*) from elearning_form_decision_history where response_id=%s',(response['id'],)).fetchone()[0],2)
        self.assertEqual(self.db.execute('select answers from elearning_form_responses where id=%s',(response['id'],)).fetchone()[0],before)
        visible=self.db.execute('select get_elearning_form_applicant_response(%s,%s,%s)',(self.tenant,self.applicant,response['id'])).fetchone()[0]
        self.assertEqual(visible['status'],'approved');self.assertNotIn('note',visible);self.assertNotIn('reviewer_id',visible)
        self.assertEqual(self.db.execute("select count(*) from notification_events where tenant_id=%s and event_type='learning_form_decision'",(self.tenant,)).fetchone()[0],2)
        self.rejected(lambda:self.decide(response,'not_approved',2),'40001')
        self.rejected(lambda:self.db.execute('update elearning_form_decision_history set note=\'Changed\' where response_id=%s',(response['id'],)),'42501')

    def test_native_service_role_can_save_settings_without_exposing_private_normalizer(self):
        with self.db.transaction(force_rollback=True):
            self.db.execute('set local role service_role')
            self.db.execute("select save_elearning_settings(%s,'{\"programmes_enabled\":true,\"platform_name\":\"Owner configured\"}'::jsonb)",(self.tenant,))
            self.rejected(lambda:self.db.execute("select normalize_academy_programme_settings('{}'::jsonb)"),'42501')
        self.assertNotEqual(self.db.execute('select settings->>\'platform_name\' from elearning_settings where tenant_id=%s',(self.tenant,)).fetchone()[0],'Owner configured')

    def test_nonbuyer_affiliate_approval_uses_domain_authority_without_copying_answers(self):
        response=self.send(self.application_form('affiliate'))
        app=self.db.execute('select id,status,details,revision from academy_applications where tenant_id=%s and learning_form_response_id=%s',(self.tenant,response['id'])).fetchone()
        self.assertEqual(app[1],'submitted');self.assertNotIn('custom_question',app[2]);self.assertIn('form_response_id',app[2])
        self.assertFalse(self.db.execute('select academy_can_refer(%s,%s)',(self.tenant,self.applicant)).fetchone()[0])
        self.decide(response)
        self.assertTrue(self.db.execute('select academy_can_refer(%s,%s)',(self.tenant,self.applicant)).fetchone()[0])
        self.assertEqual(self.db.execute('select role from tenant_memberships where tenant_id=%s and user_id=%s',(self.tenant,self.applicant)).fetchone()[0],'member')
        self.db.execute('select academy_review(%s,%s,\'application\',%s,\'suspended\',2,\'Domain suspension\')',(self.tenant,self.user,app[0]))
        self.assertEqual(self.db.execute('select status from elearning_form_reviews where response_id=%s',(response['id'],)).fetchone()[0],'suspended')
        self.assertFalse(self.db.execute('select academy_can_refer(%s,%s)',(self.tenant,self.applicant)).fetchone()[0])
        self.decide(response,'approved',3)
        self.assertTrue(self.db.execute('select academy_can_refer(%s,%s)',(self.tenant,self.applicant)).fetchone()[0])

    def test_terms_duplicates_and_missing_tuition_eligibility_reject_atomically(self):
        form=self.application_form('affiliate')
        self.rejected(lambda:self.send(form,answers={'custom_question':'No consent'}),'22023')
        key=uuid4();response=self.send(form,key=key)
        self.assertTrue(self.send(form,key=key)['duplicate'])
        self.rejected(lambda:self.send(form),'23505')
        self.rejected(lambda:self.send(self.application_form('tuition')),'42501')
        self.assertEqual(self.db.execute('select count(*) from elearning_form_responses where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from academy_applications where tenant_id=%s',(self.tenant,)).fetchone()[0],1)

    def test_permissions_self_approval_and_revoked_account_reject(self):
        response=self.send(self.application_form('affiliate'))
        self.rejected(lambda:self.decide(response,actor=self.applicant),'42501')
        self.db.execute("update tenant_memberships set role='admin' where tenant_id=%s and user_id=%s",(self.tenant,self.applicant))
        self.rejected(lambda:self.decide(response,actor=self.applicant),'42501')
        self.db.execute("update users set account_status='disabled' where id=%s",(self.applicant,))
        self.rejected(lambda:self.decide(response),'42501')
        self.assertEqual(self.db.execute('select status from elearning_form_reviews where response_id=%s',(response['id'],)).fetchone()[0],'submitted')
        self.rejected(lambda:self.db.execute('select get_elearning_form_applicant_response(%s,%s,%s)',(self.tenant,self.user,response['id'])),'P0002')

    def test_exchange_is_only_generic_forms_and_requires_independent_active_enrollment(self):
        self.rejected(lambda:self.send(self.application_form('exchange')),'42501')
        self.purchase(self.applicant)
        self.db.execute('select enroll_elearning_catalog(%s,%s,%s)',(self.tenant,self.applicant,self.course))
        response=self.send(self.application_form('exchange'))
        self.decide(response)
        self.assertEqual(self.db.execute("select count(*) from academy_applications where tenant_id=%s and kind='exchange'",(self.tenant,)).fetchone()[0],0)
        self.assertIsNone(self.db.execute("select to_regclass('public.academy_exchange_decisions')").fetchone()[0])

    def test_tuition_four_sales_and_refund_recheck_keep_domain_decision_atomic(self):
        self.purchase(self.applicant)
        code=self.db.execute('select get_academy_referral_account(%s,%s)',(self.tenant,self.applicant)).fetchone()[0]['code']
        sales=[self.direct_sale(code) for _ in range(4)]
        response=self.send(self.application_form('tuition'))
        self.decide(response,'under_review')
        self.event(sales[-1],state='refunded',sequence=2,provider='verified_test_provider',transaction='verified_test_provider:'+sales[-1]['id'])
        self.rejected(lambda:self.decide(response,'approved',2),'42501')
        self.assertEqual(self.db.execute('select status,revision from elearning_form_reviews where response_id=%s',(response['id'],)).fetchone(),('under_review',2))
        self.assertEqual(self.db.execute('select status,revision from academy_applications where learning_form_response_id=%s',(response['id'],)).fetchone(),('under_review',2))
        self.assertEqual(self.db.execute('select count(*) from academy_withdrawals where tenant_id=%s',(self.tenant,)).fetchone()[0],0)

    def test_competing_reviewers_commit_one_decision_and_one_domain_transition(self):
        response=self.send(self.application_form('affiliate'))
        # Committed synthetic fixture is confined to the marked database; the
        # rehearsal drops that whole database after the concurrent test.
        self.db.commit()
        def decide(status):
            try:
                with psycopg.connect(os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN']) as connection:
                    connection.execute('select review_elearning_form_response(%s,%s,%s,%s,1,%s)',(self.tenant,self.user,response['id'],status,'Concurrent '+status))
                return 'ok'
            except psycopg.Error as error:return error.sqlstate
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(decide,['approved','not_approved']))
        self.assertEqual(sorted(results),['40001','ok'])
        status=self.db.execute('select status,revision from elearning_form_reviews where response_id=%s',(response['id'],)).fetchone()
        self.assertEqual(status[1],2)
        self.assertEqual(self.db.execute('select status,revision from academy_applications where learning_form_response_id=%s',(response['id'],)).fetchone(),status)
        self.assertEqual(self.db.execute('select count(*) from elearning_form_decision_history where response_id=%s',(response['id'],)).fetchone()[0],1)
