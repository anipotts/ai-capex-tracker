"""publish the gold csv to a google sheet, the one source tableau public refreshes on its own.

tab `quarterly_capex` gets the whole gold table, tab `meta` gets the refresh time and source,
so the dashboard can show when it last updated.

env: GOOGLE_SERVICE_ACCOUNT_JSON (the key file contents, a github secret) and
GOOGLE_SHEET_ID (from the sheet url, not secret). the sheet must be shared with the
service account's email as an editor.

usage: uv run publish/google_sheet.py
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import gspread

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold" / "quarterly_capex.csv"


def tab(sheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title, rows=1, cols=1)


def main() -> None:
    client = gspread.service_account_from_dict(json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]))
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])

    with open(GOLD, newline="") as f:
        rows = list(csv.reader(f))

    data = tab(sheet, "quarterly_capex")
    data.clear()
    # USER_ENTERED lets sheets parse numbers and dates, so tableau sees real types, not text
    data.update(rows, value_input_option="USER_ENTERED")

    meta = tab(sheet, "meta")
    meta.clear()
    meta.update([
        ["refreshed_at_utc", "source"],
        [datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "sec edgar xbrl companyfacts api"],
    ], value_input_option="USER_ENTERED")
    print(f"published {len(rows) - 1} rows to google sheet")


if __name__ == "__main__":
    main()
