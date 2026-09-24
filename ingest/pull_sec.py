"""pull capex facts from the sec edgar companyfacts api.

writes the raw json per company (the as-landed copy) and one flat csv of every
capex fact as filed (bronze). no cleaning happens here: duplicates, amendments,
trailing twelve month columns and renamed tags all stay in, sql handles them.

usage: SEC_USER_AGENT="ai-capex-tracker you@example.com" uv run ingest/pull_sec.py
"""

import csv
import json
import os
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

COMPANIES = {
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "ORCL": "0001341439",
    # NVDA 0001045810 is left out: companyfacts has no capex fact for its FY2020, FY2021
    # or FY2023 Q1/Q2 under any tag, so its quarterly series can't be rebuilt from this api.
}

# amazon moved in 2017 (nvidia in 2020) from the first tag to the second.
CAPEX_CONCEPTS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]

URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DATA = Path(__file__).resolve().parent.parent / "data"
FIELDS = [
    "ticker", "cik", "concept", "start_date", "end_date", "duration_days",
    "value_usd", "fiscal_year", "fiscal_period", "form", "filed", "accession", "frame",
]


def fetch(cik: str, user_agent: str) -> dict:
    req = urllib.request.Request(URL.format(cik=cik), headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def flatten(ticker: str, doc: dict) -> list[dict]:
    rows = []
    us_gaap = doc["facts"].get("us-gaap", {})
    for concept in CAPEX_CONCEPTS:
        for fact in us_gaap.get(concept, {}).get("units", {}).get("USD", []):
            if "start" not in fact:
                continue  # capex is a flow, every real fact has a period start
            start, end = date.fromisoformat(fact["start"]), date.fromisoformat(fact["end"])
            rows.append({
                "ticker": ticker,
                "cik": doc["cik"],
                "concept": concept,
                "start_date": fact["start"],
                "end_date": fact["end"],
                "duration_days": (end - start).days,
                "value_usd": fact["val"],
                # fy and fp describe the filing the fact came from, not the fact's own period
                "fiscal_year": fact.get("fy"),
                "fiscal_period": fact.get("fp"),
                "form": fact["form"],
                "filed": fact["filed"],
                "accession": fact["accn"],
                "frame": fact.get("frame", ""),
            })
    return rows


def main() -> None:
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent or "@" not in user_agent:
        sys.exit("set SEC_USER_AGENT to 'name contact@email', sec rejects requests without one")

    (DATA / "raw").mkdir(parents=True, exist_ok=True)
    (DATA / "bronze").mkdir(parents=True, exist_ok=True)

    rows = []
    for ticker, cik in COMPANIES.items():
        doc = fetch(cik, user_agent)
        (DATA / "raw" / f"{ticker}.json").write_text(json.dumps(doc))
        company_rows = flatten(ticker, doc)
        rows.extend(company_rows)
        print(f"{ticker}: {len(company_rows)} capex facts")
        time.sleep(0.2)  # sec allows 10 requests/sec, stay well under

    with open(DATA / "bronze" / "capex_facts.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to data/bronze/capex_facts.csv")


if __name__ == "__main__":
    main()
