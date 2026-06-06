from __future__ import annotations

import ast
from typing import Iterable


ALLOWED_IMPORT_ROOTS = {
    "pandas",
    "numpy",
    "math",
    "statistics",
    "scipy",
    "sklearn",
    "statsmodels",
}

FORBIDDEN_IMPORT_ROOTS = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "pathlib",
    "shutil",
    "glob",
    "pickle",
    "marshal",
    "importlib",
    "inspect",
    "builtins",
    "ctypes",
    "multiprocessing",
    "threading",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "ssl",
    "tempfile",
    "sqlite3",
    "psycopg2",
    "pymysql",
    "mysql",
    "sqlalchemy",
    "boto3",
    "paramiko",
    "fabric",
    "email",
    "imaplib",
    "poplib",
    "webbrowser",
}

FORBIDDEN_CALL_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "input",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "__import__",
    "help",
    "breakpoint",
    "memoryview",
    "super",
    "classmethod",
    "staticmethod",
    "property",
}

FORBIDDEN_ATTRIBUTE_NAMES = {
    "__dict__",
    "__class__",
    "__bases__",
    "__base__",
    "__subclasses__",
    "__globals__",
    "__code__",
    "__closure__",
    "__func__",
    "__self__",
    "__module__",
    "__mro__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "__init_subclass__",
    "__reduce__",
    "__reduce_ex__",
    "__getstate__",
    "__setstate__",
}

FORBIDDEN_PANDAS_IO_FUNCTIONS = {
    "read_csv",
    "read_excel",
    "read_json",
    "read_html",
    "read_xml",
    "read_pickle",
    "read_parquet",
    "read_feather",
    "read_hdf",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_stata",
    "read_sas",
    "read_spss",
    "read_orc",
    "read_clipboard",
    "read_fwf",
    "read_table",
    "read_gbq",
}

FORBIDDEN_DATAFRAME_IO_METHODS = {
    "to_csv",
    "to_excel",
    "to_json",
    "to_html",
    "to_xml",
    "to_pickle",
    "to_parquet",
    "to_feather",
    "to_hdf",
    "to_sql",
    "to_stata",
    "to_latex",
    "to_markdown",
    "to_clipboard",
    "to_gbq",
}

FORBIDDEN_FULL_DATA_EXTRACTION_METHODS = {
    "to_dict",
    "to_records",
    "to_numpy",
    "iterrows",
    "itertuples",
}

FORBIDDEN_FULL_DATA_ATTRIBUTES = {
    "values",
}

FORBIDDEN_EXPENSIVE_METHODS = {
    "merge",
    "join",
    "applymap",
}

FORBIDDEN_DF_ATTRIBUTES = {
    "columns",
    "index",
    "dtypes",
    "shape",
    "size",
    "values",
}

FORBIDDEN_NODE_TYPES = (
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Raise,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.Lambda,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Await,
    ast.Yield,
    ast.YieldFrom,
)

FORBIDDEN_LOOP_TYPES = (
    ast.For,
    ast.AsyncFor,
    ast.While,
)

FORBIDDEN_COMPREHENSION_TYPES = (
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)

MAX_CODE_LENGTH = 16_000
MAX_AST_NODES = 1_200
MAX_STRING_LITERAL_LENGTH = 2_000
MAX_NUMERIC_LITERAL_ABS = 10_000_000
MAX_RANGE_LIMIT = 100_000


class CodeValidationError(ValueError):
    pass


def validate_generated_code(
    code: str,
    approved_columns: set[str] | list[str] | tuple[str, ...] | None = None,
    require_result_variable: bool = True,
    max_code_length: int = MAX_CODE_LENGTH,
    max_ast_nodes: int = MAX_AST_NODES,
) -> None:
    if not isinstance(code, str) or not code.strip():
        raise CodeValidationError("Generated code is empty")

    if len(code) > max_code_length:
        raise CodeValidationError("Generated code is too long")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodeValidationError(f"Invalid Python syntax: {exc}") from exc

    node_count = sum(1 for _ in ast.walk(tree))

    if node_count > max_ast_nodes:
        raise CodeValidationError("Generated code is too complex")

    approved_column_set = {str(column) for column in approved_columns or []}
    assigned_names: set[str] = set()

    for node in ast.walk(tree):
        _validate_node_type(node)
        _validate_literals(node)
        _validate_imports(node)
        _validate_calls(node)
        _validate_attributes(node)
        _validate_names(node)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                assigned_names.update(_iter_assigned_names(target))

        elif isinstance(node, ast.AnnAssign):
            assigned_names.update(_iter_assigned_names(node.target))

        elif isinstance(node, ast.AugAssign):
            assigned_names.update(_iter_assigned_names(node.target))

    if require_result_variable and "result" not in assigned_names:
        raise CodeValidationError("Generated code must assign final output to result")

    if approved_column_set:
        _validate_dataframe_column_usage(tree, approved_column_set)


def _validate_node_type(node: ast.AST) -> None:
    if isinstance(node, FORBIDDEN_NODE_TYPES):
        raise CodeValidationError(f"Forbidden syntax: {node.__class__.__name__}")

    if isinstance(node, FORBIDDEN_LOOP_TYPES):
        raise CodeValidationError(f"Loops are not allowed: {node.__class__.__name__}")

    if isinstance(node, FORBIDDEN_COMPREHENSION_TYPES):
        raise CodeValidationError(
            f"Comprehensions are not allowed: {node.__class__.__name__}"
        )


