"""Independent CEFR credentials reuse formal events and existing issuance."""
import unittest
from tests.test_elearning_credentials_database import CredentialDatabaseTests
from tests.test_elearning_content_database import DSN


@unittest.skipUnless(DSN,'Requires marked disposable learning database')
class CEFRDatabaseTests(CredentialDatabaseTests):
    def setUp(self):
        super().setUp()
        self.db.execute("insert into public.elearning_settings(tenant_id,settings) values(%s,'{\"eduhope_enabled\":true,\"learning_notifications_enabled\":true}') on conflict(tenant_id) do update set settings=excluded.settings",(self.tenant,))

    def configure(self, level='A1', section=None):
        self.db.execute('select public.configure_elearning_cefr(%s,%s,%s,%s,%s,%s,true)',(self.tenant,self.user,self.course,section or self.section,level,self.template))

    def test_section_exam_issues_cefr_without_complete_course_certificate(self):
        self.denied(self.configure,'22023')
        section=self.create(self.section);final=self.create()
        self.configure();self.finish();self.assertEqual(self.mine()['credentials'],[])
        self.submit(section,False);self.assertEqual(self.mine()['credentials'],[])
        self.submit(section);rows=self.mine()['credentials'];self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['credential_type'],'cefr_A1');self.assertEqual(rows[0]['snapshot']['cefr_level'],'A1')
        self.snapshot();self.assertEqual(len(self.mine()['credentials']),1)
        self.assertFalse(self.snapshot()['progress']['completion']['completed'])
        self.enable();self.submit(final);self.assertEqual(len(self.mine()['credentials']),2)
        self.admin('revoke',rows[0]['id'],{'confirmed':True,'reason':'Administrative correction'})
        self.assertEqual(self.mine(rows[0]['id'])['status'],'revoked')

        events={row[0] for row in self.db.execute("select distinct event_type from public.notification_events where tenant_id=%s",(self.tenant,))}
        self.assertTrue({'learning_topic_completed','learning_section_completed','learning_course_completed','learning_exam_submitted','learning_exam_result','learning_certificate_issued','learning_certificate_revoked'} <= events)
