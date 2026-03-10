"""Google Sheets data source for deckfile.

Fetches worksheet data as CSV text via gspread + google-auth,
using service-account credentials from GOOGLE_AUTH_* env vars.
"""

from __future__ import annotations

import csv
import io
import os
import re


def _get_credentials():
    """Build service-account Credentials from GOOGLE_AUTH_* env vars.

    Required env vars:
        GOOGLE_AUTH_PRIVATE_KEY_ID
        GOOGLE_AUTH_PRIVATE_KEY     (PEM, with literal \\n replaced at load)
        GOOGLE_AUTH_EMAIL
        GOOGLE_AUTH_CLIENT_ID

    Optional env vars (sensible defaults provided):
        GOOGLE_AUTH_TYPE            (default: "service_account")
        GOOGLE_AUTH_PROJECT         (default: derived from client email)
        GOOGLE_AUTH_URI
        GOOGLE_AUTH_TOKEN_URI
        GOOGLE_AUTH_PROVIDER_CERT_URL
        GOOGLE_AUTH_CLIENT_CERT_URL
    """
    try:
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "google-auth is required for gsheet sources. "
            "Install it with:  pip install deckfile[gsheets]"
        )

    required = [
        "GOOGLE_AUTH_PRIVATE_KEY_ID",
        "GOOGLE_AUTH_PRIVATE_KEY",
        "GOOGLE_AUTH_EMAIL",
        "GOOGLE_AUTH_CLIENT_ID",
    ]

    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing env vars for gsheet credentials: {', '.join(missing)}"
        )

    client_email = os.environ["GOOGLE_AUTH_EMAIL"]

    info = {
        "type": os.environ.get("GOOGLE_AUTH_TYPE", "service_account"),
        "project_id": os.environ.get(
            "GOOGLE_AUTH_PROJECT",
            client_email.split("@")[-1].split(".")[0] if "@" in client_email else "",
        ),
        "private_key_id": os.environ["GOOGLE_AUTH_PRIVATE_KEY_ID"],
        "private_key": os.environ["GOOGLE_AUTH_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": client_email,
        "client_id": os.environ["GOOGLE_AUTH_CLIENT_ID"],
        "auth_uri": os.environ.get(
            "GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"
        ),
        "token_uri": os.environ.get(
            "GOOGLE_AUTH_TOKEN_URI", "https://oauth2.googleapis.com/token"
        ),
        "auth_provider_x509_cert_url": os.environ.get(
            "GOOGLE_AUTH_PROVIDER_CERT_URL",
            "https://www.googleapis.com/oauth2/v1/certs",
        ),
        "client_x509_cert_url": os.environ.get(
            "GOOGLE_AUTH_CLIENT_CERT_URL",
            f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}",
        ),
    }

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    return Credentials.from_service_account_info(info, scopes=scopes)


def _rows_to_csv(rows: list[list[str]]) -> str:
    """Convert a list-of-lists (from gspread .get()) to CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)
    return output.getvalue()


def fetch_gsheet_csv(url: str, range: str | None = None, timeout: int | float = 30) -> str:
    """Open a Google Sheet by URL and return its contents as CSV text.

    Parameters
    ----------
    url:
        Full Google Sheets URL (the spreadsheet ID is extracted via regex).
    range:
        Optional worksheet/tab name, A1 cell range, or both in
        ``'Sheet Name'!A1:B10`` notation.  Defaults to the first sheet.

    Returns
    -------
    CSV text ready for the existing ``load_data()`` pipeline.
    """
    try:
        import gspread
    except ImportError:
        raise ImportError(
            "gspread is required for gsheet sources. "
            "Install it with:  pip install deckfile[gsheets]"
        )

    # Extract spreadsheet ID from URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not extract spreadsheet ID from URL: {url}")

    spreadsheet_id = match.group(1)
    creds = _get_credentials()
    client = gspread.authorize(creds)
    client.set_timeout(timeout)
    spreadsheet = client.open_by_key(spreadsheet_id)

    if not range:
        # No range — export entire first sheet
        return spreadsheet.sheet1.export(
            format=gspread.utils.ExportFormat.CSV
        ).decode("utf-8")

    # Parse range: could be "Sheet", "A1:B10", or "'Sheet'!A1:B10"
    sheet_name = None
    cell_range = None

    if "!" in range:
        sheet_name, cell_range = range.rsplit("!", 1)
        # Strip surrounding quotes from sheet name
        sheet_name = sheet_name.strip("'\"")
    elif re.match(r"^[A-Z]+\d+", range):
        # Looks like a cell reference (e.g. "A1:B10")
        cell_range = range
    else:
        # Just a sheet/tab name
        sheet_name = range

    worksheet = spreadsheet.worksheet(sheet_name) if sheet_name else spreadsheet.sheet1

    if cell_range:
        rows = worksheet.get(cell_range)
        return _rows_to_csv(rows)

    return worksheet.export(
        format=gspread.utils.ExportFormat.CSV
    ).decode("utf-8")
