"""Credential hook and permission checks against a marked disposable database."""
import json
from uuid import uuid4
import unittest
from tests import test_elearning_placements_database as placements
from tests import test_elearning_commerce_database as commerce
from tests.test_elearning_content_database import DSN

@unittest.skipUnless(DSN, 'Requires marked disposable learning database')
class CredentialDatabaseTests(unittest.TestCase):
    setUpClass = placements.PlacementDatabaseTests.__dict__['setUpClass']
    command = placements.PlacementDatabaseTests.command
    media = placements.PlacementDatabaseTests.media
    snapshot = placements.PlacementDatabaseTests.snapshot
    create = placements.PlacementDatabaseTests.create
    runtime = placements.PlacementDatabaseTests.runtime
    submit = placements.PlacementDatabaseTests.submit
    denied = placements.PlacementDatabaseTests.denied

    def setUp(self):
        placements.PlacementDatabaseTests.setUp(self)
        self.design = dict(name='Standard',title='Certificate of Completion',subtitle='',body='{{learner_name}} completed {{course_name}}',issuer_name='Test Academy',signer_name='Signer',signer_title='Director',logo_url='',signature_url='',logo_image='',signature_image='')
        self.template = self.admin('template', payload={'design':self.design})['saved_id']

    def admin(self, action='list', identifier=None, payload=None, tenant=None, user=None, course=None):
        return self.db.execute('select public.manage_elearning_certificates(%s,%s,%s,%s,%s,%s::jsonb)',(tenant or self.tenant,user or self.user,course or self.course,action,identifier,json.dumps(payload or {},default=str))).fetchone()[0]

    def enable(self, enabled=True, template=None):
        return self.admin('configure',payload={'enabled':enabled,'template_id':template or self.template,'title_override':'','issuer_override':''})

    def mine(self, identifier=None, user=None, tenant=None):
        return self.db.execute('select public.get_elearning_my_certificates(%s,%s,%s)',(tenant or self.tenant,user or self.learner,identifier)).fetchone()[0]

    def finish(self):
        self.snapshot(self.lesson,complete=True);self.snapshot(self.second,complete=True)
        return self.snapshot()['progress']

    def test_formal_completion_hook_idempotency_and_snapshots(self):
        self.enable();final=self.create();self.finish();self.assertEqual(self.mine()['credentials'],[])
        self.submit(final);issued=self.mine()['credentials'];self.assertEqual(len(issued),1)
        row=self.mine(issued[0]['id']);self.assertEqual(row['snapshot']['learner_name'],'Learner Player');self.assertEqual(row['snapshot']['course_name'],'Content test')
        self.snapshot(self.second,complete=True);self.snapshot();self.assertEqual(len(self.mine()['credentials']),1)
        self.db.execute("update public.users set first_name='Changed' where id=%s",(self.learner,));self.db.execute("update public.elearning_courses set name='Renamed' where id=%s",(self.course,))
        self.admin('template',self.template,{'design':{**self.design,'title':'New title'},'expected_revision':1})
        self.assertEqual(self.mine(row['id'])['snapshot'],row['snapshot'])
        self.denied(lambda:self.db.execute("update public.elearning_credentials set snapshot='{}' where id=%s",(row['id'],)),'42501')
        event=self.db.execute('select completion_id from public.elearning_credentials where id=%s',(row['id'],)).fetchone()[0]
        self.assertEqual(str(self.db.execute('select public.elearning_issue_credential(%s)',(event,)).fetchone()[0]),row['id'])

    def test_backfill_explicit_disable_and_archive_template(self):
        self.finish();self.assertEqual(self.mine()['credentials'],[]);self.enable();self.assertEqual(self.mine()['credentials'],[])
        self.denied(lambda:self.admin('backfill',payload={'confirmed':False}),'22023')
        self.assertEqual(self.admin('backfill',payload={'confirmed':True})['issued_count'],1)
        self.assertEqual(self.admin('backfill',payload={'confirmed':True})['issued_count'],0)
        self.enable(False);self.assertEqual(len(self.mine()['credentials']),1)
        self.admin('template',self.template,{'design':self.design,'status':'archived','expected_revision':1})
        self.denied(lambda:self.enable(),'22023')
        actions=[x[0] for x in self.db.execute('select action from public.audit_logs where tenant_id=%s',(self.tenant,))]
        self.assertIn('elearning.credential.issued',actions);self.assertIn('elearning.certificate.backfill',actions)

    def test_validation_isolation_and_service_privileges(self):
        self.denied(lambda:self.admin('template',payload={'design':{**self.design,'body':'{{secret}}'}}),'22023')
        self.denied(lambda:self.admin('template',payload={'design':{**self.design,'body':'{{learner_name'}}),'22023')
        self.denied(lambda:self.admin('template',self.template,{'design':self.design,'expected_revision':99}),'40001')
        self.denied(lambda:self.admin(user=self.learner),'42501')
        self.denied(lambda:self.admin(tenant=self.tenant+999),'42501')
        self.denied(lambda:self.enable(template=uuid4()),'22023')
        for role in ('anon','authenticated','service_role'):
            self.assertFalse(self.db.execute("select has_table_privilege(%s,'public.elearning_credentials','INSERT')",(role,)).fetchone()[0])
            self.assertFalse(self.db.execute("select has_function_privilege(%s,'public.elearning_issue_credential(uuid)','EXECUTE')",(role,)).fetchone()[0])
        self.enable();self.finish();row=self.mine()['credentials'][0]
        self.denied(lambda:self.mine(row['id'],user=self.user),'P0002')
        self.denied(lambda:self.admin('view',row['id'],course=uuid4()),'P0002')
        self.denied(lambda:self.mine(row['id'],tenant=self.tenant+999),'42501')

    def test_public_revocation_and_protected_historical_dependencies(self):
        self.enable();progress=self.finish();row=self.mine(self.mine()['credentials'][0]['id'])
        verify=lambda token:self.db.execute('select public.verify_elearning_credential(%s)',(token,)).fetchone()[0]
        safe=verify(row['verification_token']);self.assertEqual(set(safe),{'learner_name','course_name','issuer_name','completed_at','issued_at','credential_number','status'})
        self.assertIsNone(verify('a'*64));self.assertIsNone(verify(row['id']))
        self.denied(lambda:self.admin('revoke',row['id'],{'confirmed':True,'reason':' '}),'22023')
        self.denied(lambda:self.admin('revoke',row['id'],{'confirmed':False,'reason':'Correction'}),'22023')
        self.admin('revoke',row['id'],{'confirmed':True,'reason':'Correction'});self.assertEqual(verify(row['verification_token'])['status'],'revoked')
        self.assertEqual(self.snapshot()['progress']['completed_at'],progress['completed_at'])
        self.db.execute("update public.elearning_courses set status='archived' where id=%s",(self.course,));self.db.execute("update public.users set account_status='disabled' where id=%s",(self.learner,))
        self.assertEqual(verify(row['verification_token'])['status'],'revoked')
        self.denied(lambda:self.db.execute('delete from public.elearning_courses where id=%s',(self.course,)),'23503')
        self.denied(lambda:self.db.execute('delete from public.elearning_completion_events where id=%s',(row['completion_id'],)),'23503')

    def test_refund_and_expiry_leave_earned_credential(self):
        self.enable();self.db.execute("update public.elearning_courses set access_type='paid' where id=%s",(self.course,))
        # Reuse the real commerce event engine; manual access remains additive.
        original=self.user;self.user=self.learner
        # Admin creates plan as owner, checkout belongs to learner.
        self.user=original;plan=commerce.LearningCommerceDatabaseTests.plan(self,billing='monthly')
        ch=commerce.LearningCommerceDatabaseTests.checkout(self,plan,self.course,user=self.learner)
        commerce.LearningCommerceDatabaseTests.event(self,ch);self.finish();row=self.mine()['credentials'][0]
        commerce.LearningCommerceDatabaseTests.event(self,ch,'expired',sequence=2)
        self.assertEqual(self.mine(row['id'])['status'],'active')
        commerce.LearningCommerceDatabaseTests.event(self,ch,'refunded',sequence=3)
        self.assertEqual(self.mine(row['id'])['status'],'active')
