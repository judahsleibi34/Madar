"""Package preparation, not release acceptance. Ownership is modeled here.

Git object tests use a real local repository. Publisher tests exercise the real
entrypoint measurement and canonical SQL validator, with only private-file/root
ownership checks substituted; no issuer, provider or execution actor is used.
"""
import copy,hashlib,importlib.util,json,os,shutil,subprocess,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch,Mock
from deployment.lib import completed_normal_package as producer
from deployment.lib.completed_normal_admission import encoded,digest
from deployment.lib.completed_normal_profile import RECONCILED,profile
from deployment.lib.completed_normal_resources import candidate_roles,candidate_image
from test_schema160_release import reconciled_contract
from test_schema150_actor_inventory import fixture,repin
from test_completed_normal_private_acceptance import subjects

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('producer_boot_measurement',WEB/'scripts/continue_completed_normal_upgrade.py')
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)


def inputs():
    from deployment.lib.completed_normal_boot_actor import CONFIGURATIONS
    contract=reconciled_contract();contract.pop('plan_sha256')
    (inventory,scope),_=fixture()
    scope.update(operation=RECONCILED.operation,target_schema=160,source_sha=contract['candidate']['source_sha'],
        controller_sha=contract['candidate']['controller_sha'],system_identifier=contract['database']['system_identifier'])
    inventory,scope=repin(inventory,scope);contract['writer_inventory_sha256']=scope['inventory_sha256']
    probes={'version':1,'system_identifier':contract['database']['system_identifier'],'subjects':subjects()}
    plan={'controller_source_sha':contract['candidate']['controller_sha'],'admission_contract':contract,
        'application_artifacts':{},'application_evidence':{},'live_configuration_sha256':{k:'c'*64 for k in CONFIGURATIONS},
        'installed_controller_tree_sha256':'b'*64,'origin_routing_sha256':'d'*64,'proxy_nginx_sha256':'e'*64,
        'boot_resources':{},'backup_timer_states':{},'node1_replica':{},'original_provider_probe_sha256':digest(probes),
        'fixture_only':True,'production_authorization':False}
    model={'services':{role:{'image':candidate_image(contract,role)} for role in candidate_roles(contract)}}
    return plan,inventory,probes,model


