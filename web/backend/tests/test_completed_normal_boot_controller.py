"""Actual boot source guard with modeled filesystem ownership/configuration."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from deployment.lib import completed_normal_boot_actor as boot
from deployment.lib.completed_normal_admission import digest


class BootControllerIdentityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.source=self.root/'source';self.source.mkdir()
        self.current='a'*40;self.tree='b'*64
        actor=self.actor=boot.CompletedNormalBootActor.__new__(boot.CompletedNormalBootActor)
        actor.root=self.root;actor.profile=SimpleNamespace(operation='modeled-boot-source')
        actor.contract={'candidate':{'controller_sha':self.current,'source_sha':'c'*40,'controller_tree_sha256':self.tree},
            'source_roles':{'controller_sha':self.current}}
        actor.document={'source_bundle_sha256':'d'*64,'installed_controller_tree_sha256':self.tree}
        actor.measure=lambda:(actor.document,self.source)
        actor.ops=SimpleNamespace(repository_head=lambda:self.current)
        self.stamp=self.root/'controller';self.stamp.write_text(self.current)
        self.enterContext(patch.object(boot,'INPUTS',{'controller':self.stamp}))
        self.enterContext(patch.object(boot,'controller_tree_digest',side_effect=lambda:self.tree))
        self.enterContext(patch.object(boot,'protected',lambda p,**kw:p))
        self.enterContext(patch.object(boot,'verify_live_configuration'))
        self.enterContext(patch.object(boot.os,'geteuid',return_value=0))
        self.enterContext(patch.object(boot,'sys',SimpleNamespace(modules={})))
        self.authorization()

    def authorization(self):
        a=self.actor
        (self.root/'operator-authorization.json').write_text(json.dumps({'operation':a.profile.operation,
            'context_sha256':digest(a.contract),'plan_sha256':digest(a.document),
            'source_bundle_sha256':a.document['source_bundle_sha256'],
            'controller_sha':a.contract['candidate']['controller_sha'],'application_sha':a.contract['candidate']['source_sha']}))

    def intent(self):
        a=self.actor
        return {'operation':a.profile.operation,'context_sha256':digest(a.contract),
            'from_controller':a.contract['source_roles']['controller_sha'],
            'to_controller':a.contract['candidate']['controller_sha'],
            'old_tree_sha256':a.document['installed_controller_tree_sha256'],
            'new_tree_sha256':a.contract['candidate']['controller_tree_sha256']}

    def test_same_original_and_target_controller_needs_no_future_installation_intent(self):
        self.actor.source()
        self.assertFalse((self.root/'controller-installation-intent.json').exists())

    def test_same_source_still_requires_both_tree_identities_and_checkout(self):
        self.actor.document['installed_controller_tree_sha256']='e'*64;self.authorization()
        with self.assertRaisesRegex(RuntimeError,'installed_tree_changed'):self.actor.source()
        self.actor.document['installed_controller_tree_sha256']=self.tree;self.authorization()
        self.actor.ops.repository_head=lambda:'f'*40
        with self.assertRaisesRegex(RuntimeError,'checkout_role_changed'):self.actor.source()

    def test_a_changed_controller_or_advanced_stage_requires_real_installation_intent(self):
        self.actor.contract['source_roles']['controller_sha']='e'*40;self.authorization()
        with self.assertRaisesRegex(RuntimeError,'controller_installation_changed'):self.actor.source()
        (self.root/'controller-installation-intent.json').write_text(json.dumps(self.intent()));self.actor.source()
        (self.root/'controller-installation-intent.json').unlink()
        self.actor.contract['source_roles']['controller_sha']=self.current;self.authorization()
        for name in ('candidate-runtime.json','migration-intent.json'):
            p=self.root/name;p.write_text('{}')
            with self.subTest(stage=name),self.assertRaisesRegex(RuntimeError,'controller_installation_changed'):self.actor.source()
            p.unlink()

    def test_existing_intent_is_never_ignored_on_an_identical_controller(self):
        p=self.root/'controller-installation-intent.json';p.write_text(json.dumps(self.intent()));self.actor.source()
        bad=self.intent();bad['old_tree_sha256']='f'*64;p.write_text(json.dumps(bad))
        with self.assertRaisesRegex(RuntimeError,'controller_installation_changed'):self.actor.source()

    def test_unrecognized_controller_and_missing_authorization_refuse(self):
        self.current='f'*40;self.stamp.write_text(self.current)
        with self.assertRaisesRegex(RuntimeError,'controller_identity_changed'):self.actor.source()
        (self.root/'operator-authorization.json').unlink()
        with self.assertRaises(FileNotFoundError):self.actor.source()


if __name__=='__main__':unittest.main()
