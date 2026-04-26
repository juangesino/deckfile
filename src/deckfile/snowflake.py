"""Snowflake data source for deckfile.

Executes a SQL query against a Snowflake warehouse via the official
``snowflake-connector-python`` driver and returns the result as CSV
text so it can flow through the existing ``load_data()`` pipeline.

Credentials are read from ``SNOWFLAKE_*`` environment variables.
Two auth modes are supported:

* **Key-pair** (preferred for production / CI):
  ``SNOWFLAKE_PRIVATE_KEY`` holds a PEM-encoded RSA key.  Literal
  ``\\n`` sequences are converted to real newlines so the key can be
  stored on a single line in ``.env`` files.  Optional
  ``SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`` decrypts an encrypted key.

* **Password**:
  ``SNOWFLAKE_PASSWORD`` for basic auth.

Key-pair takes precedence when both are present.

Connection parameters (account, warehouse, database, schema, role)
may also be supplied per-source in YAML — those override env vars.
User and credentials are env-only.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any


_REQUIRED_ENV = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER")

# Connection params that can be overridden per-source in YAML.
_OVERRIDABLE = ("account", "warehouse", "database", "schema", "role")


def _load_private_key(pem: str, passphrase: str | None) -> bytes:
    """Convert a PEM-encoded RSA key into the DER bytes the connector wants.

    ``snowflake-connector-python`` declares ``cryptography`` as a transitive
    dep, so installing the ``snowflake`` extra is enough.
    """
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        raise ImportError(
            "cryptography is required for snowflake key-pair auth. "
            "Install it with:  pip install deckfile[snowflake]"
        )

    pem_bytes = pem.replace("\\n", "\n").encode("utf-8")
    pwd_bytes = passphrase.encode("utf-8") if passphrase else None

    key = serialization.load_pem_private_key(
        pem_bytes, password=pwd_bytes, backend=default_backend()
    )
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _build_connect_kwargs(source: dict) -> dict:
    """Build kwargs for snowflake.connector.connect() from env + source spec."""
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing env vars for snowflake source: {', '.join(missing)}"
        )

    private_key_pem = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
    password = os.environ.get("SNOWFLAKE_PASSWORD")

    if not private_key_pem and not password:
        raise EnvironmentError(
            "Snowflake source requires either SNOWFLAKE_PRIVATE_KEY "
            "(key-pair auth) or SNOWFLAKE_PASSWORD (password auth)."
        )

    kwargs: dict[str, Any] = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
    }

    if private_key_pem:
        passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
        kwargs["private_key"] = _load_private_key(private_key_pem, passphrase)
    else:
        kwargs["password"] = password

    # Optional connection params: env first, then YAML override.
    for key in ("warehouse", "database", "schema", "role"):
        env_val = os.environ.get(f"SNOWFLAKE_{key.upper()}")
        if env_val:
            kwargs[key] = env_val

    for key in _OVERRIDABLE:
        if key in source:
            kwargs[key] = source[key]

    return kwargs


def _coerce(value: Any) -> str:
    """Convert a Snowflake cell value to a string suitable for CSV output.

    The downstream pipeline expects CSV-style strings (DictReader output),
    so dates/datetimes/decimals must serialize without surprises.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def run_snowflake_query(query: str, source: dict) -> str:
    """Execute *query* against Snowflake and return results as CSV text.

    Parameters
    ----------
    query:
        SQL to run on the Snowflake warehouse.
    source:
        The full source spec; may carry connection overrides
        (``account``, ``warehouse``, ``database``, ``schema``, ``role``).

    Notes
    -----
    Snowflake uppercases unquoted identifiers, so ``SELECT mrr`` yields a
    column named ``MRR``. Reference that exact name in chart ``columns:``,
    or alias with quoted identifiers (``SELECT mrr AS "mrr"``).
    """
    try:
        import snowflake.connector
    except ImportError:
        raise ImportError(
            "snowflake-connector-python is required for snowflake sources. "
            "Install it with:  pip install deckfile[snowflake]"
        )

    connect_kwargs = _build_connect_kwargs(source)

    conn = snowflake.connector.connect(**connect_kwargs)
    try:
        cur = conn.cursor()
        try:
            cur.execute(query)
            columns = [c[0] for c in cur.description]
            rows = cur.fetchall()
        finally:
            cur.close()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_coerce(v) for v in row])
    return output.getvalue()