class InputTests(unittest.TestCase):
    def test_entrypoints_are_protected_control_plane_inputs(self):
        from deployment.lib.control_plane_upgrade import PROTECTED_PATHS
        for path in ('web/scripts/prepare_completed_normal_package.py','web/scripts/continue_completed_normal_upgrade.py'):
            self.assertIn(path,PROTECTED_PATHS)

    def test_exact_preparation_inputs_do_not_register_or_authorize_operation(self):
        plan,inventory,probes,model=inputs()
        prepared=producer.validate_inputs(plan,inventory,probes,model)
        self.assertEqual(prepared['plan_sha256'],'0'*64)
        self.assertNotIn('plan_sha256',plan['admission_contract'])
        with self.assertRaisesRegex(RuntimeError,'operation_profile_invalid'):profile(prepared)

    def test_mismatched_source_inventory_probes_images_or_production_request_refuse(self):
        mutations=[lambda p,i,s,m:p.update(controller_source_sha='f'*40),
            lambda p,i,s,m:p.update(production_authorization=True),
            lambda p,i,s,m:p.pop('boot_resources'),
            lambda p,i,s,m:p.update(operation_id=str(uuid.uuid4())),
            lambda p,i,s,m:p['admission_contract'].update(plan_sha256='c'*64),
            lambda p,i,s,m:i['target_credentials'].update(database_password='e'*64),
            lambda p,i,s,m:s['subjects'][0].update(password='different'),
            lambda p,i,s,m:m['services']['backend'].update(image='sha256:'+'f'*64),
            lambda p,i,s,m:m['services']['backend'].update(image='unapproved'+m['services']['backend']['image']),
            lambda p,i,s,m:m['services'].pop('provider-gateway'),
            lambda p,i,s,m:p['live_configuration_sha256'].update(unexpected='f'*64)]
        for mutate in mutations:
            args=inputs();mutate(*args)
            with self.subTest(mutation=mutate),self.assertRaises(RuntimeError):producer.validate_inputs(*args)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.files={}
        # Every required library plus actual immutable14SQL/mirrors/metadata.
        names=set(boot.REQUIRED_FILES)
        from deployment.lib.schema160_release import MANIFEST,BRIDGE
        names.update('web/deployment/releases/'+n for n in (MANIFEST,BRIDGE))
        raw=json.loads((WEB/'deployment/releases'/MANIFEST).read_bytes())
        for row in raw['migrations']:
            names.update((row['path'],row['path'].replace('/database/','/supabase/')))
        inert_build_inputs={'web/backend/requirements.txt','web/backend/constraints.txt',
            'web/frontend/package.json','web/frontend/package-lock.json'}
        for name in names:
            path=WEB/Path(name).relative_to('web') if name.startswith('web/') else WEB/name
            if not name.startswith('web/') and not path.is_file():path=WEB.parent/name
            if not path.is_file() and name.startswith(('web/database/','web/supabase/')):
                # The backend workflow mounts SQL at /database and /supabase.
                # Always read the actual pinned bytes; never stub migrations.
                path=Path('/')/Path(name).relative_to('web')
            if path.is_file():body=path.read_bytes()
            elif name in inert_build_inputs:
                # CI mounts executable source/SQL, not all package manifests.
                # These inert bytes test hashing only; no build is accepted.
                body=b'fixture-only-build-input; not artifact acceptance\n'
            else:raise FileNotFoundError(name)
            self.files[name]=('100644',body)
        self.args=inputs();self.sha=self.args[0]['controller_source_sha'];self.tree='a'*40
        self.authentication={'sha':self.sha,'commit':{'tree':{'sha':self.tree}}}
        self.enterContext(patch('deployment.lib.control_plane_upgrade.require_root_directory',lambda *a,**kw:None))
        # runpy loads the real source; model only filesystem ownership, not its
        # inventory, checksums, canonicalization or input binding.
        original=producer.runpy.run_path
        def measurement(*args,**kwargs):
            ns=original(*args,**kwargs);ns['measure'].__globals__['secured']=lambda p,**kw:p
            return ns
        self.enterContext(patch.object(producer.runpy,'run_path',side_effect=measurement))
        self.enterContext(patch.object(boot,'secured',lambda p,**kw:p))

    def freeze(self,**kwargs):
        return producer.freeze(self.base,self.sha,self.tree,self.files,*self.args,self.authentication,**kwargs)

    def test_publish_is_canonical_immutable_and_measured_by_actual_entrypoint(self):
        result=self.freeze();path=Path(result['package'])
        plan,source=boot.measure(path,result['source_bundle_sha256'],result['plan_sha256'],base=self.base)
        self.assertEqual(result['operation_id'],plan['operation_id'])
        self.assertEqual(result['attempt_id'],plan['attempt_id'])
        self.assertEqual(result['context_sha256'],digest(dict(plan['admission_contract'],plan_sha256=digest(plan))))
        self.assertEqual((path/'original-provider-probes.json').stat().st_mode&0o777,0o400)
        self.assertEqual(source.stat().st_mode&0o777,0o500)
        self.assertFalse(result['authority_issued']);self.assertFalse(result['operational_admission'])
        again=self.freeze()
        self.assertNotEqual(result['operation_id'],again['operation_id'])
        self.assertNotEqual(result['attempt_id'],again['attempt_id'])
        self.assertNotEqual(result['package'],again['package'])

    def test_mutated_inputs_or_source_are_rejected_before_execution(self):
        result=self.freeze();path=Path(result['package'])
        for name in ('source-authentication.json','candidate-model.json','original-provider-probes.json','provider-inventory-input.json'):
            p=path/name;body=p.read_bytes();p.chmod(0o600);p.write_bytes(body+b'\n')
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'package_input_changed'):
                boot.measure(path,result['source_bundle_sha256'],result['plan_sha256'],base=self.base)
            p.write_bytes(body);p.chmod(0o400)
        p=path/'source'/next(iter(self.files));p.chmod(0o600);p.write_bytes(b'substituted')
        with self.assertRaisesRegex(RuntimeError,'source_bytes_changed'):
            boot.measure(path,result['source_bundle_sha256'],result['plan_sha256'],base=self.base)

    def test_changed_remote_source_and_unsafe_paths_never_publish(self):
        self.authentication['commit']['tree']['sha']='f'*40
        with self.assertRaisesRegex(RuntimeError,'remote_source_changed'):self.freeze()
        self.authentication['commit']['tree']['sha']=self.tree
        for name in ('../escape','/absolute','web/../escape','.git/config'):
            self.files[name]=('100644',b'bad')
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'source_inventory_invalid'):self.freeze()
            del self.files[name]
        self.assertEqual(list(self.base.iterdir()),[])

    def test_invalid_migration_bytes_remove_only_own_incomplete_package(self):
        sentinel=self.base/'retained';sentinel.mkdir();(sentinel/'data').write_bytes(b'preserve')
        name=next(n for n in self.files if '/database/migrations/' in n)
        mode,body=self.files[name];self.files[name]=(mode,body+b'\n')
        with self.assertRaises(RuntimeError):self.freeze()
        self.assertEqual(list(self.base.iterdir()),[sentinel]);self.assertEqual((sentinel/'data').read_bytes(),b'preserve')


