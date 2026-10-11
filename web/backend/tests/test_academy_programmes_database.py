"""Programme rules on marked disposable PostgreSQL; never live application data."""
import json
from uuid import uuid4
from tests.test_elearning_commerce_database import LearningCommerceDatabaseTests


class AcademyProgrammeDatabaseTests(LearningCommerceDatabaseTests):
    def setUp(self):
        super().setUp()
        cfg = {'eduhope_enabled': True, 'referral_rewards_enabled': True, 'referral_reward_amount': '10.00',
               'referral_reward_currency': 'USD', 'affiliates_enabled': True, 'tuition_support_enabled': True,
               'exchange_programme_enabled': True, 'learning_notifications_enabled': True,
               'tuition_sales_threshold': 4, 'minimum_withdrawal_amount': '50.00'}
        self.db.execute('insert into public.elearning_settings(tenant_id,settings) values(%s,%s::jsonb)',(self.tenant,json.dumps(cfg)))

    def wallet(self):
        return self.db.execute('select public.academy_wallet(%s,%s)',(self.tenant,self.user)).fetchone()[0]

    def code(self):
        return self.db.execute('select public.get_academy_referral_account(%s,%s)',(self.tenant,self.user)).fetchone()[0]['code']

    def purchase(self, user=None, simulated=False):
        provider='local_test' if simulated else 'verified_test_provider'
        plan=self.plan(amount='30.00')
        ch=self.db.execute('select public.create_commerce_learning_checkout(%s,%s,%s,%s,%s,%s)',(self.tenant,user or self.user,plan['id'],self.course,uuid4(),provider)).fetchone()[0]['checkout']
        self.event(ch,provider=provider,transaction=provider+':'+ch['id'])
        return ch

    def direct_sale(self, code):
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Buyer','Test',%s,%s,'pending_verification',false) returning id",(auth,email,self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'learner','active')",(self.tenant,user,auth))
        self.db.execute('select public.attach_academy_referral(%s,%s,%s)',(self.tenant,user,code))
        self.db.execute("update public.users set account_status='active',email_verified=true where id=%s",(user,))
        return self.purchase(user)

    def apply(self, kind='affiliate', key=None):
        fields={'full_name':'Applicant','email':'applicant@example.com','country':'PS','experience':'Experience','promotion_plan':'Direct links','terms_accepted':True,'university':'University','student_number':'123','contact':'Contact','tuition_fee':'100','financial_difficulty':'Details','requested_amount':'100','education':'Education','english_background':'A1','motivation':'Learn'}
        return self.db.execute('select public.academy_submit_application(%s,%s,%s,%s::jsonb,%s)',(self.tenant,self.user,kind,json.dumps(fields),key or uuid4())).fetchone()[0]

    def review(self, entity, identifier, status, revision):
        self.db.execute('select public.academy_review(%s,%s,%s,%s,%s,%s,%s)',(self.tenant,self.user,entity,identifier,status,revision,'Verified review'))

    def test_purchase_required_and_simulation_does_not_qualify(self):
        self.assertIsNone(self.code());self.purchase(simulated=True);self.assertIsNone(self.code())
        self.purchase();self.assertIsNotNone(self.code())

    def test_affiliate_approval_reuses_codes_without_staff_role(self):
        key=uuid4();a=self.apply(key=key);self.assertEqual(self.apply(key=key),a)
        self.assertIsNone(self.code());self.review('application',a,'approved',1)
        self.assertIsNotNone(self.code());self.review('application',a,'suspended',2);self.assertIsNone(self.code())
        self.review('application',a,'approved',3);self.assertIsNotNone(self.code())

    def test_affiliate_only_candidate_owner_lifecycle_preserves_accounting_and_role(self):
        owner = self.user
        auth = uuid4()
        email = f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)', (auth, email))
        candidate = self.db.execute("insert into users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Affiliate','Candidate',%s,%s,'active',true) returning id", (auth, email, self.tenant)).fetchone()[0]
        self.db.execute("insert into tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'learner','active')", (self.tenant, candidate, auth))
        self.user = candidate
        application = self.apply()
        self.assertIsNone(self.code())
        self.rejected(lambda: self.review('application', application, 'approved', 1), '42501')
        self.db.execute("select academy_review(%s,%s,'application',%s,'approved',1,'Reviewed candidate')", (self.tenant, owner, application))
        code = self.code()
        self.assertIsNotNone(code)
        self.assertEqual(self.db.execute('select get_elearning_my_learning(%s,%s)', (self.tenant, candidate)).fetchone()[0], [])
        # The synthetic sale helper configures an offering as its current actor.
        # Keep that owner action separate from the affiliate candidate identity.
        self.user = owner
        for _ in range(6):
            self.direct_sale(code)
        self.user = candidate
        before = self.wallet()
        self.db.execute("select academy_review(%s,%s,'application',%s,'suspended',2,'Suspended candidate')", (self.tenant, owner, application))
        self.assertIsNone(self.code())
        self.assertEqual(self.wallet(), {**before, 'can_refer': False})
        self.db.execute("select academy_review(%s,%s,'application',%s,'approved',3,'Reactivated candidate')", (self.tenant, owner, application))
        self.assertEqual(self.code(), code)
        withdrawal = self.db.execute("select academy_request_withdrawal(%s,%s,50,'PayPal','Synthetic owned account',true,%s)", (self.tenant, candidate, uuid4())).fetchone()[0]
        self.rejected(lambda: self.review('withdrawal', withdrawal, 'approved', 1), '42501')
        for revision, status in enumerate(('approved', 'processing', 'paid'), 1):
            self.db.execute("select academy_review(%s,%s,'withdrawal',%s,%s,%s,'Synthetic financial review')", (self.tenant, owner, withdrawal, status, revision))
        self.assertEqual(self.wallet()['total_withdrawn'], 50)
        self.assertEqual(self.wallet()['pending'], 0)
        self.assertEqual(self.db.execute('select role from tenant_memberships where tenant_id=%s and user_id=%s', (self.tenant, candidate)).fetchone()[0], 'learner')
        self.assertEqual(self.db.execute('select count(*) from elearning_learners where tenant_id=%s and user_id=%s', (self.tenant, candidate)).fetchone()[0], 0)

    def test_verified_sales_support_unlock_and_refund_recalculation(self):
        self.purchase();code=self.code()
        self.rejected(lambda:self.apply('tuition'),'42501')
        sales=[self.direct_sale(code) for _ in range(4)]
        self.assertTrue(self.wallet()['tuition_eligible']);a=self.apply('tuition')
        self.event(sales[0],'refunded',2,provider='verified_test_provider',transaction='verified_test_provider:'+sales[0]['id'])
        self.assertEqual(self.wallet()['verified_sales'],3);self.assertFalse(self.wallet()['tuition_eligible'])
        self.rejected(lambda:self.review('application',a,'approved',1),'42501')

    def test_withdrawal_reserves_and_pays_exactly_once(self):
        self.purchase();code=self.code()
        for _ in range(6):self.direct_sale(code)
        key=uuid4()
        def withdraw():return self.db.execute("select public.academy_request_withdrawal(%s,%s,50,'PayPal','Owned account',true,%s)",(self.tenant,self.user,key)).fetchone()[0]
        w=withdraw();self.assertEqual(w,withdraw());self.assertEqual(self.wallet()['available'],10)
        self.rejected(lambda:self.db.execute("select public.academy_request_withdrawal(%s,%s,50,'PayPal','Other',true,%s)",(self.tenant,self.user,uuid4())),'22023')
        self.rejected(lambda:self.review('withdrawal',w,'paid',1),'22023')
        self.review('withdrawal',w,'approved',1);self.rejected(lambda:self.review('withdrawal',w,'processing',1),'40001')
        self.review('withdrawal',w,'processing',2);self.review('withdrawal',w,'paid',3);self.review('withdrawal',w,'paid',3)
        self.assertEqual(self.wallet()['total_withdrawn'],50);self.assertEqual(self.wallet()['pending'],0)
        count=self.db.execute("select count(*) from public.academy_workflow_history where entity_id=%s and new_status='paid'",(w,)).fetchone()[0]
        self.assertEqual(count,1)

    def test_exchange_requires_active_learning_not_referral_sales(self):
        self.rejected(lambda:self.apply('exchange'),'42501');self.purchase();self.assertEqual(self.wallet()['verified_sales'],0)
        self.assertIsNotNone(self.apply('exchange'))

    def test_notifications_target_recipient_and_deduplicate(self):
        self.apply();rows=self.db.execute("select user_id,payload from public.notification_outbox where tenant_id=%s and payload->>'event_type'='learning_affiliate_submitted'",(self.tenant,)).fetchall()
        self.assertEqual(len(rows),2);self.assertTrue(all(row[0]==self.user for row in rows))
        for _ in range(2):self.db.execute("select public.enqueue_learning_notification(%s,%s,'learning_test','test','fixed','Title')",(self.tenant,self.user))
        self.assertEqual(self.db.execute("select count(*) from public.notification_outbox where tenant_id=%s and payload->>'event_type'='learning_test'",(self.tenant,)).fetchone()[0],2)

    def test_private_tables_and_review_permissions(self):
        a=self.apply()
        self.rejected(lambda:self.db.execute('select public.academy_review(%s,%s,%s,%s,%s,%s,%s)',(self.tenant+999,self.user,'application',a,'approved',1,'Wrong tenant')),'42501')
        for role in ('anon','authenticated','service_role'):
            with self.db.transaction(force_rollback=True):
                self.db.execute('set local role '+role)
                self.rejected(lambda:self.db.execute("update public.academy_applications set status='approved'"),'42501')

    def test_reports_reuse_progress_and_isolate_tenants(self):
        self.purchase()
        result=self.db.execute('select public.academy_owner_report(%s,%s)',(self.tenant,self.user)).fetchone()[0]
        self.assertEqual(result['summary']['enrollments'],1)
        self.assertEqual(result['enrollments'][0]['course_id'],str(self.course))
        empty=self.db.execute('select public.academy_owner_report(%s,%s,%s)',(self.tenant,self.user,uuid4())).fetchone()[0]
        self.assertEqual(empty['summary']['enrollments'],0)
        self.rejected(lambda:self.db.execute('select public.academy_owner_report(%s,%s)',(self.tenant+999,self.user)),'42501')

    def test_reversal_blocks_reserved_payout_and_rejection_releases_funds(self):
        self.purchase();code=self.code();sales=[self.direct_sale(code) for _ in range(5)]
        w=self.db.execute("select public.academy_request_withdrawal(%s,%s,50,'PayPal','Owned',true,%s)",(self.tenant,self.user,uuid4())).fetchone()[0]
        self.event(sales[0],'refunded',2,provider='verified_test_provider',transaction='verified_test_provider:'+sales[0]['id'])
        self.assertEqual(self.wallet()['debt'],10)
        self.rejected(lambda:self.review('withdrawal',w,'approved',1),'42501')
        self.review('withdrawal',w,'rejected',1);self.assertEqual(self.wallet()['available'],40)
        self.db.execute("update public.tenant_memberships set status='disabled' where tenant_id=%s and user_id=%s",(self.tenant,self.user))
        # A different active owner may review suspended users; no staff role is
        # granted to an affiliate and member endpoints fail closed.
        self.rejected(self.wallet,'42501')

    def test_owner_finance_profile_and_clicks_use_existing_facts(self):
        self.purchase();code=self.code();sale=self.direct_sale(code)
        self.db.execute('select public.academy_record_referral_click(%s,%s)',(self.tenant,code))
        referrals=self.db.execute("select public.academy_owner_finance(%s,%s,'referrals',50,0)",(self.tenant,self.user)).fetchone()[0]['items']
        self.assertEqual(len(referrals),1)
        self.assertEqual(referrals[0]['clicks'],1)
        rewards=self.db.execute("select public.academy_owner_finance(%s,%s,'rewards',50,0)",(self.tenant,self.user)).fetchone()[0]['items']
        self.assertEqual(len(rewards),1)
        transactions=self.db.execute("select public.academy_owner_finance(%s,%s,'transactions',50,0)",(self.tenant,self.user)).fetchone()[0]['items']
        self.assertTrue(transactions)
        profile=self.db.execute('select public.academy_owner_member_profile(%s,%s,%s)',(self.tenant,self.user,self.user)).fetchone()[0]
        self.assertEqual(profile['wallet']['verified_sales'],1)
        self.assertEqual(profile['user']['id'],self.user)
        self.rejected(lambda:self.db.execute('select public.academy_owner_member_profile(%s,%s,%s)',(self.tenant+999,self.user,self.user)),'42501')

    def test_application_preserves_terms_and_requires_configured_information(self):
        self.db.execute("update public.elearning_settings set settings=settings || '{\"affiliate_terms\":\"Original terms\",\"tuition_support_information_required\":true}'::jsonb where tenant_id=%s",(self.tenant,))
        identifier=self.apply()
        self.db.execute("update public.elearning_settings set settings=settings || '{\"affiliate_terms\":\"Updated terms\"}'::jsonb where tenant_id=%s",(self.tenant,))
        self.assertEqual(self.db.execute('select terms_snapshot from public.academy_applications where id=%s',(identifier,)).fetchone()[0],'Original terms')
        self.review('application',identifier,'approved',1)
        for _ in range(4):self.direct_sale(self.code())
        self.rejected(lambda:self.apply('tuition'),'22023')

    def test_learner_cannot_review_or_read_owner_reports(self):
        application=self.apply();self.review('application',application,'approved',1)
        sale=self.direct_sale(self.code());learner=sale['user_id']
        self.rejected(lambda:self.db.execute("select public.academy_review(%s,%s,'application',%s,'suspended',2,'Unauthorized')",(self.tenant,learner,application)),'42501')
        self.rejected(lambda:self.db.execute('select public.academy_owner_report(%s,%s)',(self.tenant,learner)),'42501')
