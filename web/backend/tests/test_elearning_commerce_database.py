"""Commerce fulfillment and additive learning access on marked local PostgreSQL."""
import json
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import psycopg
from tests import test_elearning_content_database as content


class LearningCommerceDatabaseTests(content.ELearningContentDatabaseTests):
    def setUp(self):
        super().setUp()
        self.db.execute("update public.elearning_courses set status='published',access_type='paid' where id=%s", (self.course,))
        self.other = self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Other','published','paid') returning id", (self.tenant,)).fetchone()[0]
        self.private = self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Private','published','private') returning id", (self.tenant,)).fetchone()[0]

    def plan(self, billing='one_time', scope='single_course', ids=None, existing=None, status='active', amount='20.00'):
        details = dict(name='Test access',description='',status=status,billing_type=billing,amount=amount,currency='USD',access_scope=scope,course_ids=[str(x) for x in (ids if ids is not None else ([self.course] if scope != 'all_courses' else []))])
        result = self.db.execute('select public.manage_elearning_offering(%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.user,existing['id'] if existing else None,existing['revision'] if existing else 1,json.dumps(details))).fetchone()[0]
        return next(p for p in result['plans'] if p['id']==result['saved_plan_id'])

    def checkout(self, plan, course=None, key=None, user=None, tenant=None):
        return self.db.execute("select public.create_commerce_learning_checkout(%s,%s,%s,%s,%s,'local_test')",(tenant or self.tenant,user or self.user,plan['id'],course,key or uuid4())).fetchone()[0]['checkout']

    def event(self, checkout, state='paid', sequence=1, event_id=None, **overrides):
        terms=checkout['terms'];period=(datetime.now(timezone.utc)+timedelta(days=30)) if terms['billing_type']!='one_time' and state in ('paid','active') else None
        args=dict(tenant=self.tenant,checkout=checkout['id'],provider='local_test',event=event_id or str(uuid4()),transaction='local:'+checkout['id'],sequence=sequence,state=state,amount=terms['amount'],currency=terms['currency'],period=period,cancel=False)
        args.update(overrides)
        args["amount"]=Decimal(str(args["amount"]))
        return self.db.execute('select public.apply_commerce_payment_event(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',tuple(args.values())).fetchone()[0]

    def enroll(self, course=None):
        return self.db.execute('select public.enroll_elearning_catalog(%s,%s,%s)',(self.tenant,self.user,course or self.course)).fetchone()[0]['enrollment_id']

    def has_access(self, eid):
        return self.db.execute('select public.elearning_enrollment_has_access(%s,%s)',(self.tenant,eid)).fetchone()[0]

    def rejected(self, action, code):
        with self.db.transaction(force_rollback=True):
            with self.assertRaises(psycopg.Error) as caught: action()
            self.assertEqual(caught.exception.sqlstate,code)

    def test_billing_and_scope_independent_all_nine_combinations(self):
        for billing in ('one_time','monthly','yearly'):
            for scope in ('single_course','selected_courses','all_courses'):
                with self.subTest(billing=billing,scope=scope):
                    plan=self.plan(billing,scope,ids=[self.course,self.other] if scope=='selected_courses' else None)
                    self.assertEqual((plan['billing_type'],plan['access_scope']),(billing,scope))
                    self.event(self.checkout(plan))
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_entitlements where tenant_id=%s',(self.tenant,)).fetchone()[0],9)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_enrollments where tenant_id=%s',(self.tenant,)).fetchone()[0],0)

    def test_failed_abandoned_tampered_and_duplicate_fulfillment(self):
        plan=self.plan();ch=self.checkout(plan,self.course)
        self.rejected(lambda:self.enroll(),'42501')
        self.event(ch,'failed');self.rejected(lambda:self.enroll(),'42501')
        self.rejected(lambda:self.event(ch,sequence=2,amount=1),'22023')
        self.rejected(lambda:self.event(ch,sequence=2,currency='EUR'),'22023')
        event=str(uuid4());self.event(ch,sequence=2,event_id=event)
        self.assertTrue(self.event(ch,sequence=2,event_id=event)['duplicate'])
        self.assertTrue(self.has_access(self.enroll()))
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_entitlements where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_enrollments where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        self.rejected(lambda:self.event(ch,sequence=2,event_id=event,state='refunded'),'40001')
        key=uuid4();same=self.checkout(plan,key=key);self.assertEqual(self.checkout(plan,key=key)['id'],same['id'])
        self.rejected(lambda:self.checkout(plan,self.course,key=key),'40001')

    def test_lifetime_all_future_eligible_and_my_learning_enrollment_separation(self):
        plan=self.plan(scope='all_courses',amount='49.00');ch=self.checkout(plan);self.event(ch)
        self.assertIsNone(self.db.execute('select expires_at from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0])
        self.assertEqual(self.db.execute('select public.get_elearning_my_learning(%s,%s,50,0)',(self.tenant,self.user)).fetchone()[0],[])
        self.enroll(self.other)
        self.assertEqual(len(self.db.execute('select public.get_elearning_my_learning(%s,%s,50,0)',(self.tenant,self.user)).fetchone()[0]),1)
        future=self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Future','published','paid') returning id",(self.tenant,)).fetchone()[0]
        self.assertTrue(self.has_access(self.enroll(future)))
        self.rejected(lambda:self.enroll(self.private),'P0002')
        self.db.execute('update public.elearning_courses set catalog_visible=false where id=%s',(future,))
        self.rejected(lambda:self.enroll(future),'P0002')

    def test_subscription_expiry_reactivation_and_history_additive_manual(self):
        ch=self.checkout(self.plan('monthly','all_courses'),self.course);self.event(ch);eid=self.enroll()
        self.db.execute('update public.elearning_lessons set status=\'published\' where id=%s',(self.lesson,))
        self.db.execute('update public.elearning_sections set status=\'published\' where id=%s',(self.section,))
        self.db.execute('select public.complete_elearning_learner_lesson(%s,%s,%s,%s)',(self.tenant,self.user,self.course,self.lesson))
        self.event(ch,'expired',2);self.assertFalse(self.has_access(eid))
        self.assertEqual(self.db.execute('select count(*) from public.elearning_lesson_completions where enrollment_id=%s',(eid,)).fetchone()[0],1)
        self.event(ch,'active',3);self.assertTrue(self.has_access(eid))
        self.db.execute("insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type) values(%s,%s,%s,'manual')",(self.tenant,self.course,eid))
        self.event(ch,'expired',4);self.assertTrue(self.has_access(eid))
        self.db.execute("update public.elearning_enrollments set status='suspended' where id=%s",(eid,))
        self.assertFalse(self.has_access(eid));self.rejected(lambda:self.enroll(),'42501')
        self.event(ch,'active',5);self.assertFalse(self.has_access(eid))

    def test_bundle_archival_historical_terms_and_refund(self):
        plan=self.plan(scope='selected_courses',ids=[self.course,self.other],amount='35.00');ch=self.checkout(plan);self.event(ch)
        unrelated=self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Unrelated','published','paid') returning id",(self.tenant,)).fetchone()[0]
        self.rejected(lambda:self.enroll(unrelated),'42501')
        self.plan(existing=plan,status='archived',amount='59.00')
        self.rejected(lambda:self.checkout(plan),'42501')
        eid=self.enroll(self.other);self.assertTrue(self.has_access(eid))
        stored=self.db.execute('select terms from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0]
        self.assertEqual(stored['amount'],35);self.assertEqual(stored['access_scope'],'selected_courses')
        self.event(ch,'refunded',2);self.assertFalse(self.has_access(eid))
        self.rejected(lambda:self.event(ch,sequence=3),'42501')

    def test_tenant_relationship_draft_and_account_isolation(self):
        self.rejected(lambda:self.plan(ids=[self.private]),'22023')
        self.rejected(lambda:self.checkout(self.plan(),self.private),'42501')
        self.rejected(lambda:self.checkout(self.plan(status='draft')),'42501')
        self.rejected(lambda:self.checkout(self.plan(),tenant=self.tenant+999999),'42501')
        self.rejected(lambda:self.plan(ids=[uuid4()]),'22023')
        catalog=self.db.execute('select public.get_elearning_catalog(%s,%s)',(self.tenant,self.user)).fetchone()[0]
        self.assertNotIn(str(self.private),json.dumps(catalog))
        self.db.execute("update public.elearning_courses set status='draft' where id=%s",(self.other,))
        self.assertNotIn(str(self.other),json.dumps(self.db.execute('select public.get_elearning_catalog(%s,%s)',(self.tenant,self.user)).fetchone()[0]))

    def test_group_and_purchase_are_independent_and_cancel_at_period_end(self):
        ch=self.checkout(self.plan('yearly','single_course'),self.course);self.event(ch);eid=self.enroll()
        group=self.db.execute("insert into public.elearning_groups(tenant_id,name,status) values(%s,'Learning class','active') returning id",(self.tenant,)).fetchone()[0]
        self.db.execute('insert into public.elearning_group_members(tenant_id,group_id,user_id) values(%s,%s,%s)',(self.tenant,group,self.user))
        self.db.execute('insert into public.elearning_group_courses(tenant_id,group_id,course_id) values(%s,%s,%s)',(self.tenant,group,self.course))
        self.db.execute("insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type,source_group_id) values(%s,%s,%s,'group',%s)",(self.tenant,self.course,eid,group))
        self.event(ch,'active',2,cancel=True)
        self.assertTrue(self.has_access(eid));self.assertTrue(self.db.execute('select cancel_at_period_end from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0])
        self.event(ch,'expired',3);self.assertTrue(self.has_access(eid))
        self.db.execute('update public.elearning_group_members set removed_at=now() where group_id=%s',(group,));self.assertFalse(self.has_access(eid))
        self.event(ch,'active',4);self.assertTrue(self.has_access(eid))

    def test_expired_period_without_webhook_and_service_role_cannot_forge_records(self):
        ch=self.checkout(self.plan('monthly','all_courses'),self.course);self.event(ch);eid=self.enroll()
        self.db.execute("update public.ecommerce_entitlements set starts_at=now()-interval '2 days',expires_at=now()-interval '1 day' where checkout_id=%s",(ch['id'],))
        self.assertFalse(self.has_access(eid))
        with self.db.transaction(force_rollback=True):
            self.db.execute('set local role service_role')
            self.rejected(lambda:self.db.execute('select * from public.ecommerce_entitlements'),'42501')
            self.rejected(lambda:self.db.execute("update public.ecommerce_checkouts set state='paid'"),'42501')
