"""build the local lakehouse in duckdb: bronze csv -> silver -> gold, then run checks.

usage: uv run build.py   (after ingest/pull_sec.py has written data/bronze)
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SQL = ROOT / "sql"


def main() -> None:
    con = duckdb.connect(str(DATA / "capex.duckdb"))
    con.execute(
        "create or replace table bronze_capex_facts as select * from read_csv(?, header = true)",
        [str(DATA / "bronze" / "capex_facts.csv")],
    )

    con.execute((SQL / "01_silver_capex_facts.sql").read_text())
    con.execute((SQL / "02_gold_quarterly_capex.sql").read_text())

    failed = 0
    for check in (SQL / "03_checks.sql").read_text().split("-- ----"):
        name = next(l for l in check.splitlines() if l.startswith("-- check:"))[10:]
        rows = con.execute(check).fetchall()
        print(f"{'FAIL' if rows else 'ok  '} {name}")
        for row in rows[:10]:
            print(f"       {row}")
        failed += bool(rows)

    (DATA / "gold").mkdir(exist_ok=True)
    out = DATA / "gold" / "quarterly_capex.csv"
    con.execute(f"copy (select * from gold_quarterly_capex order by ticker, quarter_end) to '{out}' (header)")
    print(f"wrote {out.relative_to(ROOT)}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