class GitSnapshotTests(unittest.TestCase):
    def test_snapshot_reads_committed_binary_bytes_and_ignores_dirty_untracked_files(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
            git('init','-q');git('remote','add','origin','https://github.com/judahsleibi34/Madar.git')
            (root/'.gitignore').write_bytes(b'ignored\n');(root/'binary').write_bytes(b'\0\xff')
            git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic')
            sha=git('rev-parse','HEAD');(root/'binary').write_bytes(b'dirty');(root/'untracked').write_bytes(b'private')
            tree,files=producer.snapshot(root,sha)
            self.assertEqual(tree,git('rev-parse','HEAD^{tree}'))
            self.assertEqual(files['binary'],('100644',b'\0\xff'));self.assertEqual(set(files),{'.gitignore','binary'})
            import zlib
            oid=git('rev-parse','HEAD^{tree}');path=root/'.git/objects'/oid[:2]/oid[2:]
            original=path.read_bytes();path.chmod(0o600);path.write_bytes(zlib.compress(zlib.decompress(original).replace(b'binary',b'forged')))
            with self.assertRaisesRegex(RuntimeError,'source_object_changed|source_git_verification_failed'):producer.snapshot(root,sha)
            path.write_bytes(original)
            (root/'link').symlink_to('/etc/passwd');git('add','link')
            git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','bad fixture')
            with self.assertRaisesRegex(RuntimeError,'source_inventory_invalid'):producer.snapshot(root,git('rev-parse','HEAD'))


class RunningOriginTests(unittest.TestCase):
    def setUp(self):
        from deployment.lib.completed_normal_resources import ROLES,measured_spec
        from test_schema150_actor_inventory import row
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.contract=reconciled_contract();self.rows={};runtimes={}
        for n,role in enumerate(ROLES,1):
            actor=row(f'{n:064x}','origin-'+role,running=True,source=self.contract['source_roles']['application_sha'])
            actor['Image']=self.contract['origin']['images']['frontend' if role=='frontend' else 'backend']
            actor['State']['Health']={'Status':'healthy'};self.rows[role]=actor
            runtimes[role]={'id':actor['Id'],'image':actor['Image'],'spec_sha256':measured_spec(actor)}
        self.record={'source_sha':self.contract['source_roles']['application_sha'],'images':self.contract['origin']['images'],
            'worker_generation':self.contract['origin']['worker_generation'],'runtimes':runtimes}
        self.runtime=Mock();self.runtime.inspect.side_effect=lambda *a:self.rows
        self.runtime.command.return_value=json.dumps([self.contract['database']['system_identifier'],146])
        self.version={'release_sha':self.contract['source_roles']['application_sha'],'release_slot':self.contract['origin']['slot'],
            'schema_compatible_min':144,'schema_compatible_max':146}
        def http(url):
            if url.endswith('/health/version'):return self.version
            if url.endswith('/health/ready'):return {'ready':True}
            if url.endswith('/health/recovery'):return {'restricted':False,'business_writes_enabled':True}
            self.fail('unexpected origin probe')
        self.runtime.json_http.side_effect=http
        self.owner={'owner':'CANDIDATE','generation':self.contract['origin']['worker_generation'],
            'candidate':{'sha':self.contract['source_roles']['application_sha'],'slot':self.contract['origin']['slot']}}
        self.enterContext(patch('deployment.lib.runtime_authority.load_worker_authority',side_effect=lambda *a:self.owner))
        self.enterContext(patch.object(producer,'protected',lambda p,**kw:self.root/Path(p).name))
        for path in self.contract['historical_files']:(self.root/Path(path).name).write_bytes(b'synthetic history only')
        self.grant={'version':2,'schema':146,'release_sha':self.contract['source_roles']['application_sha'],
            'contract_digest':self.contract['origin']['write_contract_digest'],'mode':'NORMAL','compatible_min':144,'compatible_max':146}
        (self.root/'authority.json').write_bytes(encoded(self.grant))
        self.publish()

    def publish(self):
        (self.root/'candidate-runtime.json').write_bytes(encoded(self.record))
        for path in self.contract['historical_files']:
            self.contract['historical_files'][path]=hashlib.sha256((self.root/Path(path).name).read_bytes()).hexdigest()

    def test_all_eight_healthy_original_roles_version_and_owner_are_required(self):
        self.assertEqual(producer.observe_origin(self.contract,self.runtime)['source_sha'],self.record['source_sha'])
        self.runtime.inspect.assert_called_once()
        self.assertIn('BEGIN READ ONLY;',self.runtime.command.call_args.args[0][-1])

    def test_a_database_or_new_source_at146_cannot_substitute_for_running_origin(self):
        for fault in ('stopped-worker','unhealthy','image','spec','source','owner','range','history'):
            rows=copy.deepcopy(self.rows);record=copy.deepcopy(self.record);version=copy.deepcopy(self.version);owner=copy.deepcopy(self.owner)
            worker=self.rows['notification-worker']
            if fault=='stopped-worker':worker['State']['Running']=False
            elif fault=='unhealthy':worker['State']['Health']['Status']='starting'
            elif fault=='image':worker['Image']='sha256:'+'f'*64
            elif fault=='spec':worker['Config']['Env'].append('SUBSTITUTED=1')
            elif fault=='source':self.record['source_sha']='f'*40;self.publish()
            elif fault=='owner':self.owner['candidate']['sha']='f'*40
            elif fault=='range':self.version['schema_compatible_max']=160
            else:(self.root/'normal-completion.json').write_bytes(b'changed')
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):producer.observe_origin(self.contract,self.runtime)
            self.rows,self.record,self.version,self.owner=rows,record,version,owner
            for path in self.contract['historical_files']:(self.root/Path(path).name).write_bytes(b'synthetic history only')
            self.publish()

    def test_fenced_or_widened_authority_and_foreign_database_refuse(self):
        for changes in ({'mode':'READ_ONLY'},{'schema':160},{'compatible_max':160},{'release_sha':'f'*40}):
            (self.root/'authority.json').write_bytes(encoded(dict(self.grant,**changes)))
            with self.subTest(changes=changes),self.assertRaisesRegex(RuntimeError,'origin_authority_changed'):
                producer.observe_origin(self.contract,self.runtime)
        (self.root/'authority.json').write_bytes(encoded(self.grant))
        for observed in ([self.contract['database']['system_identifier'],160],['99999999',146]):
            self.runtime.command.return_value=json.dumps(observed)
            with self.subTest(observed=observed),self.assertRaisesRegex(RuntimeError,'origin_database_changed'):
                producer.observe_origin(self.contract,self.runtime)


