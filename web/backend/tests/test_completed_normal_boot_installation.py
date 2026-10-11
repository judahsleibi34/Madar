"""Exact-file installer tests in a private fixture, with no host systemd effects."""
import hashlib
import json
import os
from pathlib import Path
import sys
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
