"""build the lakehouse on databricks: bronze csv -> delta bronze -> silver -> gold, then checks.

same sql files as build.py, run on a databricks sql warehouse against workspace.ai_capex.
writes the gold table back out to data/gold/quarterly_capex.csv for the sheet publisher.

auth comes from the environment: a service principal in ci (DATABRICKS_HOST,
DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET) or a cli profile locally
(DATABRICKS_CONFIG_PROFILE=capex). DATABRICKS_WAREHOUSE_ID picks the warehouse.

usage: uv run run_databricks.py   (after ingest/pull_sec.py has written data/bronze)
"""

import csv
import os
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SQL = ROOT / "sql"
CATALOG, SCHEMA = "workspace", "ai_capex"
LANDING = f"/Volumes/{CATALOG}/{SCHEMA}/landing/capex_facts.csv"

w = WorkspaceClient()
WAREHOUSE = os.environ["DATABRICKS_WAREHOUSE_ID"]


def run(sql: str):
    """run one statement, wait for it, return (column names, rows)."""
    resp = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=WAREHOUSE, catalog=CATALOG, schema=SCHEMA, wait_timeout="50s"
    )
    # a cold serverless warehouse can take longer than the 50s inline wait
    while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(3)
        resp = w.statement_execution.get_statement(resp.statement_id)
    if resp.status.state != StatementState.SUCCEEDED:
        sys.exit(f"statement failed: {resp.status.error.message if resp.status.error else resp.status.state}")
    columns = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
    rows = resp.result.data_array if resp.result and resp.result.data_array else []
    return columns, rows


def main() -> None:
    with open(DATA / "bronze" / "capex_facts.csv", "rb") as f:
        w.files.upload(LANDING, f, overwrite=True)

    run(f"""
        create or replace table bronze_capex_facts as
        select * from read_files('{LANDING}', format => 'csv', header => true)
    """)
    run((SQL / "01_silver_capex_facts.sql").read_text())
    run((SQL / "02_gold_quarterly_capex.sql").read_text())

    failed = 0
    for check in (SQL / "03_checks.sql").read_text().split("-- ----"):
        name = next(l for l in check.splitlines() if l.startswith("-- check:"))[10:]
        _, rows = run(check)
        print(f"{'FAIL' if rows else 'ok  '} {name}")
        for row in rows[:10]:
            print(f"       {row}")
        failed += bool(rows)
    if failed:
        sys.exit(f"{failed} check(s) failed, not exporting gold")

    columns, rows = run("select * from gold_quarterly_capex order by ticker, quarter_end")
    (DATA / "gold").mkdir(parents=True, exist_ok=True)
    with open(DATA / "gold" / "quarterly_capex.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    print(f"wrote {len(rows)} gold rows to data/gold/quarterly_capex.csv")


if __name__ == "__main__":
    main()
