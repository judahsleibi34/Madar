import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import pitr_rehearsal as pitr

class PitrSafetyTests(unittest.TestCase):
    def test_primary_host_rejected_before_docker_or_filesystem_mutation(self):
        with patch.object(pitr.manage.socket,'gethostname',return_value='madar-gpu'),patch.object(pitr.manage,'docker') as docker:
            with self.assertRaises(RuntimeError):pitr.main('REHEARSE')
            docker.assert_not_called()
    def test_unknown_owner_scope_and_name_cannot_be_removed(self):
        for changed in ('owner','scope','name'):
            row={'Name':'/owned','Config':{'Labels':{pitr.SCOPE_LABEL:'test','com.madar.staging.owner':pitr.manage.OWNER}}}
            if changed=='owner':row['Config']['Labels']['com.madar.staging.owner']='unrelated'
            elif changed=='scope':row['Config']['Labels'][pitr.SCOPE_LABEL]='other'
            else:row['Name']='/unrelated'
            with patch.object(pitr.manage,'docker',return_value=json.dumps([row])) as docker:
                with self.assertRaises(RuntimeError):pitr.remove_container('owned','test')
                self.assertEqual(docker.call_count,1)
    def test_only_exact_owned_container_is_removed(self):
        row={'Name':'/owned','Config':{'Labels':{pitr.SCOPE_LABEL:'test','com.madar.staging.owner':pitr.manage.OWNER}}}
        with patch.object(pitr.manage,'docker',side_effect=[json.dumps([row]),b'']) as docker:
            pitr.remove_container('owned','test')
            self.assertEqual(docker.call_args.args,('rm','--force','owned'))
