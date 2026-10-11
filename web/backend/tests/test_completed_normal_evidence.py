"""Evidence reuse binds executed bytes and source; summaries cannot grant it."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deployment.lib import completed_normal_evidence as m


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source='a'*40
        self.images={'backend':'sha256:'+'b'*64,'frontend':'sha256:'+'c'*64}
        self.reports={}
        for schema in (115,136):
            cases={key:{'verified':True,'observations':{'fixture':True}} for key in m.CASES}
            cases['local_schema']['observations']={'schema':schema}
            self.reports[str(schema)]={'source_sha':self.source,'images':self.images,'cases':cases,
                'runner_sha256':'d'*64,'input_sha256':'e'*64}
        combined={'schema115':self.reports['115'],'schema136':self.reports['136'],
            'all_original_row_counts_preserved':True,
            'auth_storage_roots_preserved':{key:{'rows':2,'root':'f'*64} for key in (
                'auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets')}}
        self.execution={'status':'passed','result':{'operation':'actual-current-backup-private-native-restore',
            'production_modified':False,'schema':136,'native_login_and_aal2_verified':True,
            'role_attributes_password_verifiers_and_grantors_verified':True,'owners_and_acls_restored':True,
            'existing_factor_verification':combined}}
        self.document={'application_evidence':{},'application_artifacts':{'backend':'backend@'+self.images['backend'],
            'frontend':'frontend@'+self.images['frontend'],'build_timestamp':'fixture-time'},
            'node1_replica':{'host':'madar-node1-lan','filesystem_uuid':'fixture-volume','configuration_sha256':'1'*64},
            'live_configuration_sha256':{'node1_configuration':'1'*64}}
        self.rebind()
        def inspect(args):
            role='frontend' if args[-1].startswith('frontend') else 'backend'
            labels={'org.opencontainers.image.revision':self.source,'com.madar.release.sha':self.source,
                'com.madar.release.built_at':'fixture-time','com.madar.frontend.api_origin':'/api'}
            return json.dumps([{'Id':self.images[role],'Config':{'Labels':labels}}])
        self.actor=SimpleNamespace(document=self.document,
            contract={'candidate':{'source_sha':self.source,'images':self.images}},runtime=SimpleNamespace(command=inspect))
        p=patch.object(m,'readonly_configuration',lambda p,**kw:p);p.start();self.addCleanup(p.stop)

    def rebind(self):
        for key,value in dict(self.reports,execution=self.execution).items():
            path=self.root/(key+'.json');path.write_text(json.dumps(value,sort_keys=True))
            self.document['application_evidence'][key]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_exact_two_schema_executions_are_reused_without_changing_application_revision(self):
        result=m.verify_application_evidence(self.actor)
        self.assertEqual(result['application_source_sha'],self.source)
        self.assertFalse(result['historical_evidence_relabelled'])

    def test_changed_file_rejected_even_when_it_still_claims_pass(self):
        path=self.root/'115.json';path.write_text(path.read_text()+' ')
        with self.assertRaisesRegex(RuntimeError,'evidence_bytes_changed'):m.verify_application_evidence(self.actor)

    def test_agent_summary_without_independent_execution_is_not_acceptance(self):
        self.execution={'status':'passed','result':{'schema':136,'production_modified':False}}
        self.rebind()
        with self.assertRaisesRegex(RuntimeError,'execution_incomplete'):m.verify_application_evidence(self.actor)

    def test_changed_source_or_unexecuted_schema_case_rejects_even_rebound_packet(self):
        self.reports['115']['source_sha']='9'*40;self.rebind()
        with self.assertRaisesRegex(RuntimeError,'acceptance_incompatible'):m.verify_application_evidence(self.actor)
        self.reports['115']['source_sha']=self.source
        self.reports['136']['cases']['tenant_isolation']['verified']=False;self.rebind()
        with self.assertRaisesRegex(RuntimeError,'acceptance_incompatible'):m.verify_application_evidence(self.actor)

    def test_image_bytes_or_provenance_change_rejects_original_good_acceptance(self):
        good=self.actor.runtime.command
        def changed(args):
            rows=json.loads(good(args));rows[0]['Id']='sha256:'+'0'*64;return json.dumps(rows)
        self.actor.runtime.command=changed
        with self.assertRaisesRegex(RuntimeError,'accepted_image_changed'):m.verify_application_evidence(self.actor)
        def relabelled(args):
            rows=json.loads(good(args));rows[0]['Config']['Labels']['com.madar.release.sha']='0'*40
            return json.dumps(rows)
        self.actor.runtime.command=relabelled
        with self.assertRaisesRegex(RuntimeError,'provenance_changed'):m.verify_application_evidence(self.actor)

    def test_missing_original_mfa_root_is_not_data_preservation(self):
        del self.execution['result']['existing_factor_verification']['auth_storage_roots_preserved']['auth.mfa_factors']
        self.rebind()
        with self.assertRaisesRegex(RuntimeError,'execution_incomplete'):m.verify_application_evidence(self.actor)

    def test_unit_results_and_old_rehearsal_cannot_authorize_new_source(self):
        self.actor.contract.update(rehearsal_sha256='2'*64)
        self.actor.contract['candidate']['controller_sha']='3'*40
        self.document['source_bundle_sha256']='4'*64
        path=self.root/'rehearsal.json';path.write_text(json.dumps({'status':'passed','tests':111}))
        self.document['complete_rehearsal']={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(RuntimeError,'rehearsal_source_binding_changed'):m.verify_complete_rehearsal(self.actor)

if __name__=='__main__':unittest.main()
