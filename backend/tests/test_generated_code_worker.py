import os
import subprocess
import unittest
from unittest.mock import patch

import pandas as pd

from data_analysis.ai.code_validator import CodeValidationError
from data_analysis.ai.sandbox import SandboxExecutionError, run_generated_code_locally
from data_analysis.ai import sandbox


VALID_CODE = '''
mean_value = float(df["score"].mean())
result = {"title": "Mean", "summary": "Calculated safely", "metrics": [{"label": "Mean", "value": mean_value}], "tables": [], "charts": []}
'''


class GeneratedCodeWorkerTests(unittest.TestCase):
    def run_valid(self):
        with patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            return run_generated_code_locally(pd.DataFrame({"score": [10, 20]}), VALID_CODE, {"score"}, 10)

    def test_valid_code_runs_in_isolated_process(self):
        result = self.run_valid()
        self.assertEqual(result["metrics"][0]["value"], 15.0)

    def test_worker_forces_numerical_libraries_to_one_thread(self):
        expected = {
            "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
        }
        self.assertEqual(set(sandbox.WORKER_THREAD_ENV), expected)
        self.assertTrue(all(value == "1" for value in sandbox.WORKER_THREAD_ENV.values()))

    def test_valid_numpy_operation_runs_with_limits(self):
        code = '''
mean_value = float(np.mean(df["score"]))
result = {"title": "Mean", "summary": "Calculated safely", "metrics": [{"label": "Mean", "value": mean_value}], "tables": [], "charts": []}
'''
        with patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            result = run_generated_code_locally(pd.DataFrame({"score": [2, 4]}), code, {"score"}, 10)
        self.assertEqual(result["metrics"][0]["value"], 3.0)

    def test_worker_is_required_even_when_local_exec_flag_is_enabled(self):
        with patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "false"}, clear=False):
            with self.assertRaisesRegex(SandboxExecutionError, "isolated"):
                run_generated_code_locally(pd.DataFrame({"score": [1]}), VALID_CODE, {"score"})

    def test_network_filesystem_and_process_imports_are_blocked(self):
        for code in ("import socket\nresult = {}", "open('/etc/passwd')\nresult = {}", "import multiprocessing\nresult = {}"):
            with self.subTest(code=code), self.assertRaises(CodeValidationError):
                with patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
                    run_generated_code_locally(pd.DataFrame({"score": [1]}), code, {"score"})

    def test_timeout_kills_worker_and_returns_structured_error(self):
        with patch("data_analysis.ai.sandbox.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 1)), \
             patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            with self.assertRaisesRegex(SandboxExecutionError, "timed out"):
                run_generated_code_locally(pd.DataFrame({"score": [1]}), VALID_CODE, {"score"}, 1)

    def test_worker_crash_and_oversized_output_fail_closed(self):
        crashed = subprocess.CompletedProcess([], 1, stdout=b'{"success":false,"code":"MemoryError"}', stderr=b"")
        with patch("data_analysis.ai.sandbox.subprocess.run", return_value=crashed), \
             patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            with self.assertRaisesRegex(SandboxExecutionError, "MemoryError"):
                run_generated_code_locally(pd.DataFrame({"score": [1]}), VALID_CODE, {"score"})

        oversized = subprocess.CompletedProcess([], 1, stdout=b"x" * (sandbox.MAX_SANDBOX_OUTPUT_BYTES + 1), stderr=b"")
        with patch("data_analysis.ai.sandbox.subprocess.run", return_value=oversized), patch.dict(
            os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False
        ), self.assertRaisesRegex(SandboxExecutionError, "too large"):
            run_generated_code_locally(pd.DataFrame({"score": [1]}), VALID_CODE, {"score"})

    def test_startup_and_malformed_protocol_errors_are_structured(self):
        startup = subprocess.CompletedProcess([], 1, stdout=b'{"success":false,"code":"worker_startup_ImportError"}', stderr=b"")
        malformed = subprocess.CompletedProcess([], 1, stdout=b"not-json", stderr=b"bounded diagnostic")
        for process, expected in ((startup, "worker_startup_ImportError"), (malformed, "worker_protocol_invalid")):
            with self.subTest(expected=expected), patch(
                "data_analysis.ai.sandbox.subprocess.run", return_value=process
            ), patch.dict(
                os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False
            ), self.assertRaisesRegex(SandboxExecutionError, expected):
                run_generated_code_locally(pd.DataFrame({"score": [1]}), VALID_CODE, {"score"})


if __name__ == "__main__": unittest.main()
