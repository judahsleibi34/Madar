"""Focused detached-candidate safety tests; never production acceptance evidence."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import DetachedRecoveryCandidate,KINDS
from deployment.lib.active_recovery_inputs import KEYS
from deployment.lib.active_recovery_resumption import ResumptionPlan
from deployment.lib.provider_local_transition import LocalTransitionContract
from deployment.lib.provider_recovery_runtime import digest


class DetachedCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        identity={'container_id':'b'*64,'image_id':'sha256:'+'c'*64,'spec_sha256':'d'*64}
        keys=KEYS
        self.plan=ResumptionPlan('a'*40,'b'*64,{'backend':'sha256:'+'c'*64,'frontend':'sha256:'+'d'*64},
            {key:'e'*64 for key in keys},{'backend':identity,'frontend':identity},'f'*64,'1'*64,'2'*64,'3'*64,'4'*64)
        fp={key:'e'*64 for key in ('environment','state','upstream','worker_authority','controller','recovery','traffic')}
        self.contract=LocalTransitionContract(self.plan.source_sha,self.plan.candidate_images,'f'*64,self.plan.checkpoint_manifest_sha256,
            self.plan.reconciliation_execution_sha256,self.plan.acceptance_execution_sha256,fp)
        self.c=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate)
        self.c.plan=self.plan;self.c.contract=self.contract;self.c.verify_recorded_runtime=lambda:None;self.c.root=Path(self.tmp.name)/self.plan.digest
        self.c.root.mkdir(mode=0o700);self.c.prefix='madar-normal-'+self.plan.digest[:12]
        self.c.network_name=self.c.prefix+'-runtime';self.c.slot='green';self.c.backend_port=8201;self.c.frontend_port=3200
        self.auth={'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}
        (self.c.root/'authorization.json').write_text(json.dumps(self.auth));(self.c.root/'authorization.json').chmod(0o600)
        self.events=[{'phase':phase,'plan_sha256':self.plan.digest} for phase in ('authorized','detached_candidate_pending')]
        self.write_events()
        for name,value in [('ROOT',Path(self.tmp.name)),('protected',lambda p,**kw:p)]:
            item=patch('deployment.lib.active_recovery_candidate.'+name,value);item.start();self.addCleanup(item.stop)
        # Owner observations are exercised independently; these fixtures cannot
        # run root-owned production code or create real Docker resources.
        self.owner=patch('deployment.lib.active_recovery_candidate.os.geteuid',return_value=0)
        self.owner.start();self.addCleanup(self.owner.stop)
        self.c.require_authorization=lambda contract:None

    def write_events(self):
        (self.c.root/'events.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in self.events));(self.c.root/'events.jsonl').chmod(0o600)

    def test_no_normal_grant_even_after_fresh_authorization(self):
        with self.assertRaisesRegex(RuntimeError,'normal_grant_forbidden'):self.c.set_write_authority(self.contract,'NORMAL')
        self.assertFalse((self.c.root/'write-authority').exists())

    def test_read_only_authority_is_separate_and_traversable_under_private_umask(self):
        previous=os.umask(0o077)
        try:self.c.set_write_authority(self.contract,'READ_ONLY')
        finally:os.umask(previous)
        directory=self.c.root/'write-authority'
        self.assertEqual(directory.stat().st_mode&0o777,0o755)
        self.assertEqual((directory/'authority.json').stat().st_mode&0o777,0o444)
        self.assertEqual(json.loads((directory/'authority.json').read_text())['mode'],'READ_ONLY')
        with self.assertRaises(FileExistsError):self.c.set_write_authority(self.contract,'READ_ONLY')

    def test_names_leave_emergency_consumer_inventory_unchanged(self):
        for kind in KINDS:self.assertNotIn(kind+'-worker',self.c.name(kind))
        self.assertNotEqual(self.c.name('backend'),'madar-green-backend')

    def test_endpoint_is_durable_across_docker_ip_reassignment(self):
        self.assertEqual(self.c.endpoint('backend'),'http://127.0.0.1:8201')
        self.assertEqual(self.c.endpoint('frontend'),'http://127.0.0.1:3200')
        with self.assertRaises(RuntimeError):self.c.endpoint('unregistered')

    def test_existing_container_prevents_any_effect(self):
        calls=[]
        def command(args):calls.append(args);return self.c.name('backend')
        self.c.command=command
        with self.assertRaisesRegex(RuntimeError,'already_exists'):self.c.require_free_destinations()
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][1:3],['ps','-a'])

    def test_retired_name_collision_prevents_any_effect(self):
        self.c.command=lambda args:'madar-green-backend-retired-'+self.plan.digest[:12]
        with self.assertRaisesRegex(RuntimeError,'already_exists'):self.c.require_free_destinations()

    def test_existing_network_prevents_any_effect(self):
        self.c.command=lambda args:self.c.network_name if args[1]=='network' else ''
        with self.assertRaisesRegex(RuntimeError,'already_exists'):self.c.require_free_destinations()

    def test_stopped_container_reserved_port_also_rejected(self):
        def command(args):
            if args[1]=='inspect':return json.dumps([{'HostConfig':{'PortBindings':{'8000/tcp':[{'HostPort':'8201'}]}}}])
            return 'abc' if args[1:3]==['ps','-aq'] else ''
        self.c.command=command
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):self.c.require_free_destinations()

    def test_modified_image_or_running_standby_rejected(self):
        self.c.inspect=lambda name:self.row(name)
        self.c.verify_identities()
        for key in ('Image','State','HostConfig','Mounts'):
            def changed(name):
                row=self.row(name)
                if name==self.c.name('notification'):
                    if key=='Image':row[key]='sha256:'+'0'*64
                    elif key=='State':row[key]={'Running':True}
                    elif key=='Mounts':row[key]=[]
                    else:row[key]['RestartPolicy']['Name']='always'
                return row
            self.c.inspect=changed
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.c.verify_identities()

    def test_loopback_port_binding_must_match_role(self):
        def changed(name):
            row=self.row(name)
            if name==self.c.name('backend'):row['HostConfig']['PortBindings']['8000/tcp'][0]['HostPort']='3200'
            return row
        self.c.inspect=changed
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):self.c.verify_identities()

    def row(self,name):
        kind=next(kind for kind in ('backend','frontend','parser',*KINDS) if name==self.c.name(kind))
        bindings=({'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':'8201'}]} if kind=='backend' else
            {'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'3200'}]} if kind=='frontend' else {})
        return {'Image':self.contract.images['frontend' if kind=='frontend' else 'backend'],
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':bindings},'State':{'Running':kind not in KINDS},
            'Config':{'Env':['MADAR_RELEASE_SHA='+self.contract.sha,'MADAR_BUSINESS_WRITE_CONTRACT='+digest(asdict(self.contract))]},
            'Mounts':[{'Source':str(self.c.root/'write-authority'),'Destination':'/run/madar/business-write-authority','RW':False}]}

    def test_unhealthy_database_rejects_read_only_acceptance(self):
        self.c.inspect=lambda name:self.row(name);self.c.require_write_authority=lambda *args:None
        version={'release_sha':self.contract.sha,'release_slot':'green','schema_compatible_min':115,'schema_compatible_max':115}
        replies=[(200,version),(503,{'components':{'database':'unavailable','auth':'ok','schema':'ok','storage':'ok'}}),
            (200,{'restricted':True,'business_writes_enabled':False})]
        with patch.object(self.c,'health_json',side_effect=replies):
            with self.assertRaisesRegex(RuntimeError,'unready'):self.c.verify_read_only()

    def test_unfenced_candidate_rejected_before_any_denial_probe(self):
        self.c.inspect=lambda name:self.row(name);self.c.require_write_authority=lambda *args:None
        version={'release_sha':self.contract.sha,'release_slot':'green','schema_compatible_min':115,'schema_compatible_max':115}
        with patch.object(self.c,'health_json',side_effect=[(200,version),(200,{}),(200,{'restricted':False,'business_writes_enabled':True})]):
            with self.assertRaisesRegex(RuntimeError,'binding_changed'):self.c.verify_read_only()

    def trusted_fixture_metadata(self):
        from types import SimpleNamespace
        original=Path.stat;original_lstat=Path.lstat
        def observation(path,*args,**kwargs):
            if path==self.c.root or path in self.c.root.parents:
                return SimpleNamespace(st_uid=0,st_mode=0o040700 if path==self.c.root else 0o040755)
            return original(path,*args,**kwargs)
        def link_observation(path,*args,**kwargs):
            if path==self.c.root or path in self.c.root.parents:return observation(path)
            return original_lstat(path,*args,**kwargs)
        return patch.object(Path,'stat',observation),patch.object(Path,'lstat',link_observation)

    def test_missing_run_credentials_do_not_affect_fresh_namespace(self):
        a,b=self.trusted_fixture_metadata()
        with a,b:self.c.require_fresh_stage()
        self.assertFalse((self.c.root/'authorized.credential').exists())

    def test_changed_approval_or_plan_denied(self):
        a,b=self.trusted_fixture_metadata()
        for key in ('plan_sha256','source_bundle_sha256','operation'):
            receipt={**self.auth,key:'changed'};(self.c.root/'authorization.json').write_text(json.dumps(receipt))
            with a,b,self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'fresh_authorization_required'):
                self.c.require_fresh_stage()

    def test_repeated_candidate_stage_or_wrong_phase_denied(self):
        a,b=self.trusted_fixture_metadata()
        self.events.append({'phase':'detached_candidate_ready','plan_sha256':self.plan.digest});self.write_events()
        with a,b,self.assertRaisesRegex(RuntimeError,'stage_not_authorized'):self.c.require_fresh_stage()

    def test_nonroot_cannot_consume_fresh_receipt(self):
        with patch('deployment.lib.active_recovery_candidate.os.geteuid',return_value=1000):
            with self.assertRaisesRegex(RuntimeError,'root_namespace_required'):self.c.require_fresh_stage()

    def test_image_source_must_match_accepted_commit(self):
        self.c.command=lambda args:json.dumps([{'Id':args[-1],'Config':{'Labels':{'org.opencontainers.image.revision':self.contract.sha}}}])
        self.c.verify_image_source()
        self.c.command=lambda args:json.dumps([{'Id':args[-1],'Config':{'Labels':{'org.opencontainers.image.revision':'0'*40}}}])
        with self.assertRaisesRegex(RuntimeError,'image_source_changed'):self.c.verify_image_source()

    def test_backup_marker_uses_directory_bind_for_atomic_updates(self):
        cfg={'BACKUP_FRESHNESS_MARKER':'/run/madar/backup-state/latest.json'}
        with patch('deployment.lib.provider_recovery_runtime.readonly_configuration',side_effect=lambda path,**kw:path),patch.object(Path,'is_dir',return_value=True),patch.object(Path,'is_symlink',return_value=False),patch.object(Path,'read_text',return_value=json.dumps({'format':2,'verified':True,'scope':'complete-coordinated-checkpoint','schema':115,'manifest_sha256':self.plan.checkpoint_manifest_sha256,'execution_sha256':self.plan.checkpoint_execution_sha256})):
            mount=self.c._backup_marker_mount(cfg)
        self.assertEqual(mount,'type=bind,src=/var/lib/madar/backup-state,dst=/run/madar/backup-state,readonly')
        self.assertNotIn('src=/var/lib/madar/backup-state/latest.json',mount)
        with self.assertRaisesRegex(RuntimeError,'destination_changed'),patch('deployment.lib.provider_recovery_runtime.readonly_configuration',side_effect=lambda path,**kw:path):
            self.c._backup_marker_mount({'BACKUP_FRESHNESS_MARKER':'/old-preparation-PASS.json'})

    def test_historical_preparation_marker_cannot_seed_normal_candidate(self):
        with patch('deployment.lib.provider_recovery_runtime.readonly_configuration',side_effect=lambda path,**kw:path),patch.object(Path,'read_text',return_value=json.dumps({'format':1,'verified':True,'manifest_sha256':'old'})):
            with self.assertRaisesRegex(RuntimeError,'proof_changed'):
                self.c._backup_marker_mount({'BACKUP_FRESHNESS_MARKER':'/run/madar/backup-state/latest.json'})


    def test_saved_runtime_reconstruction_never_reuses_stage_authority(self):
        from dataclasses import asdict,replace
        from types import SimpleNamespace
        from deployment.lib.provider_recovery import RecoveryContract
        from deployment.lib.provider_recovery_runtime import file_digest
        base=Path(self.tmp.name);recovery=base/'recovery-input';recovery.mkdir();local=base/'local-input';local.mkdir()
        metadata={'migration_policy':'none','schema':{key:115 for key in ('compatible_min','compatible_max','target','rollback_compatible_min','rollback_compatible_max')}}
        metadata['schema']['migration_class']='none'
        old=RecoveryContract('9'*40,'9'*40,'9'*40,'blue',self.plan.candidate_images,
            {key:'e'*64 for key in ('environment','state','upstream','worker_authority','controller')},'f'*64,'1'*64,'2'*64)
        (recovery/'contract.json').write_text(json.dumps(asdict(old)));(recovery/'schema-contract.json').write_text(json.dumps(metadata))
        (local/'configuration.env').write_text('synthetic')
        fingerprints=dict(self.plan.retained_inputs)
        for key,path in [('recovery_contract',recovery/'contract.json'),('schema_contract',recovery/'schema-contract.json'),('local_configuration',local/'configuration.env')]:fingerprints[key]=file_digest(path)
        plan=replace(self.plan,retained_inputs=fingerprints,candidate_destination={'slot':'green','backend_port':8201,'frontend_port':3200,'retained_slot':'blue','retained_source_sha':'9'*40,'redis_name':'madar-provider402-rehearsal-000000000000-candidate-redis','redis_network':'madar-provider402-rehearsal-000000000000-candidate-blue-runtime','redis_network_id':'a'*64,'subnet':'10.253.0.0/24','retired_port_declarations':{}});root=base/plan.digest;root.mkdir()
        (root/'authorization.json').write_text(json.dumps({**self.auth,'plan_sha256':plan.digest}))
        contract=replace(self.contract,recovery_context=digest(asdict(old)))
        (root/'candidate-contract.json').write_text(json.dumps({'version':1,'plan_sha256':plan.digest,'contract':asdict(contract)}))
        fake=SimpleNamespace(paths=SimpleNamespace(state=base/'state'))
        with (patch('deployment.lib.active_recovery_candidate.RECOVERY',recovery),patch('deployment.lib.active_recovery_candidate.LOCAL',local),
             patch('deployment.lib.active_recovery_candidate.ProductionRecoveryOperations',return_value=fake),
             patch.object(DetachedRecoveryCandidate,'_load_configuration') as load,
             patch.object(DetachedRecoveryCandidate,'require_fresh_stage',side_effect=AssertionError('stage permission reused'))):
            restored=DetachedRecoveryCandidate.from_saved_runtime(plan,root,lambda:None)
            self.assertEqual(restored.slot,'green');self.assertEqual(restored.backend_port,8201)
            self.assertEqual(restored.contract,contract);load.assert_called_once_with(local/'configuration.env')
            (recovery/'schema-contract.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'recovery_inputs_changed'):
                DetachedRecoveryCandidate.from_saved_runtime(plan,root,lambda:None)
