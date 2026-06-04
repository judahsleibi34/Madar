from __future__ import annotations

from types import MappingProxyType
from typing import Any

import math
import statistics

import numpy as np
import pandas as pd

from data_analysis.ai.code_validator import validate_generated_code
from data_analysis.ai.result_validator import validate_analysis_result
from data_analysis.ai.settings import is_local_ai_exec_allowed


class SandboxExecutionError(RuntimeError):
    pass


SAFE_BUILTINS = MappingProxyType(
    {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
)


SAFE_GLOBALS = {
    "__builtins__": SAFE_BUILTINS,
    "pd": pd,
    "np": np,
    "math": math,
    "statistics": statistics,
}


def run_generated_code_locally(
    df: pd.DataFrame,
    code: str,
    approved_columns: set[str] | list[str] | tuple[str, ...],
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    if not is_local_ai_exec_allowed():
        raise SandboxExecutionError(
            "Local generated-code execution is disabled in this environment."
        )

    if not isinstance(df, pd.DataFrame):
        raise SandboxExecutionError("Sandbox expected a pandas DataFrame")

    approved_column_set = {str(column) for column in approved_columns}

    validate_generated_code(
        code=code,
        approved_columns=approved_column_set,
        require_result_variable=True,
    )

    safe_df = _copy_approved_dataframe(df, approved_column_set)

    local_scope: dict[str, Any] = {
        "df": safe_df,
        "result": None,
    }

    try:
        # In-process exec cannot enforce a hard timeout safely. Production must
        # use AI_ALLOW_LOCAL_EXEC=false and run generated code in an isolated worker.
        _ = timeout_seconds
        exec(
            code,
            dict(SAFE_GLOBALS),
            local_scope,
        )
    except Exception as exc:
        raise SandboxExecutionError("Generated code failed") from exc

    result = local_scope.get("result")

    if result is None:
        raise SandboxExecutionError("Generated code did not produce result")

    return validate_analysis_result(result)


def _copy_approved_dataframe(
    df: pd.DataFrame,
    approved_columns: set[str],
) -> pd.DataFrame:
    missing_columns = [
        column
        for column in approved_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise SandboxExecutionError(
            f"Approved columns are missing from dataframe: {missing_columns}"
        )

    safe_df = df[list(approved_columns)].copy()
    safe_df.columns = [str(column) for column in safe_df.columns]

    return safe_df