def _validate_literals(node: ast.AST) -> None:
    if not isinstance(node, ast.Constant):
        return

    value = node.value

    if isinstance(value, str) and len(value) > MAX_STRING_LITERAL_LENGTH:
        raise CodeValidationError("String literal is too long")

    if isinstance(value, (int, float)) and abs(value) > MAX_NUMERIC_LITERAL_ABS:
        raise CodeValidationError("Numeric literal is too large")


def _validate_imports(node: ast.AST) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            root = _root_module_name(alias.name)
            _validate_import_root(root)

    elif isinstance(node, ast.ImportFrom):
        root = _root_module_name(node.module)
        _validate_import_root(root)


def _validate_calls(node: ast.AST) -> None:
    if not isinstance(node, ast.Call):
        return

    call_name = _get_call_name(node)
    qualified_name = _get_qualified_call_name(node)

    if call_name in FORBIDDEN_CALL_NAMES:
        raise CodeValidationError(f"Forbidden function call: {call_name}")

    if call_name in FORBIDDEN_PANDAS_IO_FUNCTIONS:
        raise CodeValidationError(f"Forbidden data read function: {call_name}")

    if call_name in FORBIDDEN_DATAFRAME_IO_METHODS:
        raise CodeValidationError(f"Forbidden data write method: {call_name}")

    if call_name in FORBIDDEN_FULL_DATA_EXTRACTION_METHODS:
        raise CodeValidationError(f"Forbidden full-data extraction method: {call_name}")

    if call_name in FORBIDDEN_EXPENSIVE_METHODS:
        raise CodeValidationError(
            f"Potentially expensive method is not allowed: {call_name}"
        )

    if qualified_name:
        if qualified_name.startswith("pd.") and call_name in FORBIDDEN_PANDAS_IO_FUNCTIONS:
            raise CodeValidationError(f"Forbidden pandas I/O call: {qualified_name}")

        if qualified_name.startswith("df.") and call_name in FORBIDDEN_DATAFRAME_IO_METHODS:
            raise CodeValidationError(f"Forbidden DataFrame export call: {qualified_name}")

        if (
            qualified_name.startswith("df.")
            and call_name in FORBIDDEN_FULL_DATA_EXTRACTION_METHODS
        ):
            raise CodeValidationError(
                f"Forbidden full-data extraction call: {qualified_name}"
            )

    _validate_range_call(node, call_name)


def _validate_range_call(node: ast.Call, call_name: str | None) -> None:
    if call_name != "range":
        return

    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
            if abs(arg.value) > MAX_RANGE_LIMIT:
                raise CodeValidationError("range limit is too large")


def _validate_attributes(node: ast.AST) -> None:
    if not isinstance(node, ast.Attribute):
        return

    if node.attr in FORBIDDEN_ATTRIBUTE_NAMES:
        raise CodeValidationError(f"Forbidden attribute access: {node.attr}")

    if node.attr in FORBIDDEN_DATAFRAME_IO_METHODS:
        raise CodeValidationError(f"Forbidden DataFrame I/O method: {node.attr}")

    if node.attr in FORBIDDEN_PANDAS_IO_FUNCTIONS:
        raise CodeValidationError(f"Forbidden pandas I/O function: {node.attr}")

    if node.attr in FORBIDDEN_FULL_DATA_ATTRIBUTES:
        raise CodeValidationError(f"Forbidden full-data attribute: {node.attr}")


def _validate_names(node: ast.AST) -> None:
    if not isinstance(node, ast.Name):
        return

    if node.id.startswith("__") and node.id.endswith("__"):
        raise CodeValidationError(f"Forbidden dunder name: {node.id}")


def _validate_import_root(root: str) -> None:
    if root in FORBIDDEN_IMPORT_ROOTS:
        raise CodeValidationError(f"Forbidden import: {root}")

    if root not in ALLOWED_IMPORT_ROOTS:
        raise CodeValidationError(f"Import not allowed: {root}")


def _validate_dataframe_column_usage(tree: ast.AST, approved_columns: set[str]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            _validate_df_subscript(node, approved_columns)

        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "df":
                if node.attr in FORBIDDEN_DF_ATTRIBUTES:
                    raise CodeValidationError(f"Direct df.{node.attr} access is not allowed")


def _validate_df_subscript(node: ast.Subscript, approved_columns: set[str]) -> None:
    if not isinstance(node.value, ast.Name):
        return

    if node.value.id != "df":
        return

    used_columns = _extract_df_subscript_columns(node.slice)

    if not used_columns:
        raise CodeValidationError(
            "Dynamic df column access is not allowed. Use explicit approved column names."
        )

    for column in used_columns:
        if column not in approved_columns:
            raise CodeValidationError(f"Column not approved: {column}")


def _extract_df_subscript_columns(slice_node: ast.AST) -> set[str]:
    columns: set[str] = set()

    if isinstance(slice_node, ast.Constant):
        if isinstance(slice_node.value, str):
            columns.add(slice_node.value)

    elif isinstance(slice_node, ast.List):
        for item in slice_node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                columns.add(item.value)

    elif isinstance(slice_node, ast.Tuple):
        for item in slice_node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                columns.add(item.value)

    return columns


def _root_module_name(module_name: str | None) -> str:
    if not module_name:
        return ""

    return module_name.split(".")[0].strip()


def _get_call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def _get_qualified_call_name(node: ast.Call) -> str | None:
    parts: list[str] = []
    current: ast.AST = node.func

    while isinstance(current, ast.Attribute):
        parts.insert(0, current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.insert(0, current.id)
        return ".".join(parts)

    return None


def _iter_assigned_names(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Name):
        yield node.id

    elif isinstance(node, (ast.Tuple, ast.List)):
        for item in node.elts:
            yield from _iter_assigned_names(item)