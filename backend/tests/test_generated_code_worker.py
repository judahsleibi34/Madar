import os
import subprocess
import unittest
from unittest.mock import patch

import pandas as pd

from data_analysis.ai.code_validator import CodeValidationError
from data_analysis.ai.sandbox import SandboxExecutionError, run_generated_code_locally


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
        crashed = subprocess.CompletedProcess([], 1, stdout=b'{"success":false,"code":"MemoryError"}')
        with patch("data_analysis.ai.sandbox.subprocess.run", return_value=crashed), \
             patch.dict(os.environ, {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            with self.assertRaisesRegex(SandboxExecutionError, "MemoryError"):
                run_generated_code_locally(pd.DataFrame({"score": [1]}), VALID_CODE, {"score"})


if __name__ == "__main__": unittest.main()
