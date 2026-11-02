"""Real file/spec hashes; modeled protected ownership and original enrollment.

No native provider or protected-upgrade acceptance is claimed by these tests.
"""
import copy,hashlib,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from deployment.lib import historical_origin as origin
from deployment.lib import isolated_release_environment as isolation
from deployment.lib import completed_normal_boot_actor as boot
from deployment.lib.completed_normal_resources import measured_spec
from deployment.lib.migration_inventory import digest
from test_historical_origin import HistoricalPreparationBindingTests


class HistoricalConfigurationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.enterContext(patch.object(isolation,'MOUNT_ROOTS',(self.root,)))
        lstat=Path.lstat
        def metadata(path,*args,**kwargs):
            value=lstat(path,*args,**kwargs);fields=list(value)
            if path.is_relative_to(self.root):fields[4]=1000
            if path==Path(tempfile.gettempdir()):fields[0]&=~0o022
            return os.stat_result(fields)
        self.enterContext(patch.object(Path,'lstat',metadata))
        self.enterContext(patch.object(origin.os,'geteuid',return_value=0))
        self.rows=[];self.scope={}
        self.original_config=self.root/'original-provider.conf';self.original_config.write_bytes(b'actual original configuration\n');self.original_config.chmod(0o600)
        for number,name in enumerate(origin.PROVIDERS,1):
            mounts=([{'Type':'bind','Source':str(self.original_config),'Destination':'/etc/original.conf',
                'RW':False,'Propagation':'rprivate'}] if name in ('supabase-db','supabase-envoy') else [])
            row={'Id':f'{number:064x}','Name':'/'+name,'Image':'sha256:'+'a'*64,
                'Config':{'Env':['ORIGINAL_PROVIDER_SETTING=actual']},'HostConfig':{},'Mounts':mounts}
            self.rows.append(row)
            self.scope[row['Id']]={'name':row['Name'],'image':row['Image'],'spec_sha256':measured_spec(row),
                'binds':{m['Destination']:isolation.measure_bind_source(m['Source']) for m in mounts}}
        self.inputs=origin.provider_configurations(self.rows,self.scope)
        self.original={'runtime':{r['Name']:{'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)} for r in self.rows},
            'provider_configurations':copy.deepcopy(self.inputs)}
        self.enterContext(patch.object(origin,'recorded_observation',return_value=self.original))
        self.runtime=SimpleNamespace(inspect=lambda names:{r['Name'].removeprefix('/'):r for r in self.rows})
        self.enterContext(patch('deployment.lib.emergency_routing_repair.Runtime',return_value=self.runtime))
        self.contract=HistoricalPreparationBindingTests().contract()

    def test_real_original_provider_inputs_are_observed_without_requiring_future_envoy_files(self):
        self.assertEqual(origin.verify_provider_configurations(self.contract['source_roles']),digest(self.inputs))
        for row in self.inputs.values():
            for value in row['read_only_inputs'].values():
                self.assertEqual(value['source'],str(self.original_config))
        self.assertFalse((self.root/'native.env').exists())

    def test_missing_old_enrollment_input_does_not_gain_an_implicit_new_capability(self):
        self.original.pop('provider_configurations')
        with self.assertRaisesRegex(RuntimeError,'enrollment_required'):
            origin.verify_provider_configurations(self.contract['source_roles'])

    def test_modified_bytes_replaced_inode_and_changed_provider_spec_refuse(self):
        before=self.original_config.read_bytes();self.original_config.write_bytes(b'modified original settings')
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
            origin.verify_provider_configurations(self.contract['source_roles'])
        self.original_config.write_bytes(before)
        old=self.original_config.with_name('old.conf');self.original_config.rename(old)
        self.original_config.write_bytes(before);self.original_config.chmod(0o600)
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
            origin.verify_provider_configurations(self.contract['source_roles'])
        self.original_config.unlink();old.rename(self.original_config)
        self.rows[1]['Config']['Env']=['REPLACED_PROVIDER_SETTING=unreviewed']
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
            origin.verify_provider_configurations(self.contract['source_roles'])

    def test_read_only_input_becoming_writable_or_foreign_actor_cannot_reuse_original_binding(self):
        self.rows[0]['Mounts'][0]['RW']=True
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
            origin.verify_provider_configurations(self.contract['source_roles'])
        self.rows[0]['Mounts'][0]['RW']=False;self.rows[0]['Id']='f'*64
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
            origin.verify_provider_configurations(self.contract['source_roles'])

    def configuration_plan(self):
        paths={}
        for key in boot.HISTORICAL_CONFIGURATIONS:
            path=self.root/(key+'.env');path.write_text('original '+key);path.chmod(0o600);paths[key]=(path,True)
        self.enterContext(patch.object(boot,'HISTORICAL_CONFIGURATIONS',paths))
        self.enterContext(patch.object(boot,'readonly_configuration',lambda p,**kw:Path(p)))
        hashes={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,(path,_) in paths.items()}
        self.original['configuration_sha256']={name:hashes[key] for key,name in
            (('production_configuration','application'),('backup_configuration','backup'),('database_transport','database_transport'))}
        return {'admission_contract':self.contract,'live_configuration_sha256':dict(hashes,original_provider_configurations=digest(self.inputs))}

    def test_existing_package_configuration_guard_authenticates_actual_historical_inputs(self):
        document=self.configuration_plan();boot.verify_live_configuration(document)
        self.assertEqual(boot.configuration_names(document),set(document['live_configuration_sha256']))
        for key in document['live_configuration_sha256']:
            changed=copy.deepcopy(document);changed['live_configuration_sha256'][key]='f'*64
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'configuration_changed'):
                boot.verify_live_configuration(changed)

    def test_historical_marker_alone_cannot_select_a_different_profile_or_legacy_config_layout(self):
        document=self.configuration_plan();document['admission_contract']['operation']='unsupported-operation'
        with self.assertRaises(RuntimeError):boot.verify_live_configuration(document)
        document=self.configuration_plan();document['live_configuration_sha256']={k:'a'*64 for k in boot.CONFIGURATIONS}
        with self.assertRaisesRegex(RuntimeError,'configuration_contract_invalid'):boot.verify_live_configuration(document)
