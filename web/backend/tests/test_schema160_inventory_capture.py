"""Real exclusive publication; Docker/SQL/systemd observations are models.

No authority is issued and no operational profile is registered by these tests.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deployment.lib import schema150_provider_adapter as adapter
from deployment.lib import completed_normal_baseline as baseline
from deployment.lib.completed_normal_admission import digest, encoded
from test_schema150_actor_inventory import fixture, repin
from test_schema160_release import reconciled_contract


class OriginalInventoryCaptureTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name);self.package=self.base/('normal-source-'+'a'*64);self.package.mkdir()
        (self.inventory,_),self.rows=fixture()
        self.contract=reconciled_contract()
        db=self.inventory['containers']['native:db']
        self.contract['database'].update(container_id=db['id'],image=db['image'])
        self.roles={'roles':{k:{'rolcanlogin':True,'rolsuper':k=='postgres'} for k in self.inventory['roles']},'memberships':[]}
        self.inventory['roles']=adapter.role_measurements(self.roles)
        self.fragment=self.base/'unit.service';self.fragment.write_bytes(b'[Unit]\nDescription=Synthetic only\n')
        for unit in self.inventory['supervisors'].values():
            unit.update(fragment_sha256=hashlib.sha256(self.fragment.read_bytes()).hexdigest(),dropins_sha256=adapter.digest({}))
        scope={'operation':self.contract['operation'],'context_sha256':digest(self.contract),
            'source_sha':self.contract['candidate']['source_sha'],'controller_sha':self.contract['candidate']['controller_sha'],
            'inventory_sha256':'0'*64,'system_identifier':self.contract['database']['system_identifier'],
            'source_schema':146,'target_schema':160}
        self.inventory,scope=repin(self.inventory,scope)
        self.contract['writer_inventory_sha256']=scope['inventory_sha256']
        (self.package/'provider-inventory-input.json').write_bytes(encoded(self.inventory))
        self.runtime=Mock();self.runtime.command.side_effect=self.command
        self.guard=Mock()
        for change in (patch.object(baseline,'BASE',self.base),patch.object(adapter.os,'geteuid',return_value=0),
                patch.object(adapter,'protected',side_effect=lambda p,**kw:Path(p)),
                patch('deployment.lib.schema150_object_inventory.measure_roots',return_value={'identity':'actual model'})):
            change.start();self.addCleanup(change.stop)

    def command(self,args,**kwargs):
        if args[:3]==['docker','ps','-aq']:return '\n'.join(r['Id'] for r in self.rows)
        if args[:2]==['docker','inspect']:return json.dumps(self.rows)
        if args[:2]==['docker','exec']:
            self.assertIn('BEGIN READ ONLY;',kwargs['input']);self.assertIn('COMMIT;',kwargs['input'])
            self.assertNotIn('UPDATE ',kwargs['input']);self.assertNotIn('ALTER ',kwargs['input'])
            return json.dumps(self.roles if 'pg_authid' in kwargs['input'] else [self.contract['database']['system_identifier'],146])
        if args[:2]==['systemctl','show']:
            return f'FragmentPath={self.fragment}\nDropInPaths=\nUnitFileState=enabled\nJob=\nControlPID=0\n'
        self.fail('Unexpected command: '+repr(args))

    def capture(self):return adapter.capture_original_inventory(self.package,self.contract,self.runtime,source_guard=self.guard)

    def test_publishes_exact_pinned_inventory_without_issuing_authority_or_fencing(self):
        result=self.capture()
        self.assertEqual((self.package/'provider-inventory.json').read_bytes(),encoded(self.inventory))
        self.assertEqual(result['inventory_sha256'],self.contract['writer_inventory_sha256'])
        self.assertFalse(result['authority_issued']);self.assertFalse(result['writers_fenced'])
        self.assertEqual(self.guard.call_count,3)
        with self.assertRaisesRegex(RuntimeError,'already_published'):self.capture()

    def test_changed_origin_and_role_measurements_never_publish(self):
        original=self.runtime.command.side_effect
        for kind in ('origin','roles'):
            def changed(args,**kwargs):
                if args[:2]==['docker','exec']:
                    if kind=='origin' and 'pg_authid' not in kwargs['input']:return json.dumps(['foreign',146])
                    if kind=='roles' and 'pg_authid' in kwargs['input']:return json.dumps({'roles':{},'memberships':[]})
                return original(args,**kwargs)
            self.runtime.command.side_effect=changed
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):self.capture()
            self.assertFalse((self.package/'provider-inventory.json').exists())

    def test_unknown_actor_and_missing_snapshot_are_refused(self):
        original=self.runtime.command.side_effect
        def incomplete(args,**kwargs):
            if args[:2]==['docker','inspect']:return json.dumps(self.rows[:-1])
            return original(args,**kwargs)
        self.runtime.command.side_effect=incomplete
        with self.assertRaisesRegex(RuntimeError,'snapshot_incomplete'):self.capture()
        self.assertFalse((self.package/'provider-inventory.json').exists())

    def test_source_change_before_publication_leaves_no_inventory(self):
        self.guard.side_effect=[None,None,RuntimeError('source_changed')]
        with self.assertRaisesRegex(RuntimeError,'source_changed'):self.capture()
        self.assertFalse((self.package/'provider-inventory.json').exists())

    def test_pending_supervisor_refuses_without_publication(self):
        original=self.runtime.command.side_effect
        self.runtime.command.side_effect=lambda args,**kw:original(args,**kw).replace('Job=\n','Job=42\n') if args[:2]==['systemctl','show'] else original(args,**kw)
        with self.assertRaisesRegex(RuntimeError,'supervisor_changed_or_pending'):self.capture()
        self.assertFalse((self.package/'provider-inventory.json').exists())

    def test_non_root_cannot_measure_or_publish(self):
        with patch.object(adapter.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(RuntimeError,'root_package_required'):self.capture()
        self.runtime.command.assert_not_called()
