"""Real provider intent journal and exact files; systemd remains a model."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.lib import completed_normal_boot_installation as boot
from deployment.lib import schema149_provider_lifecycle as retained
from deployment.lib import schema150_provider_lifecycle as lifecycle
from deployment.lib import schema150_actor_inventory as inventory
from deployment.lib.completed_normal_profile import RECONCILED
from test_schema150_actor_inventory import fixture, repin


class ProviderBootBarrierTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.units=self.root/'units';self.units.mkdir()
        (data,binding),_=fixture()
        binding.update(operation=RECONCILED.operation,target_schema=160)
        data['binding_sha256']=inventory.binding_scope_digest(binding)
        data,binding=repin(data,binding)
        contract={'operation':binding['operation'],'candidate':{'source_sha':binding['source_sha'],
            'controller_sha':binding['controller_sha']},'writer_inventory_sha256':binding['inventory_sha256'],
            'database':{'system_identifier':binding['system_identifier']}}
        binding['context_sha256']=boot.digest(contract)
        self.binding,self.data=binding,data
        self.installer=boot.CompletedNormalBootInstallation.__new__(boot.CompletedNormalBootInstallation)
        self.installer.contract,self.installer.profile,self.installer.root,self.installer.units=contract,RECONCILED,self.root,self.units
        for mod,attribute,replacement in ((retained,'protected',lambda p,**_:Path(p)),
                (retained,'require_root_directory',lambda _:None),(boot,'protected',lambda p,**_:Path(p))):
            guard=patch.object(mod,attribute,replacement);guard.start();self.addCleanup(guard.stop)
        path=self.root/'provider-journal';path.mkdir(mode=0o700)
        self.journal=lifecycle.ProtectedProviderJournal(path)
        self.preimage={k:{'fixture':'pre-effect'} for k in ('ingress','supervisors','objects','roles')}
        self.journal.append('prepared',{'binding':binding,'preimage':self.preimage})
        (self.root/'provider-inventory.json').write_text(json.dumps(data))
        self.barrier=self.root/'provider-barrier.json'
        self.name='99zzzzzz-schema160-'+binding['context_sha256'][:12]+'.conf'

    def arm(self, *, complete=False):
        self.journal.append('effect_intent',{'step':'arm_boot_interlock'})
        self.barrier.write_text(json.dumps({'binding':self.binding,'preimage_sha256':lifecycle.digest(self.preimage)}))
        for unit in self.data['supervisors']:
            directory=self.units/(unit+'.d');directory.mkdir()
            (directory/self.name).write_bytes(('[Unit]\nConditionPathExists=!'+str(self.barrier)+'\n').encode())
        if complete:self.journal.append('effect_complete',{'step':'arm_boot_interlock'})

    def test_before_intent_and_before_effect_expects_no_overlay(self):
        self.assertEqual(self.installer.provider_barrier_dropins(),{})
        self.journal.append('effect_intent',{'step':'arm_boot_interlock'})
        self.assertEqual(self.installer.provider_barrier_dropins(),{})

    def test_pending_post_effect_and_completed_effect_verify_the_same_exact_overlay(self):
        self.arm();before=(self.root/'provider-journal/0000.json').read_bytes()
        expected={unit:{str(boot.UNITS/(unit+'.d')/self.name)} for unit in self.data['supervisors']}
        self.assertEqual(self.installer.provider_barrier_dropins(),expected)
        self.journal.append('effect_complete',{'step':'arm_boot_interlock'})
        self.assertEqual(self.installer.provider_barrier_dropins(),expected)
        self.assertEqual((self.root/'provider-journal/0000.json').read_bytes(),before)

    def test_interrupted_partial_installation_cannot_be_accepted(self):
        self.arm();next(self.units.glob('*.d/'+self.name)).unlink()
        with self.assertRaises(FileNotFoundError):self.installer.provider_barrier_dropins()

    def test_barrier_without_intent_refuses(self):
        self.barrier.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'without_intent'):self.installer.provider_barrier_dropins()

    def test_wrong_scope_and_changed_preimage_refuse(self):
        self.arm();original=json.loads(self.barrier.read_text())
        for change in ({'preimage_sha256':'f'*64},{'binding':dict(self.binding,controller_sha='f'*40)}):
            self.barrier.write_text(json.dumps(dict(original,**change)))
            with self.assertRaisesRegex(RuntimeError,'barrier_changed'):self.installer.provider_barrier_dropins()

    def test_inventory_substitution_and_changed_dropin_refuse(self):
        self.arm();path=self.root/'provider-inventory.json';original=path.read_bytes()
        changed=copy.deepcopy(self.data);changed['supervisors'].pop(next(iter(changed['supervisors'])))
        path.write_text(json.dumps(changed))
        with self.assertRaises(RuntimeError):self.installer.provider_barrier_dropins()
        path.write_bytes(original);next(self.units.glob('*.d/'+self.name)).write_text('[Unit]\nConditionPathExists=/wrong\n')
        with self.assertRaisesRegex(RuntimeError,'dropin_changed'):self.installer.provider_barrier_dropins()

    def test_lost_barrier_before_authorized_clear_refuses(self):
        self.arm(complete=True);self.barrier.unlink()
        with self.assertRaisesRegex(RuntimeError,'barrier_missing'):self.installer.provider_barrier_dropins()

    def test_journal_wrong_binding_or_broken_chain_refuses(self):
        self.arm();path=self.root/'provider-journal/0000.json';original=path.read_bytes()
        changed=json.loads(original);changed['payload']['binding']['controller_sha']='f'*40
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(RuntimeError,'journal_chain'):self.installer.provider_barrier_dropins()
        path.write_bytes(original);self.journal.append('effect_complete',{'step':'fence_ingress'})
        with self.assertRaisesRegex(RuntimeError,'journal_sequence'):self.installer.provider_barrier_dropins()

    def test_clear_intent_or_completion_retains_verified_dropins_without_barrier(self):
        self.arm(complete=True)
        for step in lifecycle.STEPS[1:]:
            if step=='resume_accepted_workers':
                self.journal.append('private_ready',{'binding_sha256':lifecycle.digest(self.binding)})
            self.journal.append('effect_intent',{'step':step})
            if step=='clear_boot_interlock':
                self.barrier.unlink();self.assertTrue(self.installer.provider_barrier_dropins())
            self.journal.append('effect_complete',{'step':step})
        self.assertTrue(self.installer.provider_barrier_dropins())
        # A reconstructed barrier after clear is not a fresh recovery grant.
        self.barrier.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'barrier_changed'):self.installer.provider_barrier_dropins()

    def test_installed_boot_accepts_only_the_observed_overlay_inventory_and_loaded_paths(self):
        from test_completed_normal_boot_installation import CompletedBootInstallationTests
        case=CompletedBootInstallationTests();case.setUp();self.addCleanup(case.doCleanups)
        installer=case.installer;installer.install()
        signed=(installer.root/'boot-installation.json').read_bytes()
        overlays={name:{str(boot.UNITS/(name+'.d')/self.name)}
            for name in [boot.PROXY,*installer.baseline['old_units']]}
        for unit in overlays:
            directory=case.units/(unit+'.d');directory.mkdir(exist_ok=True)
            (directory/self.name).write_text('[Unit]\nConditionPathExists=!/fixture/barrier\n')
        previous=case.ops.command
        def loaded(label,args,**kwargs):
            result=previous(label,args,**kwargs)
            if args[:2]==['systemctl','show'] and args[2] in overlays:
                lines=result.stdout.splitlines()
                result.stdout='\n'.join(line+' '+next(iter(overlays[args[2]]))
                    if line.startswith('DropInPaths=') else line for line in lines)+'\n'
            return result
        with patch.object(installer,'provider_barrier_dropins',return_value=overlays):
            with patch.object(case.ops,'command',side_effect=loaded):
                installer.installed()
                (case.units/(boot.PROXY+'.d')/'unknown.conf').write_text('[Unit]\n')
                with self.assertRaisesRegex(RuntimeError,'proxy_inventory_changed'):installer.installed()
                (case.units/(boot.PROXY+'.d')/'unknown.conf').unlink()
            with self.assertRaisesRegex(RuntimeError,'effective_actor_controls_changed'):installer.installed()
        self.assertEqual((installer.root/'boot-installation.json').read_bytes(),signed)


if __name__=='__main__':unittest.main()
