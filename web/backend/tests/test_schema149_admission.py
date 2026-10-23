"""Exact successor admission, historical isolation and fail-closed activation."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema149_release as release
from deployment.lib import schema149_consumers as consumers
from deployment.lib import schema149_controller as controller
from deployment.lib import completed_normal_admission as admission
from deployment.lib.completed_normal_profile import OUTBOX, FENCED, COMMERCIAL, profile, expected_origin_grant
from deployment.lib.completed_normal_write_handoff import CompletedNormalWriteHandoff
from deployment.lib.migration_executor import MigrationManifest, LockedMigrationExecutor
from test_schema148_admission import fenced_contract


def successor_contract():
    value = fenced_contract()
    value.update(version=6, operation=OUTBOX.operation, migration_manifest_sha256=release.MANIFEST_SHA256,
                 provider_maintenance_sha256='e'*64, writer_inventory_sha256='f'*64)
    value['candidate']['compatible_max'] = 149
    return value


class SuccessorAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        web = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
        shutil.copytree(web/'deployment/releases', self.root/'web/deployment/releases')
        for row in json.loads((self.root/'web/deployment/releases'/release.MANIFEST).read_text())['migrations']:
            for tree in ('database','supabase'):
                source = web/tree/'historical-architecture-146-150'/Path(row['path']).name
                if not source.exists(): source = Path('/'+tree+'/historical-architecture-146-150')/source.name
                target = self.root/'web'/tree/'historical-architecture-146-150'/source.name
                target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(source.read_bytes())

    def test_profile_and_all_historical_bounds_are_exact(self):
        value = successor_contract(); admission.validate_contract(value)
        self.assertIs(profile(value), OUTBOX)
        self.assertEqual((OUTBOX.version,OUTBOX.source,OUTBOX.target,OUTBOX.migrations),(6,146,149,(147,148,149)))
        self.assertEqual((FENCED.version,FENCED.source,FENCED.target,FENCED.migrations),(5,146,148,(147,148)))
        self.assertEqual((COMMERCIAL.source,COMMERCIAL.target),(144,146))
        self.assertEqual(expected_origin_grant(value,'NORMAL')['compatible_max'],146)
        for key in ('provider_maintenance_sha256','writer_inventory_sha256','notification_cutover_sha256','database_structure_sha256'):
            bad=copy.deepcopy(value);bad.pop(key)
            with self.subTest(key=key), self.assertRaises(RuntimeError): admission.validate_contract(bad)
        for version in (5,True,7):
            bad=copy.deepcopy(value);bad['version']=version
            with self.subTest(version=version),self.assertRaises(RuntimeError): admission.validate_contract(bad)

    def test_superseded_coordinated_source_refuses_even_fresh_authority(self):
        with patch.object(admission,'require_fresh_authorization') as authorized:
            with self.assertRaisesRegex(RuntimeError,'superseded_non_executable'):
                release.admitted_manifest(self.root,successor_contract())
            authorized.assert_not_called()
        with self.assertRaisesRegex(ValueError,'not executable'):
            MigrationManifest.load(self.root/'web/deployment/releases'/release.MANIFEST,self.root)

    def test_published_sql_mirrors_metadata_and_order_cannot_change(self):
        release.source_manifest(self.root)
        for path in [self.root/'web/deployment/releases'/release.MANIFEST,self.root/'web/deployment/releases'/release.BRIDGE,
                     *self.root.glob('web/database/historical-architecture-146-150/*.sql'),*self.root.glob('web/supabase/historical-architecture-146-150/*.sql')]:
            before=path.read_bytes();path.write_bytes(before+b'\n')
            with self.subTest(path=path.name),self.assertRaises(RuntimeError):release.source_manifest(self.root)
            path.write_bytes(before)
        path=self.root/'web/deployment/releases'/release.MANIFEST
        original=path.read_bytes();actual=self.root/'alias.json';actual.write_bytes(original);path.unlink();path.symlink_to(actual)
        with self.assertRaises(OSError):release.source_manifest(self.root)

    def observation(self,schema):
        return {'system_identifier':successor_contract()['database']['system_identifier'],'schema':schema,
                'delivery_protocol':1 if schema==146 else 2,'outbox_protocol':2 if schema==149 else 1,
                **{name:0 for name in release.COUNTERS}}

    def test_both_queue_leases_deletion_sessions_prepared_and_locks_refuse(self):
        for schema in (146,147,148,149):
            value=self.observation(schema);release.require_database_quiescence(value,successor_contract(),schema)
            for key in value:
                bad=dict(value);bad[key]=True if isinstance(value[key],int) else 'wrong-cluster'
                with self.subTest(schema=schema,key=key),self.assertRaises(RuntimeError):
                    release.require_database_quiescence(bad,successor_contract(),schema)
            for key in release.COUNTERS:
                bad=dict(value);bad[key]=1
                with self.subTest(counter=key),self.assertRaises(RuntimeError):release.require_database_quiescence(bad,successor_contract(),schema)
        with self.assertRaises(RuntimeError):release.require_target_protocols(148,2,1)
        release.require_target_protocols(149,2,2)

    def test_new_manifest_guard_calls_current_provider_barrier_before_sql(self):
        calls=[]
        class Cursor:
            def execute(self,sql):calls.append(sql)
            def fetchone(self):return (self.value,)
        cursor=Cursor();cursor.value=self.observation(146)
        with patch.object(admission,'require_fresh_authorization',side_effect=lambda _:calls.append('authority')):
            release.migration_guard(successor_contract(),cursor,SimpleNamespace(number=147,from_schema=146,to_schema=147),
                consumer_guard=lambda:calls.append('consumers'),provider_guard=lambda a,b:calls.append((a,b)))
        self.assertEqual(calls[:3],['authority','consumers',(146,147)])
        self.assertIn(release.QUIESCENCE_SQL,calls)

    def test_intermediate_or_missing_activation_never_reaches_write_guard(self):
        handoff=CompletedNormalWriteHandoff.__new__(CompletedNormalWriteHandoff)
        handoff.profile=OUTBOX;handoff.contract=successor_contract();handoff.root=self.root;handoff.guard=lambda **_:self.fail('write guard reached')
        for schema in (146,147,148):
            with self.subTest(schema=schema),self.assertRaisesRegex(RuntimeError,'requires_target'):handoff.grant(schema=schema)
        with self.assertRaisesRegex(RuntimeError,'not_accepted'):handoff.grant(schema=149)
        actor=SimpleNamespace(contract=successor_contract(),provider_adapter=object())
        with self.assertRaisesRegex(RuntimeError,'not_installed'):controller.require_controller_adapter(actor)

    def test_every_mutating_worker_role_and_unknown_host_process_fail_closed(self):
        actors={str(i)*64:{'role':role,'image':'sha256:'+'a'*64,'spec_sha256':'b'*64,'generation':'origin'}
                for i,role in enumerate(sorted(consumers.WORKERS),1)}
        policy={'version':1,'operation':'delivery-outbox-deletion-exclusive-cutover','actors':actors}
        observed={key:{**row,'running':False,'restarting':False,'restart':'no'} for key,row in actors.items()}
        self.assertEqual(consumers.verify_actor_inventory(observed,policy)['unknown_actors'],0)
        for key in actors:
            bad=copy.deepcopy(observed);bad[key]['running']=True
            with self.assertRaises(RuntimeError):consumers.verify_actor_inventory(bad,policy)
        with self.assertRaises(RuntimeError):consumers.verify_actor_inventory({},policy)
        runtime=SimpleNamespace(command=lambda args:'10 uvicorn app:app\n11 python -m workers.data_deletion_worker' if args[0]=='ps' else '/docker/'+'a'*64)
        with self.assertRaisesRegex(RuntimeError,'live_mutating_worker'):consumers.verify_host_processes(runtime,{'a'*64},positive_pid=10)
