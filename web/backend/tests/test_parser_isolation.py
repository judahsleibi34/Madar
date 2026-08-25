import json
import base64
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from data_analysis.io.data_reading import DataReadingNormal, ParserWorkerUnavailableError
from workers import parser_worker


def _slow_parser(_payload):
    time.sleep(2)
    return {"columns": [], "data": []}


def _successful_parser(_payload):
    return {"columns": ["name"], "data": [["A"]]}


class ParserIsolationTests(unittest.TestCase):
    def setUp(self):
        DataReadingNormal.clear_shared_cache()

    def _dataset(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name).resolve()
        scoped = root / "tenant_7" / "user_12"
        scoped.mkdir(parents=True)
        dataset = scoped / "data.csv"
        dataset.write_text("name,value\nA,1\n", encoding="utf-8")
        return temporary, root, dataset

    def test_worker_parses_only_the_authorized_tenant_user_path(self):
        temporary, root, dataset = self._dataset()
        self.addCleanup(temporary.cleanup)
        with patch.dict(
            "os.environ",
            {
                "DATA_UPLOAD_DIR": str(root),
                "PARSER_WORKER_PROCESS": "true",
                "PARSER_ISOLATED_WORKER_ENABLED": "true",
            },
            clear=False,
        ):
            result = parser_worker.parse_dataset(
                {"input_path": str(dataset), "tenant_id": "7", "user_id": "12"}
            )
            self.assertEqual(result["columns"], ["name", "value"])
            self.assertEqual(result["data"], [["A", 1]])
            with self.assertRaisesRegex(RuntimeError, "Failed to read data"):
                parser_worker.parse_dataset(
                    {"input_path": str(dataset), "tenant_id": "8", "user_id": "12"}
                )

    def test_backend_accepts_a_bounded_valid_worker_result(self):
        temporary, root, dataset = self._dataset()
        self.addCleanup(temporary.cleanup)
        response = Mock(status_code=200)
        response.headers = {}
        response.iter_content.return_value = [
            json.dumps({"columns": ["name", "value"], "data": [["A", 1]]}).encode()
        ]
        response.json.side_effect = lambda: json.loads(response._content)
        with patch.dict(
            "os.environ",
            {
                "DATA_UPLOAD_DIR": str(root),
                "PARSER_ISOLATED_WORKER_ENABLED": "true",
                "PARSER_WORKER_PROCESS": "false",
            },
            clear=False,
        ), patch("data_analysis.io.data_reading.requests.post", return_value=response) as post:
            dataframe = DataReadingNormal(
                str(dataset), tenant_id="7", user_id="12"
            ).read()
        self.assertEqual(dataframe.to_dict("records"), [{"name": "A", "value": 1}])
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertTrue(post.call_args.kwargs["stream"])

    def test_backend_fails_closed_for_worker_failure_and_invalid_result(self):
        temporary, root, dataset = self._dataset()
        self.addCleanup(temporary.cleanup)
        failed = Mock(status_code=500)
        invalid = Mock(status_code=200)
        invalid.headers = {}
        invalid.iter_content.return_value = [b'{"columns":[],"data":"wrong"}']
        invalid.json.side_effect = lambda: json.loads(invalid._content)
        environment = {
            "DATA_UPLOAD_DIR": str(root),
            "PARSER_ISOLATED_WORKER_ENABLED": "true",
            "PARSER_WORKER_PROCESS": "false",
        }
        with patch.dict("os.environ", environment, clear=False), patch(
            "data_analysis.io.data_reading.requests.post", return_value=failed
        ):
            with self.assertRaises(ParserWorkerUnavailableError) as context:
                DataReadingNormal(
                    str(dataset), tenant_id="7", user_id="12"
                ).read(refresh=True)
        self.assertEqual(context.exception.status_code, 503)

        with patch.dict("os.environ", environment, clear=False), patch(
            "data_analysis.io.data_reading.requests.post", return_value=invalid
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to read data"):
                DataReadingNormal(
                    str(dataset), tenant_id="7", user_id="12"
                ).read(refresh=True)

    def test_backend_returns_controlled_503_when_worker_times_out(self):
        temporary, root, dataset = self._dataset()
        self.addCleanup(temporary.cleanup)
        with patch.dict(
            "os.environ",
            {
                "DATA_UPLOAD_DIR": str(root),
                "PARSER_ISOLATED_WORKER_ENABLED": "true",
                "PARSER_WORKER_PROCESS": "false",
            },
            clear=False,
        ), patch(
            "data_analysis.io.data_reading.requests.post",
            side_effect=requests.Timeout("parser timeout"),
        ):
            with self.assertRaises(ParserWorkerUnavailableError) as context:
                DataReadingNormal(
                    str(dataset), tenant_id="7", user_id="12"
                ).read(refresh=True)
        self.assertEqual(getattr(context.exception, "status_code", None), 503)
        self.assertEqual(context.exception.headers.get("Retry-After"), "30")

    def test_worker_rejects_remote_and_unscoped_requests(self):
        with self.assertRaisesRegex(ValueError, "remote_input_not_allowed"):
            parser_worker.parse_dataset(
                {
                    "input_path": "https://example.com/data.csv",
                    "tenant_id": "7",
                    "user_id": "12",
                }
            )
        with self.assertRaisesRegex(ValueError, "invalid_parse_request"):
            parser_worker.parse_dataset(
                {"input_path": "/tmp/data.csv", "tenant_id": None, "user_id": "12"}
            )

    def test_worker_parses_bounded_remote_content_without_network_or_host_path(self):
        result = parser_worker.parse_dataset(
            {
                "content_b64": base64.b64encode(b"name,value\nA,1\n").decode("ascii"),
                "source_url": "https://example.com/data.csv",
                "content_type": "text/csv",
                "tenant_id": "7",
                "user_id": "12",
            }
        )
        self.assertEqual(result["columns"], ["name", "value"])
        self.assertEqual(result["data"], [["A", 1]])

    def test_worker_rejects_oversized_or_ambiguous_remote_content(self):
        common = {
            "content_b64": base64.b64encode(b"a\n1\n").decode("ascii"),
            "source_url": "https://example.com/data.csv",
            "content_type": "text/csv",
            "tenant_id": "7",
            "user_id": "12",
        }
        with self.assertRaisesRegex(ValueError, "invalid_parse_request"):
            parser_worker.parse_dataset({**common, "input_path": "/tmp/data.csv"})
        with patch.object(parser_worker, "MAX_CONTENT_BYTES", 1), self.assertRaisesRegex(
            ValueError, "remote_content_invalid"
        ):
            parser_worker.parse_dataset(common)
        for html_payload in (
            {**common, "content_type": "text/html"},
            {
                **common,
                "content_b64": base64.b64encode(
                    b"<!doctype html><title>not a dataset</title>"
                ).decode("ascii"),
            },
        ):
            with self.assertRaisesRegex(ValueError, "remote_content_invalid"):
                parser_worker.parse_dataset(html_payload)

    def test_worker_hard_timeout_terminates_child_and_accepts_next_job(self):
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "parser_job_timeout"):
            parser_worker.parse_dataset_with_timeout(
                {"input_path": "unused", "tenant_id": "7", "user_id": "12"},
                parse_target=_slow_parser,
                timeout_seconds=1,
            )
        # The one-second untrusted-job budget starts only after a freshly
        # spawned interpreter reports ready. Cold startup has a separate
        # ten-second cap and termination has a two-second cap, so assert the
        # full documented bound instead of a scheduler-sensitive cold-start
        # benchmark.
        self.assertLess(time.monotonic() - started, 14.5)

        result = parser_worker.parse_dataset_with_timeout(
            {"input_path": "unused", "tenant_id": "7", "user_id": "12"},
            parse_target=_successful_parser,
            timeout_seconds=2,
        )
        self.assertEqual(result, {"columns": ["name"], "data": [["A"]]})

    def test_compose_enforces_worker_resource_and_network_isolation(self):
        repository_root = Path(
            os.getenv("MADAR_TEST_REPOSITORY_ROOT", Path(__file__).resolve().parents[2])
        )
        compose = (repository_root / "docker-compose.yml").read_text(encoding="utf-8")
        worker = compose.split("\n  parser-worker:\n", 1)[1].split("\n  frontend:\n", 1)[0]
        self.assertIn('user: "65534:65534"', worker)
        self.assertIn("read_only: true", worker)
        self.assertIn('cap_drop: ["ALL"]', worker)
        self.assertIn('security_opt: ["no-new-privileges:true"]', worker)
        self.assertIn("pids_limit: 64", worker)
        self.assertIn(
            "${MADAR_STORAGE_ROOT:-../backend}/private_uploads:/app/private_uploads:ro",
            worker,
        )
        self.assertIn("- parser_internal", worker)
        self.assertNotIn("env_file:", worker)
        networks = compose.split("\nnetworks:\n", 1)[1]
        self.assertIn("parser_internal:", networks)
        self.assertIn("internal: true", networks)


if __name__ == "__main__":
    unittest.main()
