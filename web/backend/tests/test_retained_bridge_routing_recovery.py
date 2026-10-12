"""Focused scope guards for the one-shot READ_ONLY availability repair."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

path=Path(__file__).resolve().parents[2]/'scripts/recover_completed_normal_read_only.py'
spec=importlib.util.spec_from_file_location('retained_bridge_recovery_tests',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class RetainedBridgeRoutingTests(unittest.TestCase):
    def setUp(self):
        self.version={'release_sha':'a'*40,'release_slot':'blue','schema_compatible_min':136,
                      'schema_compatible_max':144,'schema_excluded_versions':[142]}
        self.recovery={'restricted':True,'business_writes_enabled':False}
        self.components={k:'ok' for k in ('environment','database','auth','storage','schema','redis',
                                        'admin_mfa_policy','parser_isolation','backup_freshness')}
        self.components.update(notification_worker='unavailable',calendar_sync_worker='unavailable',
                               data_deletion_worker='unavailable')
        self.runtime=Mock()
        self.runtime.json_http.side_effect=lambda url: self.version if url.endswith('/version') else self.recovery
        self.runtime.fetch.side_effect=lambda url:(503,json.dumps({'ready':False,'components':self.components}).encode())
        self.actor=SimpleNamespace(runtime=self.runtime,contract={'candidate':{'source_sha':'a'*40}})

    def test_read_only_core_accepts_only_deliberately_stopped_business_workers(self):
        m.verify_core(self.actor)
        self.assertEqual(self.runtime.denied.call_count,2)
        self.assertEqual(self.runtime.http_status.call_args.args,('http://127.0.0.1:3100/',))

    def test_database_auth_storage_backup_or_unrelated_failure_rejects(self):
        for key in ('database','auth','storage','backup_freshness','other_dependency'):
            previous=dict(self.components);self.components[key]='unavailable'
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'core_unready'):
                m.verify_core(self.actor)
            self.components=previous

    def test_restricted_authority_is_required(self):
        for value in ({'restricted':False,'business_writes_enabled':True},
                      {'restricted':True,'business_writes_enabled':True}):
            self.recovery=value
            with self.assertRaisesRegex(RuntimeError,'write_fence_changed'):
                m.verify_endpoint(self.actor,'http://127.0.0.1:8101')

    def test_endpoint_source_slot_bounds_and_exclusion_are_exact(self):
        original=dict(self.version)
        for key,value in [('release_sha','b'*40),('release_slot','green'),('schema_compatible_min',115),
                          ('schema_compatible_max',145),('schema_excluded_versions',[])]:
            self.version=dict(original,**{key:value})
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'endpoint_identity_changed'):
                m.verify_endpoint(self.actor,'http://127.0.0.1:8101')

    def test_failed_write_denial_probe_is_not_ignored(self):
        self.runtime.denied.side_effect=RuntimeError('business_write_fence_failed')
        with self.assertRaisesRegex(RuntimeError,'business_write_fence_failed'):
            m.verify_core(self.actor)

    def test_malformed_source_cannot_select_another_package(self):
        for value in ('../other','x'*64,'a'*63):
            with self.assertRaisesRegex(RuntimeError,'source_hash_invalid'):m.assemble(value)


if __name__=='__main__':unittest.main()
