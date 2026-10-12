"""Reusable academy ownership: all fixtures live only in a marked rehearsal."""
import json
from uuid import uuid4
from contextlib import contextmanager
from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests


class AcademyMultiTenantDatabaseTests(AcademyProgrammeDatabaseTests):
    def setUp(self):
        super().setUp()
        self.a = (self.tenant,self.user,self.course)
        tenant=self.db.execute("insert into tenants(brand_name,owner_name) values('Different academy','Other owner') returning tenant_id").fetchone()[0]
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        user=self.db.execute("insert into users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Other','Owner',%s,%s,'active',true) returning id",(auth,email,tenant)).fetchone()[0]
        self.db.execute("insert into tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(tenant,user,auth))
        course=self.db.execute("insert into elearning_courses(tenant_id,name,status,access_type) values(%s,'Other course','published','paid') returning id",(tenant,)).fetchone()[0]
        cfg={'programmes_enabled':True,'affiliates_enabled':True,'referral_rewards_enabled':True,'referral_reward_amount':'15.00','referral_reward_currency':'USD','tuition_support_enabled':True,'tuition_sales_threshold':6,'minimum_withdrawal_amount':'20.00','withdrawals_enabled':True,'withdrawal_methods':['PayPal'],'exchange_programme_enabled':True,'learning_notifications_enabled':True,'referral_eligibility':'purchase_or_affiliate','support_programme_name':'Student Scholarship'}
        self.db.execute('insert into elearning_settings(tenant_id,settings) values(%s,%s::jsonb)',(tenant,json.dumps(cfg)))
        self.b=(tenant,user,course)

    @contextmanager
    def academy(self,which):
        prior=(self.tenant,self.user,self.course)
        self.tenant,self.user,self.course=which
        try:yield
        finally:self.tenant,self.user,self.course=prior

    def test_other_academy_application_ids_cannot_be_reviewed(self):
        for kind in ('affiliate','tuition','exchange'):
            with self.academy(self.b):
                self.purchase()
                if kind=='tuition':
                    code=self.code()
                    for _ in range(6):self.direct_sale(code)
                identifier=self.apply(kind)
            self.rejected(lambda:self.review('application',identifier,'approved',1),'P0002')
            # Tenant-scoped projection never returns another academy's rows.
            rows=self.db.execute('select id from academy_applications where tenant_id=%s',(self.a[0],)).fetchall()
            self.assertNotIn((identifier,),rows)

    def test_distinct_rewards_thresholds_and_withdrawal_minimums(self):
        for which,amount,threshold in ((self.a,10,4),(self.b,15,6)):
            with self.academy(which):
                self.purchase();self.direct_sale(self.code())
                wallet=self.wallet()
                self.assertEqual(wallet['available'],amount)
                self.assertEqual(wallet['threshold'],threshold)
                self.assertFalse(wallet['tuition_eligible'])
        with self.academy(self.b):
            self.direct_sale(self.code())
            key=self.db.execute("select academy_request_withdrawal(%s,%s,20,'PayPal','Owned',true,%s)",(self.tenant,self.user,uuid4())).fetchone()[0]
        self.rejected(lambda:self.review('withdrawal',key,'approved',1),'P0002')
        self.rejected(lambda:self.db.execute("select academy_request_withdrawal(%s,%s,20,'PayPal','Owned',true,%s)",(self.tenant,self.user,uuid4())),'22023')
        self.assertEqual(self.wallet()['available'],10)

    def test_referrals_rewards_reports_and_affiliation_do_not_leak(self):
        with self.academy(self.b):
            identifier=self.apply();self.review('application',identifier,'approved',1)
            code=self.code();self.direct_sale(code)
        self.assertIsNone(self.code())
        for kind in ('referrals','rewards','transactions'):
            result=self.db.execute('select academy_owner_finance(%s,%s,%s,50,0)',(self.tenant,self.user,kind)).fetchone()[0]
            self.assertEqual(result['items'],[])
        report=self.db.execute('select academy_owner_report(%s,%s,%s)',(self.tenant,self.user,self.b[2])).fetchone()[0]
        self.assertEqual(report['enrollments'],[])
        self.rejected(lambda:self.db.execute('select attach_academy_referral(%s,%s,%s)',(self.tenant,self.user,code)),'22023')
        with self.db.transaction(force_rollback=True):
            self.db.execute('set local role service_role')
            self.rejected(lambda:self.db.execute("update academy_referral_rewards set status='reversed' where tenant_id=%s",(self.b[0],)),'42501')

    def test_composite_history_and_member_foreign_keys(self):
        with self.academy(self.b):identifier=self.apply()
        self.rejected(lambda:self.db.execute("insert into academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status) values(%s,'application',%s,%s,'approved')",(self.tenant,identifier,self.user)),'23503')
        self.rejected(lambda:self.db.execute("insert into academy_applications(tenant_id,user_id,kind,details,idempotency_key) values(%s,%s,'affiliate','{}',%s)",(self.tenant,self.b[1],uuid4())),'23503')

    def test_owner_notifications_are_scoped_and_legacy_flag_normalizes(self):
        with self.academy(self.b):identifier=self.apply()
        recipients=self.db.execute("select distinct user_id from notification_outbox where tenant_id=%s and payload->>'source_id'=%s",(self.b[0],str(identifier))).fetchall()
        self.assertEqual(recipients,[(self.b[1],)])
        cfg=self.db.execute('select settings from elearning_settings where tenant_id=%s',(self.tenant,)).fetchone()[0]
        self.assertTrue(cfg['programmes_enabled']);self.assertNotIn('eduhope_enabled',cfg)
        self.assertEqual(cfg['tuition_sales_threshold'],4)

    def test_support_active_learner_model_is_not_referral_specific(self):
        self.db.execute("update elearning_settings set settings=settings || '{\"support_eligibility\":\"active_learner\",\"tuition_sales_threshold\":null,\"support_programme_name\":\"Scholarship\"}'::jsonb where tenant_id=%s",(self.tenant,))
        self.assertFalse(self.wallet()['tuition_eligible'])
        self.purchase();self.assertTrue(self.wallet()['tuition_eligible'])
        self.assertEqual(self.wallet()['verified_sales'],0)
        self.assertIsNotNone(self.apply('tuition'))

    def test_same_global_user_affiliate_status_is_academy_specific(self):
        auth=self.db.execute('select auth_id from users where id=%s',(self.a[1],)).fetchone()[0]
        self.db.execute("insert into tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'learner','active')",(self.b[0],self.a[1],auth))
        with self.academy((self.b[0],self.a[1],self.b[2])):
            identifier=self.apply()
            self.db.execute("select academy_review(%s,%s,'application',%s,'approved',1,'Tenant approval')",(self.b[0],self.b[1],identifier))
            self.assertIsNotNone(self.code())
        self.assertIsNone(self.code())
        self.assertEqual(self.db.execute('select role from tenant_memberships where tenant_id=%s and user_id=%s',(self.b[0],self.a[1])).fetchone()[0],'learner')