if __name__=='__main__':unittest.main()


class HistoricalOriginProducerTests(unittest.TestCase):
    publish=RunningOriginTests.publish
    def setUp(self):
        RunningOriginTests.setUp(self)
        from test_historical_origin import HistoricalPreparationBindingTests
        from deployment.lib import historical_origin
        self.contract=HistoricalPreparationBindingTests().contract()
        self.record.update(source_sha=self.contract['source_roles']['application_sha'],images=self.contract['origin']['images'],worker_generation=self.contract['origin']['worker_generation'])
        self.owner.update(generation=self.contract['origin']['worker_generation'],candidate={'sha':self.contract['source_roles']['application_sha'],'slot':self.contract['origin']['slot']})
        value={'runtime':{'/madar-'+self.contract['origin']['slot']+'-'+role:row for role,row in self.record['runtimes'].items()},'worker_authority':self.owner}
        self.enterContext(patch.object(historical_origin,'validate_source_binding',return_value=self.root))
        self.enterContext(patch.object(historical_origin,'recorded_observation',return_value=value))
        self.enterContext(patch.object(historical_origin,'attest',return_value=self.contract['source_roles']))
        self.enterContext(patch('deployment.lib.control_plane_upgrade.SystemOperations',return_value=Mock()))
        self.enterContext(patch('deployment.lib.provider_recovery_runtime.readonly_configuration',lambda p,**k:self.root/'state.json'))
        (self.root/'state.json').write_text('{}')
        for path in self.contract['historical_files']:(self.root/Path(path).name).write_bytes(b'synthetic enrollment data')
        self.publish()
    def test_truthful_bootstrap_never_reads_or_invents_a_previous_positive_grant(self):
        (self.root/'authority.json').unlink()
        self.assertEqual(producer.observe_origin(self.contract,self.runtime)['source_sha'],self.record['source_sha'])
    def test_fabricated_grant_beside_enrollment_refuses(self):
        (self.root/'write-authority').mkdir();(self.root/'write-authority/authority.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'bootstrap_grant_not_historical'):producer.observe_origin(self.contract,self.runtime)
    def test_actual_runtime_grant_or_mount_cannot_hide_behind_bootstrap(self):
        for kind in ('environment','mount'):
            actor=self.rows['backend'];saved=copy.deepcopy(actor)
            if kind=='environment':actor['Config']['Env'].append('MADAR_BUSINESS_WRITE_AUTHORITY=/run/madar/business-write-authority/authority.json')
            else:actor['Mounts']=[{'Destination':'/run/madar/business-write-authority'}]
            with self.assertRaises(RuntimeError):producer.observe_origin(self.contract,self.runtime)
            self.rows['backend']=saved
