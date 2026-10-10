"""Referral money ledger behavior on the marked disposable SQL rehearsal only."""
import json
import os
from uuid import uuid4
from tests.test_elearning_commerce_database import LearningCommerceDatabaseTests


class AcademyReferralDatabaseTests(LearningCommerceDatabaseTests):
    def setUp(self):
        super().setUp()
        self.db.execute("insert into public.elearning_settings(tenant_id,settings) values(%s,%s::jsonb) on conflict(tenant_id) do update set settings=excluded.settings", (self.tenant,json.dumps({'referral_rewards_enabled':True,'referral_reward_amount':'5.25','referral_reward_currency':'USD'})))
        self.code=self.account()['code']
        auth=uuid4()
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,f'{auth}@example.com'))
        self.referred=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Referred','Learner',%s,%s,'pending_verification',false) returning id",(auth,f'{auth}@example.com',self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'learner','active')",(self.tenant,self.referred,auth))

    def account(self, tenant=None, user=None):
        return self.db.execute('select public.get_academy_referral_account(%s,%s)',(tenant or self.tenant,user or self.user)).fetchone()[0]

    def attach(self, code=None, user=None, tenant=None):
        self.db.execute('select public.attach_academy_referral(%s,%s,%s)',(tenant or self.tenant,user or self.referred,code or self.code))

    def activate(self):
        self.db.execute("update public.users set account_status='active',email_verified=true where id=%s",(self.referred,))

    def test_first_purchase_snapshot_exactly_once_and_reversal(self):
        self.attach();self.activate()
        self.assertEqual(self.account()['history'][0]['status'],'pending')
        self.db.execute("update public.elearning_settings set settings=settings || '{\"referral_reward_amount\":\"10.00\",\"referral_reward_currency\":\"EUR\"}'::jsonb where tenant_id=%s",(self.tenant,))
        plan=self.plan();checkout=self.checkout(plan,user=self.referred);event=str(uuid4())
        self.event(checkout,event_id=event);self.event(checkout,event_id=event)
        balance=self.account()['balances'][0]
        self.assertEqual((balance['amount'],balance['currency'],balance['simulated']),(5.25,'USD',True))
        self.event(self.checkout(plan,user=self.referred))
        self.assertEqual(self.account()['earned_count'],1)
        self.event(checkout,'refunded',2)
        self.assertEqual(self.account()['balances'][0]['amount'],0)
        self.assertEqual(self.account()['history'][0]['status'],'reversed')

    def test_invalid_cross_tenant_self_existing_and_duplicate_referrals(self):
        self.rejected(lambda:self.attach(code=uuid4()),'22023')
        self.rejected(lambda:self.attach(user=self.user),'42501')
        self.attach();self.rejected(self.attach,'23505')
        self.activate();self.rejected(self.attach,'42501')
        self.rejected(lambda:self.account(tenant=self.tenant+100000),'42501')

    def test_signup_failure_or_free_enrollment_does_not_reward(self):
        self.attach()
        self.assertEqual(self.account()['earned_count'],0)
        self.assertEqual(self.account()['balances'],[])
        self.db.execute('delete from public.tenant_memberships where tenant_id=%s and user_id=%s',(self.tenant,self.referred))
        self.db.execute('delete from public.users where id=%s',(self.referred,))
        self.assertEqual(self.account()['referred_count'],0)

    def test_no_credit_without_verified_payment_event(self):
        self.attach();self.activate();checkout=self.checkout(self.plan(),user=self.referred)
        self.db.execute("update public.ecommerce_checkouts set state='paid' where id=%s",(checkout['id'],))
        self.assertEqual(self.account()['earned_count'],0)

    def test_disabled_program_stops_new_attribution_but_honors_existing_terms(self):
        self.attach();self.activate()
        self.db.execute("update public.elearning_settings set settings=settings || '{\"referral_rewards_enabled\":false}'::jsonb where tenant_id=%s",(self.tenant,))
        self.assertIsNone(self.account()['code'])
        self.event(self.checkout(self.plan(),user=self.referred))
        self.assertEqual(self.account()['balances'][0]['amount'],5.25)

    def test_concurrent_first_purchases_credit_one_reward(self):
        from concurrent.futures import ThreadPoolExecutor
        from decimal import Decimal
        import psycopg
        self.attach();self.activate();plan=self.plan()
        checkouts=[self.checkout(plan,user=self.referred),self.checkout(plan,user=self.referred)]
        self.db.commit()  # Fixtures remain only in the marked disposable rehearsal.
        def pay(checkout):
            with psycopg.connect(os.environ["ELEARNING_SYNTHETIC_DATABASE_DSN"]) as db:
                return db.execute('select public.apply_commerce_payment_event(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(self.tenant,checkout['id'],'local_test',str(uuid4()),'local:'+checkout['id'],1,'paid',Decimal(str(checkout['terms']['amount'])),checkout['terms']['currency'],None,False)).fetchone()[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(pay,checkouts))
        self.assertEqual(self.account()['earned_count'],1)
        self.assertEqual(self.account()['balances'][0]['amount'],5.25)

    def test_restricted_rpc_and_private_tables(self):
        for role in ('anon','authenticated'):
            with self.db.transaction(force_rollback=True):
                self.db.execute('set local role '+role)
                with self.assertRaises(Exception): self.account()
