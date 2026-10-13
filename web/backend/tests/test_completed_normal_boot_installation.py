"""Exact-file installer tests in a private fixture, with no host systemd effects."""
import hashlib
import copy
import json
import os
import shutil
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_boot_installation as m
from deployment.lib import completed_normal_admission as admission
from test_completed_normal_admission import fixture_contract

class Operations:
    def __init__(self,states):self.states={k:dict(v) for k,v in states.items()};self.calls=[];self.installation=None;self.fail=None
    def systemctl_state(self,name):return dict(self.states.get(name,{'enabled':'disabled','active':'inactive'}))
    def command(self,label,args,**kw):
        self.calls.append((label,list(args)))
        if self.fail==label:self.fail=None;raise RuntimeError('injected_'+label)
        if args[:2]==['systemctl','disable']:
            self.states.setdefault(args[2],{'active':'inactive'})['enabled']='disabled'
        elif args[:2]==['systemctl','enable']:
            self.states.setdefault(args[2],{'active':'inactive'})['enabled']='enabled'
        if args[:2]==['systemctl','show']:
            installer=self.installation
            if args[2]!=m.PROXY:
                name=args[2]
                dropins=[] if name==installer.name else [*installer.baseline['old_unit_dropins'][name],
                    str(m.UNITS/(name+'.d')/('99-superseded-'+admission.digest(installer.contract)[:12]+'.conf'))]
                return SimpleNamespace(stdout='FragmentPath='+str(m.UNITS/name)+'\nDropInPaths='+' '.join(dropins)+'\n')
            return SimpleNamespace(stdout='Requires=docker.service '+installer.name+'\nExecStartPre='+installer.command('proxy-gate')+
                '\nDropInPaths='+' '.join([*installer.baseline['proxy_dropins'],str(installer.proxy)])+'\n')
        if args[:2] not in (['systemctl','disable'],['systemctl','enable'],['systemctl','daemon-reload'],['systemd-analyze','verify']):
            raise AssertionError('unexpected effect in the boot installer')
        return SimpleNamespace(stdout='')

