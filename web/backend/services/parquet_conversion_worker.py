"""Isolated CSV-to-Parquet converter. Input is trusted parent JSON only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import duckdb
import polars as pl


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    request = json.loads(sys.stdin.buffer.read(8193))
    source_fd = int(request["source_fd"])
    output = Path(str(request["output_path"]))
    scratch = Path(str(request["scratch_path"]))
    declared_rows = request.get("declared_rows")
    if source_fd < 3 or not output.is_absolute() or not scratch.is_absolute():
        raise ValueError("invalid conversion request")
    source = f"/proc/self/fd/{source_fd}"
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("SET memory_limit='256MiB'")
        connection.execute("SET max_temp_directory_size='512MiB'")
        connection.execute(f"SET temp_directory={sql_literal(str(scratch))}")
        connection.execute("SET threads=1")
        connection.execute("SET preserve_insertion_order=true")
        connection.execute(
            f"SET allowed_paths=[{sql_literal(source)},{sql_literal(str(output))}]"
        )
        connection.execute(
            f"SET allowed_directories=[{sql_literal(str(scratch))},{sql_literal(str(output.parent))}]"
        )
        connection.execute("SET autoinstall_known_extensions=false")
        connection.execute("SET autoload_known_extensions=false")
        connection.execute("SET allow_community_extensions=false")
        connection.execute("SET enable_external_access=false")
        connection.execute("SET lock_configuration=true")
        connection.execute(
            "COPY (SELECT * FROM read_csv_auto(?, header=true, sample_size=-1, "
            "strict_mode=true)) TO " + sql_literal(str(output))
            + " (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)",
            [source],
        )
        rows = int(connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(output)],
        ).fetchone()[0])
        if isinstance(declared_rows, int) and rows != declared_rows:
            raise ValueError("parquet row count mismatch")
    finally:
        connection.close()

    csv_schema = dict(pl.scan_csv(
        source, infer_schema_length=10_000, try_parse_dates=False,
        low_memory=True, glob=False, raise_if_empty=True,
    ).collect_schema())
    parquet_schema = dict(pl.scan_parquet(
        output, glob=False, low_memory=True,
    ).collect_schema())
    compatible = [
        name for name, dtype in csv_schema.items()
        if name in parquet_schema and str(dtype) == str(parquet_schema[name])
    ]
    numeric_types = {
        pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Int128,
        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        pl.Float32, pl.Float64, pl.Decimal,
    }
    numeric = [
        name for name in compatible if csv_schema[name].base_type() in numeric_types
    ]
    sys.stdout.write(json.dumps({
        "ok": True, "size_bytes": output.stat().st_size, "row_count": rows,
        "polars_compatible_columns": compatible, "polars_numeric_columns": numeric,
    }, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write('{"ok":false}')
        raise SystemExit(2)
