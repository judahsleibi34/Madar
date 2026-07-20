from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from data_analysis.ai.code_validator import validate_generated_code
from data_analysis.ai.result_validator import validate_analysis_result
from data_analysis.ai.settings import is_local_ai_exec_allowed

if os.name == "posix":
    import resource
else:
    resource = None


class SandboxExecutionError(RuntimeError):
    pass


MAX_SANDBOX_INPUT_BYTES = int(os.getenv("AI_SANDBOX_MAX_INPUT_BYTES", str(5 * 1024 * 1024)))
MAX_SANDBOX_OUTPUT_BYTES = int(os.getenv("AI_SANDBOX_MAX_OUTPUT_BYTES", str(1024 * 1024)))
SANDBOX_MEMORY_BYTES = int(os.getenv("AI_SANDBOX_MEMORY_BYTES", str(1024 * 1024 * 1024)))


def _limit_child() -> None:
    if resource is None:
        return

    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (SANDBOX_MEMORY_BYTES, SANDBOX_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_SANDBOX_OUTPUT_BYTES, MAX_SANDBOX_OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    if hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))


def run_generated_code_locally(
    df: pd.DataFrame,
    code: str,
    approved_columns: set[str] | list[str] | tuple[str, ...],
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    if not is_local_ai_exec_allowed():
        raise SandboxExecutionError("Local generated-code execution is disabled in this environment.")
    if os.getenv("AI_ISOLATED_WORKER_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise SandboxExecutionError("The isolated generated-code worker is not enabled.")
    if not isinstance(df, pd.DataFrame):
        raise SandboxExecutionError("Sandbox expected a pandas DataFrame")
    approved = {str(column) for column in approved_columns}
    validate_generated_code(code=code, approved_columns=approved, require_result_variable=True)
    missing = [column for column in approved if column not in df.columns]
    if missing:
        raise SandboxExecutionError(f"Approved columns are missing from dataframe: {missing}")
    payload = json.dumps({
        "code": code,
        "approved_columns": sorted(approved),
        "dataframe": df[sorted(approved)].to_json(orient="split", date_format="iso"),
    }, separators=(",", ":")).encode()
    if len(payload) > MAX_SANDBOX_INPUT_BYTES:
        raise SandboxExecutionError("Sandbox input is too large")
    worker = Path(__file__).resolve().parents[2] / "workers" / "generated_code_worker.py"
    timeout = max(1, min(int(timeout_seconds or 5), 30))
    with tempfile.TemporaryDirectory(prefix="madar-ai-worker-") as workdir:
        env = {
            "PATH": os.getenv("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "PYTHONIOENCODING": "utf-8",
            "MPLCONFIGDIR": str(Path(workdir) / "mpl"),
        }
        try:
            process = subprocess.run(
                [sys.executable, "-I", str(worker)],
                input=payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=workdir,
                env=env,
                timeout=timeout,
                check=False,
                start_new_session=True,
                preexec_fn=_limit_child if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired as error:
            raise SandboxExecutionError("Generated code timed out") from error
    if len(process.stdout) > MAX_SANDBOX_OUTPUT_BYTES:
        raise SandboxExecutionError("Generated code output is too large")
    try:
        response = json.loads(process.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SandboxExecutionError("Generated code worker returned an invalid result") from error
    if process.returncode != 0 or not response.get("success"):
        raise SandboxExecutionError(str(response.get("code") or "Generated code failed"))
    return validate_analysis_result(response.get("result"))