class CompletedBootInstallationTests(unittest.TestCase):
    def test_application_successor_preserves_verified_older_compatible_boot_actor(self):
        from test_completed_normal_application_release import application_contract
        contract=application_contract();document=copy.deepcopy(self.installer.document)
        current='madar-compatible-normal-boot-'+Path(contract['source_roles']['completion_root']).name[:12]+'.service'
        historical='madar-compatible-normal-boot-c3c5ec68f56f.service'
        receipt=self.path/'origin-boot-preimages.json';receipt.write_text(json.dumps({'old_units':[historical]}))
        original_path=Path(contract['source_roles']['completion_root'])/'boot-preimages.json'
        contract['historical_files'][str(original_path)]=hashlib.sha256(receipt.read_bytes()).hexdigest()
        baseline=document['boot_resources']
        for name in (current,historical):
            p=self.units/name;p.write_text('[Unit]\nDescription=verified compatible origin\n');p.chmod(0o644)
            baseline['old_units'].append(name);baseline['old_unit_dropins'][name]=[]
            baseline['unit_states'][name]={'enabled':'disabled','active':'inactive'}
            baseline['files'][str(m.UNITS/name)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'uid':0,'mode':0o644}
        old_gate=str(m.DROPINS/'99z-compatible-normal-795df6dc0143.conf')
        p=self.proxy/Path(old_gate).name;p.write_text('[Unit]\nRequires='+current+'\n');p.chmod(0o644)
        baseline['proxy_dropins'].append(old_gate);baseline['files'][old_gate]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'uid':0,'mode':0o644}
        contract['plan_sha256']=admission.digest(document)
        with patch.object(m,'protected',side_effect=lambda path,**kw:receipt if path==original_path else path):
            installer=m.CompletedNormalBootInstallation(contract,document,self.installer.package,lambda:None,self.ops,
                units=self.units,admissions=self.path/'admissions')
            self.assertTrue(installer.proxy.name.startswith('99zz-compatible-normal-'))
            self.ops.installation=installer;installer.root.mkdir()
            self.ops.states.update(baseline['unit_states'])
            originals={p:p.read_bytes() for p in self.units.rglob('*') if p.is_file()}
            installer.install();installer.restore_application_preimages()
            self.assertTrue(all(p.read_bytes()==body for p,body in originals.items()))
            self.assertFalse(installer.proxy.exists())
            self.assertTrue((installer.root/'application-boot-restored.json').exists())

    def test_manual_successor_gate_sorts_after_existing_completed_origin(self):
        from test_completed_normal_manual_profile import manual_contract
        contract=manual_contract();document=copy.deepcopy(self.installer.document)
        origin='99-compatible-normal-'+Path(contract['source_roles']['completion_root']).name[:12]+'.conf'
        canonical=str(m.DROPINS/origin)
        document['boot_resources']['proxy_dropins'].append(canonical)
        document['boot_resources']['files'][canonical]={'sha256':'b'*64,'uid':0,'mode':0o644}
        contract['plan_sha256']=admission.digest(document)
        installer=m.CompletedNormalBootInstallation(contract,document,self.installer.package,lambda:None,self.ops,
            units=self.units,admissions=self.path/'admissions')
        self.assertTrue(all(Path(p).name<installer.proxy.name for p in installer.baseline['proxy_dropins']))
        self.assertTrue(installer.proxy.name.startswith('99z-compatible-normal-'))
        self.assertTrue(self.installer.proxy.name.startswith('99-compatible-normal-'))
        late=str(m.DROPINS/'zz-unreviewed.conf')
        document['boot_resources']['proxy_dropins'].append(late)
        document['boot_resources']['files'][late]={'sha256':'c'*64,'uid':0,'mode':0o644}
        contract['plan_sha256']=admission.digest(document)
        with self.assertRaisesRegex(RuntimeError,'completed_boot_proxy_gate_order_unreviewed'):
            m.CompletedNormalBootInstallation(contract,document,self.installer.package,lambda:None,self.ops,
                units=self.units,admissions=self.path/'admissions')
        self.assertEqual(self.ops.calls,[])

    @unittest.skipUnless(shutil.which('systemd-analyze'),'offline systemd parser unavailable')
    def test_real_systemd_parser_reproduces_old_reset_and_accepts_ordered_successor(self):
        # Offline parser only: no manager reload, unit start, Docker or DB access.
        units=self.path/'offline-parser';units.mkdir()
        fragment=units/'order-test.service'
        fragment.write_text('[Unit]\nDefaultDependencies=no\n[Service]\nType=oneshot\n'
            'StandardOutput=null\nStandardError=null\nExecStart=/usr/bin/true\n')
        dropins=units/(fragment.name+'.d');dropins.mkdir()
        old=dropins/'99-compatible-normal-c3c5ec68f56f.conf'
        old.write_text('[Service]\nExecStartPre=\nExecStartPre=/usr/bin/true old-gate\n')
        candidate=dropins/'99-compatible-normal-402aea67e904.conf'
        candidate.write_text('[Service]\nExecStartPre=\nExecStartPre=/usr/bin/true successor-gate\n')
        original=old.read_bytes()
        def effective_gate():
            result=subprocess.run(['systemd-analyze','verify','--man=no','--generators=no',str(fragment)],
                env={**os.environ,'SYSTEMD_UNIT_PATH':str(units),'SYSTEMD_LOG_LEVEL':'debug','SYSTEMD_COLORS':'0'},
                capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr[-1500:])
            return [line.strip() for line in (result.stdout+result.stderr).splitlines()
                if 'Command Line: /usr/bin/true ' in line]
        self.assertEqual(effective_gate(),['Command Line: /usr/bin/true old-gate'])
        candidate.rename(dropins/'99z-compatible-normal-402aea67e904.conf')
        self.assertEqual(effective_gate(),['Command Line: /usr/bin/true successor-gate'])
        self.assertEqual(old.read_bytes(),original)

    def test_manual_supersession_accepts_only_the_verified_compatible_origin_actor(self):
        from test_completed_normal_manual_profile import manual_contract
        contract=manual_contract();document=copy.deepcopy(self.installer.document)
        name='madar-compatible-normal-boot-'+Path(contract['source_roles']['completion_root']).name[:12]+'.service'
        path=self.units/name;path.write_text('[Unit]\nDescription=exact completed origin\n');path.chmod(0o644)
        baseline=document['boot_resources'];baseline['old_units'].append(name)
        baseline['old_unit_dropins'][name]=[]
        baseline['unit_states'][name]={'enabled':'disabled','active':'inactive'}
        baseline['files'][str(m.UNITS/name)]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'uid':0,'mode':0o644}
        contract['plan_sha256']=admission.digest(document)
        installer=m.CompletedNormalBootInstallation(contract,document,self.installer.package,lambda:None,self.ops,
            units=self.units,admissions=self.path/'admissions')
        installer.preflight(read_only=True)
        self.assertEqual(self.ops.calls,[])
        document['boot_resources']['old_units'][-1]='madar-compatible-normal-boot-'+('f'*12)+'.service'
        contract['plan_sha256']=admission.digest(document)
        with self.assertRaisesRegex(RuntimeError,'resource_contract_invalid'):
            m.CompletedNormalBootInstallation(contract,document,self.installer.package,lambda:None,self.ops,
                units=self.units,admissions=self.path/'admissions')
    def test_boot_queues_disabled_proxy_only_after_successful_verified_recovery(self):
        body=m.unit_bytes('/measured/boot').decode()
        self.assertIn('Wants=madar-release-proxy.service\n',body)
        self.assertIn('Before=madar-release-proxy.service\n',body)
        gate=m.proxy_bytes('madar-compatible-normal-boot-test.service','/measured/gate').decode()
        self.assertIn('Requires=docker.service madar-compatible-normal-boot-test.service\n',gate)
        self.assertIn('After=docker.service madar-compatible-normal-boot-test.service\n',gate)
        # Installation queues nothing immediately and preserves the original
        # disabled proxy activation. Its guarded boot dependency owns recovery.
        self.assertNotIn('ExecStartPost=',body)

    def test_proxy_gate_runs_as_root_without_changing_proxy_service_identity(self):
        body=m.proxy_bytes('madar-compatible-normal-boot-test.service','/usr/bin/python3 /root-private/gate.py').decode()
        self.assertIn('ExecStartPre=+/usr/bin/python3 /root-private/gate.py\n',body)
        self.assertNotIn('User=',body)
        self.assertNotIn('Group=',body)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.units=self.path/'units';self.units.mkdir(mode=0o755);self.proxy=self.units/(m.PROXY+'.d');self.proxy.mkdir(mode=0o755)
        old=['madar-emergency-routing.service','madar-normal-local-boot-61838c083590.service',
             'madar-normal-local-fallback-82c2321cc671.service']
        files={}
        for name in [m.PROXY,*old]:
            target=self.units/name;target.write_text('[Unit]\nDescription=retained fixture '+name+'\n')
            files[str(m.UNITS/name)]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'uid':0,'mode':0o644}
            target.chmod(0o644)
        proxy_dropins=[]
        for name in ('90-emergency-routing.conf','91-emergency-routing-retry.conf','92-normal-local-continuation.conf'):
            target=self.proxy/name;target.write_text('[Unit]\nRequires='+old[1]+'\n');target.chmod(0o600)
            canonical=str(m.DROPINS/name);proxy_dropins.append(canonical)
            files[canonical]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'uid':0,'mode':0o600}
        states={name:{'enabled':'enabled','active':'active'} for name in [m.PROXY,*old]}
        states[m.PROXY]['active']='failed' # Real current manager/runtime split.
        document={'operation':admission.OPERATION,'source_bundle_sha256':'a'*64,
            'boot_resources':{'files':files,'proxy_dropins':proxy_dropins,'old_units':old,
                'old_unit_dropins':{n:[] for n in old},'unit_states':states}}
        self.contract=fixture_contract();self.contract['plan_sha256']=admission.digest(document)
        self.ops=Operations(states);self.root=self.path/'admissions'/admission.digest(self.contract);self.root.mkdir(parents=True)
        self.installer=m.CompletedNormalBootInstallation(self.contract,document,
            Path('/var/lib/madar-control-plane/normal-local-preparation')/('normal-source-'+'a'*64),
            lambda:None,self.ops,units=self.units,admissions=self.path/'admissions')
        self.ops.installation=self.installer
        stat=Path.stat
        def fixture_stat(path,*args,**kw):
            value=stat(path,*args,**kw)
            if path.is_relative_to(self.path):
                fields=list(value);fields[4]=0;return os.stat_result(fields)
            return value
        for p in (patch.object(m,'protected',lambda path,**kw:path),patch.object(m.os,'geteuid',return_value=0),
            patch.object(m,'require_fresh_authorization',lambda c:None),patch.object(Path,'stat',fixture_stat)):
            p.start();self.addCleanup(p.stop)
        self.original={path:path.read_bytes() for path in self.units.rglob('*') if path.is_file()}
    def test_installer_archives_exact_dropins_preserves_units_and_closes_old_activation_edges(self):
        self.installer.preflight();self.assertEqual(self.ops.calls,[])
        result=self.installer.install()
        self.assertFalse(result['historical_units_deleted'])
        for path,body in self.original.items():
            if path.parent==self.proxy:
                self.assertEqual((self.root/'proxy-originals'/path.name).read_bytes(),body)
                self.assertNotIn(self.installer.baseline['old_units'][1],path.read_text())
            else:self.assertEqual(path.read_bytes(),body)
        for name in self.installer.baseline['old_units']:
            self.assertEqual(self.ops.systemctl_state(name)['enabled'],'disabled')
            body=(self.units/(name+'.d')/('99-superseded-'+admission.digest(self.contract)[:12]+'.conf')).read_text()
            self.assertNotIn('PartOf=\n',body);self.assertIn('RefuseManualStart=yes',body)
            self.assertIn('ConditionPathExists=!'+str(self.root/'boot-installation.json'),body)
        self.assertIn('Requires=docker.service '+self.installer.name,self.installer.proxy.read_text())
        self.assertNotIn('Requires=\n',self.installer.proxy.read_text())
        self.assertFalse(any(args[:2] in (['systemctl','start'],['systemctl','restart'],['docker','start']) for _,args in self.ops.calls))
        with self.assertRaisesRegex(RuntimeError,'already_consumed'):self.installer.preflight()
    def test_changed_file_dropin_or_unit_state_rejects_before_mutation(self):
        path=self.units/m.PROXY;old=path.read_bytes();path.write_bytes(old+b'changed\n')
        with self.assertRaisesRegex(RuntimeError,'preimage_changed'):self.installer.preflight()
        path.write_bytes(old)
        extra=self.proxy/'100-unreviewed.conf';extra.write_text('[Unit]\n')
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.installer.preflight()
        extra.unlink();self.ops.states[m.PROXY]['active']='active'
        with self.assertRaisesRegex(RuntimeError,'unit_state_changed'):self.installer.preflight()
        self.assertEqual(self.ops.calls,[])

    def test_read_only_preflight_cannot_authorize_installation(self):
        with patch.object(m,'require_fresh_authorization',side_effect=RuntimeError('fresh_authorization_required')) as check:
            self.assertFalse(self.installer.preflight(read_only=True)['production_modified'])
            check.assert_not_called()
            with self.assertRaisesRegex(RuntimeError,'fresh_authorization_required'):self.installer.install()
        self.assertEqual(self.ops.calls,[])
        self.assertEqual({path:path.read_bytes() for path in self.original},self.original)
    def test_unknown_legacy_boot_actor_prevents_partial_supersession(self):
        (self.units/'madar-normal-local-boot-ffffffffffff.service').write_text('[Unit]\n')
        with self.assertRaisesRegex(RuntimeError,'legacy_unit_inventory_changed'):self.installer.preflight()
        self.assertEqual(self.ops.calls,[])
    def test_failure_after_receipt_restores_only_owned_additions_and_activation(self):
        self.ops.fail='completed_boot_enable_new'
        with self.assertRaisesRegex(RuntimeError,'injected'):self.installer.install()
        for path,body in self.original.items():self.assertEqual(path.read_bytes(),body)
        self.assertTrue((self.root/'boot-installation-failed.json').is_file())
        self.assertEqual(len(list(self.root.glob('retained-*'))),len(self.installer.paths()))
        self.assertFalse(any(p.exists() for p in self.installer.paths()))
        for name in self.installer.baseline['old_units']:self.assertEqual(self.ops.systemctl_state(name)['enabled'],'enabled')
        with self.assertRaisesRegex(RuntimeError,'already_consumed'):self.installer.install()
    def test_altered_new_resource_is_rejected_and_never_silently_replaced(self):
        self.installer.install();self.installer.proxy.write_bytes(b'altered')
        with self.assertRaisesRegex(RuntimeError,'resource_changed'):self.installer.installed()
    def test_original_fragment_change_after_installation_is_not_hidden_by_overlay(self):
        self.installer.install();(self.units/m.PROXY).write_bytes(b'altered-original')
        with self.assertRaisesRegex(RuntimeError,'preserved_resource_changed'):self.installer.installed()
    def test_dependency_supersession_retains_every_unrelated_setting(self):
        original=b'[Unit]\nRequires=docker.service madar-normal-local-boot-61838c083590.service\nAfter=network-online.target madar-normal-local-boot-61838c083590.service\n[Service]\nNoNewPrivileges=yes\nExecStartPre=/original/guard\n'
        result=m.superseded_dependencies(original,self.installer.baseline['old_units'])
        self.assertEqual(result,b'[Unit]\nRequires=docker.service\nAfter=network-online.target\n[Service]\nNoNewPrivileges=yes\nExecStartPre=/original/guard\n')
        with self.assertRaisesRegex(RuntimeError,'syntax_unreviewed'):
            m.superseded_dependencies(b'[Unit]\nRequires=$DYNAMIC_UNIT\n',self.installer.baseline['old_units'])
    def test_actual_dropin_inventory_change_after_installation_rejects(self):
        self.installer.install();(self.proxy/'100-unapproved.conf').write_text('[Unit]\n')
        with self.assertRaisesRegex(RuntimeError,'proxy_inventory_changed'):self.installer.installed()

if __name__=='__main__':unittest.main()
