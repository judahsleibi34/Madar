"""Migration 145 admin review controls, on the marked disposable SQL rehearsal only."""
import json
from decimal import Decimal
from uuid import uuid4
from tests.test_academy_referrals_database import AcademyReferralDatabaseTests


class AcademyAdminControlsDatabaseTests(AcademyReferralDatabaseTests):
    def configure(self, **values):
        self.db.execute("update public.elearning_settings set settings=settings||%s::jsonb where tenant_id=%s", (json.dumps(values), self.tenant))

    def paid_purchase(self, state='paid', checkout=None):
        """A real-provider purchase by the referred learner (test-mode sales never count)."""
        if checkout is None:
            checkout = self.db.execute("select public.create_commerce_learning_checkout(%s,%s,%s,%s,%s,'stripe')", (self.tenant, self.referred, self.plan()['id'], None, uuid4())).fetchone()[0]['checkout']
        sequence = 1 if state == 'paid' else 2
        self.db.execute('select public.apply_commerce_payment_event(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (self.tenant, checkout['id'], 'stripe', str(uuid4()), 'pi_' + checkout['id'], sequence, state, Decimal(str(checkout['terms']['amount'])), checkout['terms']['currency'], None, False))
        return checkout

    def reward(self):
        return self.db.execute('select w.status from public.academy_referral_rewards w join public.academy_referrals r on(r.tenant_id,r.id)=(w.tenant_id,w.referral_id) where r.tenant_id=%s and r.referred_id=%s', (self.tenant, self.referred)).fetchone()

    def referral_id(self):
        return self.db.execute('select id from public.academy_referrals where tenant_id=%s and referred_id=%s', (self.tenant, self.referred)).fetchone()[0]

    def wallet(self):
        return self.db.execute('select public.academy_wallet_values(%s,%s)', (self.tenant, self.user)).fetchone()[0]

    def audit(self, action):
        row = self.db.execute("select metadata from public.audit_logs where tenant_id=%s and action=%s order by created_at desc limit 1", (self.tenant, action)).fetchone()
        return row and row[0]

    def test_rewards_stay_immediate_without_the_review_setting(self):
        self.attach(); self.activate(); self.paid_purchase()
        self.assertEqual(self.reward()[0], 'earned')
        self.assertEqual(self.account()['history'][0]['reward_status'], 'earned')

    def test_reviewed_rewards_count_only_after_approval(self):
        self.configure(referral_reward_review_required=True)
        self.attach(); self.activate()
        self.assertIsNone(self.account()['history'][0]['reward_status'])  # sign-up only
        self.paid_purchase()
        self.assertEqual(self.reward()[0], 'pending')
        self.assertEqual(self.account()['history'][0]['reward_status'], 'pending')
        self.assertEqual((self.wallet()['verified_sales'], Decimal(str(self.wallet()['total_earned']))), (0, Decimal('0')))
        self.configure(programmes_enabled=True)
        self.db.execute('select public.academy_review_reward(%s,%s,%s,%s,%s)', (self.tenant, self.user, self.referral_id(), 'earned', ''))
        self.assertEqual(self.reward()[0], 'earned')
        self.assertEqual(self.wallet()['verified_sales'], 1)
        self.assertEqual(self.audit('academy.reward.approved')['previous_status'], 'pending')
        self.rejected(lambda: self.db.execute('select public.academy_review_reward(%s,%s,%s,%s,%s)', (self.tenant, self.user, self.referral_id(), 'rejected', 'late')), '40001')

    def test_rejection_needs_a_reason_and_refunds_reverse_pending_rewards(self):
        self.configure(referral_reward_review_required=True)
        self.attach(); self.activate(); checkout = self.paid_purchase()
        self.configure(programmes_enabled=True)
        self.rejected(lambda: self.db.execute('select public.academy_review_reward(%s,%s,%s,%s,%s)', (self.tenant, self.user, self.referral_id(), 'rejected', ' ')), '22023')
        self.rejected(lambda: self.db.execute('select public.academy_review_reward(%s,%s,%s,%s,%s)', (self.tenant, self.referred, self.referral_id(), 'earned', '')), '42501')
        self.paid_purchase('refunded', checkout)
        self.assertEqual(self.reward()[0], 'reversed')
        self.assertEqual(self.wallet()['verified_sales'], 0)

    def test_tuition_override_requires_a_reason_and_is_audited(self):
        self.configure(programmes_enabled=True, tuition_support_enabled=True, tuition_sales_threshold=4)
        self.assertFalse(self.wallet()['tuition_eligible'])
        override = lambda eligible, reason: self.db.execute('select public.academy_set_tuition_override(%s,%s,%s,%s,%s)', (self.tenant, self.user, self.user, eligible, reason))
        self.rejected(lambda: override(True, ''), '22023')
        override(True, 'Approved hardship case reviewed by the board')
        self.assertTrue(self.wallet()['tuition_eligible'])
        self.assertTrue(self.wallet()['tuition_override'])
        self.assertEqual(self.audit('academy.tuition_override.set')['reason'], 'Approved hardship case reviewed by the board')
        override(None, 'Override no longer needed')
        self.assertFalse(self.wallet()['tuition_eligible'])
        self.assertIsNone(self.wallet()['tuition_override'])
        self.assertTrue(self.audit('academy.tuition_override.cleared')['previous'])

    def test_manual_institution_verification_and_audit_log(self):
        self.db.execute('select public.academy_set_institution_verification(%s,%s,%s,%s,%s)', (self.tenant, self.user, self.referred, True, 'Student card checked'))
        verified = self.db.execute('select exists(select 1 from public.academy_institution_verifications where tenant_id=%s and user_id=%s)', (self.tenant, self.referred)).fetchone()[0]
        self.assertTrue(verified)
        entries = self.db.execute('select public.academy_audit_log(%s,%s,%s,%s)', (self.tenant, self.user, 50, 0)).fetchone()[0]['entries']
        self.assertEqual(entries[0]['action'], 'academy.institution.verified')
        self.assertEqual(entries[0]['metadata']['note'], 'Student card checked')
        self.rejected(lambda: self.db.execute('select public.academy_audit_log(%s,%s,%s,%s)', (self.tenant, self.referred, 50, 0)), '42501')
        self.rejected(lambda: self.db.execute('select public.academy_audit_log(%s,%s,%s,%s)', (self.tenant + 100000, self.user, 50, 0)), '42501')
        self.db.execute('select public.academy_set_institution_verification(%s,%s,%s,%s,%s)', (self.tenant, self.user, self.referred, False, ''))
        self.assertEqual(self.db.execute('select count(*) from public.academy_institution_verifications where tenant_id=%s', (self.tenant,)).fetchone()[0], 0)
