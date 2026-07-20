from __future__ import annotations

import io
import json
import math
import os
import socket
import statistics
import sys
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from data_analysis.ai.code_validator import validate_generated_code
from data_analysis.ai.result_validator import validate_analysis_result


def _network_denied(*_args, **_kwargs):
    raise PermissionError("network_disabled")


def main() -> int:
    os.environ.clear()
    socket.socket = _network_denied
    try:
        payload = json.loads(sys.stdin.buffer.read(5 * 1024 * 1024).decode("utf-8"))
        code = str(payload["code"])
        approved = {str(item) for item in payload["approved_columns"]}
        validate_generated_code(code=code, approved_columns=approved, require_result_variable=True)
        dataframe = pd.read_json(io.StringIO(payload["dataframe"]), orient="split")
        dataframe = dataframe[sorted(approved)].copy()
        safe_builtins = MappingProxyType({
            "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
            "enumerate": enumerate, "float": float, "int": int, "isinstance": isinstance,
            "len": len, "list": list, "max": max, "min": min, "range": range,
            "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
            "tuple": tuple, "zip": zip,
        })
        globals_scope = {"__builtins__": safe_builtins, "pd": pd, "np": np, "math": math, "statistics": statistics}
        local_scope = {"df": dataframe, "result": None}
        exec(code, globals_scope, local_scope)
        result = validate_analysis_result(local_scope.get("result"))
        sys.stdout.write(json.dumps({"success": True, "result": result}, separators=(",", ":")))
        return 0
    except BaseException as error:
        sys.stdout.write(json.dumps({"success": False, "code": type(error).__name__}, separators=(",", ":")))
        return 1


if __name__ == "__main__": raise SystemExit(main())
