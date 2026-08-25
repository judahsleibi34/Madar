import unittest
from unittest.mock import patch

import load_probe


class LoadProbeTests(unittest.TestCase):
    def test_transport_timeout_is_counted_instead_of_escaping(self):
        with patch("load_probe.urllib.request.urlopen", side_effect=TimeoutError("synthetic")):
            status, elapsed_ms, size = load_probe.request("http://127.0.0.1:1/", 0.01)
        self.assertEqual(status, 0)
        self.assertGreaterEqual(elapsed_ms, 0)
        self.assertEqual(size, 0)


if __name__ == "__main__":
    unittest.main()
