"""DuckDB query engine for source-level SQL transformations."""

from __future__ import annotations

import os
import re
import tempfile
from typing import Dict, List

# Matches ref(name) — with optional whitespace and optional quotes around name.
_REF_RE = re.compile(r"\bref\(\s*['\"]?(\w+)['\"]?\s*\)")


def parse_refs(sql: str) -> list[str]:
    """Extract source names from ref() calls in a SQL query."""
    return _REF_RE.findall(sql)


def run_dep_query(sql: str, upstream: Dict[str, str]) -> List[dict]:
    """Run a SQL query where ref(name) calls resolve to upstream sources.

    Parameters
    ----------
    sql : str
        SQL query containing ref(name) calls.
    upstream : dict[str, str]
        Mapping of source_name -> raw CSV text for each referenced source.

    Returns
    -------
    list[dict]
        Query results as a list of row dicts (values stringified).
    """
    import duckdb

    tmp_paths: list[str] = []
    try:
        conn = duckdb.connect()
        resolved_sql = sql

        for name, raw_csv in upstream.items():
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                f.write(raw_csv)
                tmp_paths.append(f.name)

            conn.execute(
                f"CREATE VIEW \"{name}\" AS SELECT * FROM read_csv('{f.name}', header=true, null_padding=true, ignore_errors=true)"
            )
            resolved_sql = _REF_RE.sub(
                lambda m: f'"{m.group(1)}"' if m.group(1) == name else m.group(0),
                resolved_sql,
            )

        try:
            result = conn.execute(resolved_sql)
        except duckdb.Error as e:
            raise ValueError(f"SQL error in dep source query: {e}") from e
        columns = [desc[0] for desc in result.description]
        return [
            {col: str(val) for col, val in zip(columns, row)}
            for row in result.fetchall()
        ]
    finally:
        for p in tmp_paths:
            os.unlink(p)


def run_query(raw_csv: str, sql: str) -> List[dict]:
    """Run a SQL query against CSV data using DuckDB.

    The CSV data is exposed as a table called ``source``.

    Parameters
    ----------
    raw_csv : str
        Raw CSV text (with header row).
    sql : str
        SQL query to execute.  Reference the data as ``source``.

    Returns
    -------
    list[dict]
        Query results as a list of row dicts.
    """
    import duckdb

    tmp_path = None
    try:
        # Write CSV to a temp file so DuckDB can read it with type inference.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(raw_csv)
            tmp_path = f.name

        conn = duckdb.connect()
        conn.execute(
            f"CREATE VIEW source AS SELECT * FROM read_csv('{tmp_path}', header=true, null_padding=true, ignore_errors=true)"
        )
        try:
            result = conn.execute(sql)
        except duckdb.Error as e:
            raise ValueError(f"SQL error in source query: {e}") from e
        columns = [desc[0] for desc in result.description]
        # Stringify values so downstream code (which expects csv.DictReader
        # output) can do string slicing on dates and float() on numbers.
        return [
            {col: str(val) for col, val in zip(columns, row)}
            for row in result.fetchall()
        ]
    finally:
        if tmp_path:
            os.unlink(tmp_path)
