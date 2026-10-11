import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import Response
from services.notification_service import _format_notification


class AffiliateNotificationExperienceTests(unittest.TestCase):
    def notification(self, event, path='/my-learning/account', tenant='7'):
        return {'tenant_id': 7, 'event_type': event, 'data': {'action': {'kind': 'learning', 'path': path, 'tenant_id': tenant}}}

    def test_existing_recipient_events_open_focused_account_destinations(self):
        for event, path in [('learning_affiliate_submitted', '/my-learning/affiliate'),
                            ('learning_referral_attributed', '/my-learning/referrals'),
                            ('learning_reward_earned', '/my-learning/rewards'),
                            ('learning_reward_reversed', '/my-learning/rewards'),
                            ('learning_withdrawal_paid', '/my-learning/withdrawals')]:
            with self.subTest(event=event):
                row = self.notification(event)
                self.assertEqual(_format_notification(row)['data']['action']['path'], path)
                self.assertEqual(row['data']['action']['path'], '/my-learning/account')

    def test_owner_unknown_foreign_and_explicit_destinations_are_preserved(self):
        for row in [self.notification('learning_reward_earned_owner', '/e-learning/reports'),
                    self.notification('learning_application_approved', '/my-learning/programmes'),
                    self.notification('learning_reward_earned', tenant='8'),
                    self.notification('learning_reward_earned', path='https://foreign.example'),
                    self.notification('learning_reward_earned', path='/my-learning/rewards')]:
            self.assertEqual(_format_notification(row)['data'], row['data'])

    def test_member_context_does_not_require_enrollment_and_uses_session_tenant(self):
        from routes.academy_programme_routes import capabilities
        actor = SimpleNamespace(tenant_id=7, user_id=9, role='learner')
        config = {'enabled': True, 'academy_enabled': True, 'programmes_enabled': True, 'affiliates_enabled': True}
        with patch('routes.academy_programme_routes.member', return_value=actor), \
             patch('services.academy_capability_service.capabilities', return_value={'affiliate': True, 'tuition': False, 'exchange': False}), \
             patch('routes.academy_programme_routes.service.get_settings', return_value=config), \
             patch('routes.academy_programme_routes.service.settings_available', return_value=True), \
             patch('services.elearning_academy_service.member_profile', return_value={'subdomain': 'academy'}) as profile:
            result = capabilities(SimpleNamespace(), Response())
        self.assertFalse(result['can_manage'])
        self.assertTrue(result['programme_flags']['affiliate'])
        profile.assert_called_once_with(7)
        self.assertEqual(result['academy']['subdomain'], 'academy')
