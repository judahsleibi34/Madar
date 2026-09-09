import unittest
from services.commercial_metrics import commercial_metric_snapshot, record_commercial_metric


class CommercialMetricsTests(unittest.TestCase):
    def test_bounded_counters_reject_arbitrary_sensitive_labels(self):
        before = commercial_metric_snapshot()
        record_commercial_metric('capability_denial')
        record_commercial_metric('untrusted-receipt-or-credential')
        after = commercial_metric_snapshot()
        self.assertEqual(set(before), set(after))
        self.assertEqual(after['commercial_capability_denial_total'], before['commercial_capability_denial_total'] + 1)
        self.assertNotIn('untrusted', str(after))
