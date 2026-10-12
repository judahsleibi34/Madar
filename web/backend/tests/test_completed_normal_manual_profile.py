"""The manual successor cannot inherit historical authorization or range."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from deployment.lib import completed_normal_admission as admission
from deployment.lib.completed_normal_profile import LEGACY, MANUAL, profile, expected_origin_grant
from test_completed_normal_admission import fixture_contract


def manual_contract():
    value=fixture_contract()
    value.update(version=2,operation=MANUAL.operation)
    root=admission.ADMISSIONS/('a'*64)
    value['source_roles']={'application_sha':'a'*40,'controller_sha':'b'*40,
        'completion_root':str(root),'completion_sha256':'1'*64,
        'completed_compatible_upgrade':True,'schema':136}
    value['database']['schema']=136
    value['candidate'].update(compatible_min=136,compatible_max=144)
    value['historical_files']={str(root/name):'7'*64 for name in admission.COMPATIBLE_HISTORICAL_NAMES}
    return value


class ManualProfileTests(unittest.TestCase):
    def test_legacy_contract_keeps_exact_original_operation(self):
        value=fixture_contract();admission.validate_contract(value)
        self.assertIs(profile(value),LEGACY)

    def test_manual_contract_is_separate_completed_origin(self):
        value=manual_contract();admission.validate_contract(value)
        self.assertIs(profile(value),MANUAL)
        self.assertEqual(MANUAL.migrations,(137,138,139,140,141,143,144))
        self.assertFalse(MANUAL.supports(142))
        self.assertFalse(MANUAL.supports(True))
        self.assertFalse(MANUAL.supports(145))

    def test_operation_version_and_origin_cannot_mix(self):
        for field,value in [('version',1),('operation',LEGACY.operation),('operation','release')]:
            contract=manual_contract();contract[field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):admission.validate_contract(contract)
        for field,value in [('completed_compatible_upgrade',False),('schema',115),('completion_root','/tmp/attacker')]:
            contract=manual_contract();contract['source_roles'][field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):admission.validate_contract(contract)

    def test_schema_and_history_cannot_be_widened(self):
        for field,value in [('compatible_min',115),('compatible_max',145)]:
            contract=manual_contract();contract['candidate'][field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):admission.validate_contract(contract)
        contract=manual_contract();contract['historical_files'].pop(next(iter(contract['historical_files'])))
        with self.assertRaises(RuntimeError):admission.validate_contract(contract)

    def test_fresh_authorization_binds_new_operation_and_source_schema(self):
        contract=manual_contract()
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'interlock';path.write_text(json.dumps({'status':'authorized_cycle','rehearsal_sha256':contract['rehearsal_sha256']}))
            with patch.object(admission,'require_upgrade_authorization') as required,patch('deployment.lib.control_plane_upgrade_authorization.UPGRADE_INTERLOCK',path):
                admission.require_fresh_authorization(contract)
            self.assertEqual(required.call_args.kwargs['required_operation'],MANUAL.operation)
            self.assertEqual(required.call_args.kwargs['required_schema'],136)

    def test_origin_grant_remains_historical_136_range(self):
        grant=expected_origin_grant(manual_contract(),'READ_ONLY')
        self.assertEqual((grant['version'],grant['schema'],grant['compatible_min'],grant['compatible_max']),(2,136,115,136))
        self.assertNotEqual(grant['release_sha'],manual_contract()['candidate']['source_sha'])

    def test_manual_grant_cannot_publish_normal_at_source_schema(self):
        from deployment.lib.completed_normal_write_handoff import CompletedNormalWriteHandoff
        driver=object.__new__(CompletedNormalWriteHandoff);driver.profile=MANUAL
        with self.assertRaisesRegex(RuntimeError,'requires_target_schema'):
            driver.grant(schema=136)

    def test_restart_before_complete_backup_cannot_regrant_normal(self):
        from deployment.lib.completed_normal_database import require_manual_normal_completion
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError,'normal_completion_pending'):
                require_manual_normal_completion(manual_contract(),Path(directory))

    def test_candidate_grant_rejects_142_old_range_and_wrong_identity(self):
        contract=manual_contract()
        grant={'version':2,'schema':144,'release_sha':contract['candidate']['source_sha'],
            'contract_digest':admission.digest(contract),'mode':'READ_ONLY','compatible_min':136,'compatible_max':144}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/admission.digest(contract)/'write-authority/authority.json';path.parent.mkdir(parents=True)
            with patch('deployment.lib.provider_recovery_runtime.protected',lambda p,**kw:Path(p)),patch.object(os,'geteuid',return_value=0):
                path.write_text(json.dumps(grant));self.assertEqual(admission.require_candidate_authority(contract,admissions=root),grant)
                for change in ({'schema':142},{'compatible_min':115},{'compatible_max':136},{'release_sha':'f'*40},{'contract_digest':'f'*64}):
                    path.write_text(json.dumps(dict(grant,**change)))
                    with self.subTest(change=change),self.assertRaises(RuntimeError):admission.require_candidate_authority(contract,admissions=root)


if __name__=='__main__':unittest.main()
