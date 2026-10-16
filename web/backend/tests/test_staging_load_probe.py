from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch


class StagingLoadProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ.get("MADAR_TEST_REPOSITORY_ROOT", Path(__file__).resolve().parents[2]))
        spec = importlib.util.spec_from_file_location("staging_load_probe", root / "staging/load_probe.py")
        cls.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.probe)

    def test_redirect_is_measured_without_loading_the_redirect_destination(self):
        followed = []

        class Destination(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                followed.append(True)
                self.send_response(200)
                self.end_headers()

        destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)

        class Redirect(Destination):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/unverified-target")
                self.end_headers()

        source = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        for server in (destination, source):
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 2)
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "no_proxy": ""}):
            status, _elapsed, _size = self.probe.request(f"http://127.0.0.1:{source.server_port}/", 2)
        self.assertEqual(status, 302)
        self.assertEqual(followed, [])

    def test_timeout_is_recorded_as_transport_failure(self):
        with patch.object(self.probe.OPENER, "open", side_effect=TimeoutError("synthetic")):
            status, _elapsed, size = self.probe.request("http://127.0.0.1:1/", 0.01)
        self.assertEqual((status, size), (0, 0))

    def test_cli_rejects_unsafe_targets_and_unbounded_timeouts_before_requests(self):
        cases = (
            ["https://production.example/"], ["http://127.0.0.1:invalid/"],
            ["http://user:password@127.0.0.1/"], ["http://127.0.0.1/#fragment"],
            ["http://127.0.0.1/", "--timeout", "nan"], ["http://127.0.0.1/", "--timeout", "inf"],
            ["http://127.0.0.1/", "--timeout", "-1"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments), patch.object(sys, "argv", ["load_probe", *arguments]), \
                 patch.object(self.probe, "request") as request:
                with self.assertRaises(SystemExit):
                    self.probe.main()
                request.assert_not_called()
