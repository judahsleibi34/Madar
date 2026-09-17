import importlib.util
import socket
import unittest
from pathlib import Path


def load_guard():
    path = Path(__file__).resolve().parents[1] / "scripts/run_tests_no_external_network.py"
    spec = importlib.util.spec_from_file_location("outbound_test_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OutboundTestGuardTests(unittest.TestCase):
    def test_loopback_host_allowlist(self):
        guard = load_guard()
        for host in ("localhost", "127.0.0.1", "::1"):
            with self.subTest(host=host):
                self.assertTrue(guard._loopback_host(host))

    def test_external_connection_is_rejected_and_recorded(self):
        guard = load_guard()
        candidate = type("FakeSocket", (), {"family": socket.AF_INET})()
        with self.assertRaisesRegex(OSError, "external network disabled"):
            guard._guarded_connect(candidate, ("203.0.113.1", 443))
        self.assertEqual(guard.EXTERNAL_ATTEMPTS, ["203.0.113.1"])

    def test_external_dns_is_replaced_without_network_access(self):
        guard = load_guard()
        result = guard._guarded_getaddrinfo("example.com", 443)
        self.assertEqual(result[0][4], ("93.184.216.34", 443))
        self.assertEqual(guard.EXTERNAL_ATTEMPTS, [])


if __name__ == "__main__":
    unittest.main()
