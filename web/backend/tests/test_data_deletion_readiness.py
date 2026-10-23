"""A live standby is not proof of functional deletion consumption."""
import os
import unittest
from unittest.mock import Mock,patch
from services import readiness_service as readiness


class DeletionConsumptionReadinessTests(unittest.TestCase):
    def test_only_positive_consuming_health_is_ready(self):
        environment={'DATA_DELETION_WORKER_REQUIRED':'true','DATA_DELETION_WORKER_ENABLED':'true',
                     'DATA_DELETION_WORKER_HEALTH_URL':'http://127.0.0.1:8094/health'}
        for payload,expected in [({'status':'ok','consuming':True},'ok'),
                ({'status':'ok','consuming':False},'unavailable'),
                ({'status':'ok','consuming':'true'},'unavailable'),
                ({'status':'starting','consuming':True},'unavailable'),({},'unavailable'),([], 'unavailable')]:
            with self.subTest(payload=payload),patch.dict(os.environ,environment),patch.object(
                    readiness.requests,'get',return_value=Mock(status_code=200,json=Mock(return_value=payload))):
                self.assertEqual(readiness.check_data_deletion_worker(),expected)
    def test_malformed_health_is_not_ready(self):
        with patch.dict(os.environ,{'DATA_DELETION_WORKER_REQUIRED':'true','DATA_DELETION_WORKER_ENABLED':'true',
                'DATA_DELETION_WORKER_HEALTH_URL':'http://127.0.0.1:8094/health'}),patch.object(
                readiness.requests,'get',return_value=Mock(status_code=200,json=Mock(side_effect=ValueError('invalid')))):
            self.assertEqual(readiness.check_data_deletion_worker(),'unavailable')
