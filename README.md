# ai capex tracker

quarterly capital spending (capex) for the hyperscalers building ai infrastructure:
microsoft, alphabet, amazon, meta, oracle. built from sec edgar xbrl filings.

## pipeline

| layer | where | what |
|---|---|---|
| raw | `data/raw/*.json` | companyfacts json exactly as the sec returns it |
| bronze | `bronze_capex_facts` | every capex fact as filed, duplicates and all |
| silver | `sql/01_silver_capex_facts.sql` | fiscal year to date values, tags reconciled, restatements deduped |
| gold | `sql/02_gold_quarterly_capex.sql` | quarterly capex from ytd deltas, ttm, yoy, calendar alignment |
| checks | `sql/03_checks.sql` | each query returns bad rows, empty means pass |
| publish | `publish/google_sheet.py` | gold to a google sheet, which tableau public refreshes daily |

the same sql runs in two places: duckdb locally (`build.py`) and a databricks sql warehouse
against delta tables in `workspace.ai_capex` (`run_databricks.py`).

## schedule

`.github/workflows/refresh.yml` runs weekly on github actions: pull sec, upload bronze to a
databricks volume, rebuild silver and gold, run the checks, publish the sheet, and commit
the gold csv to the `data` branch when it changed (`main` only takes pull requests).
`data/gold/quarterly_capex.csv` on `main` is a seed copy. databricks free edition can't reach
data.sec.gov, so the fetch happens in actions.

| name | kind | value |
|---|---|---|
| `SEC_USER_AGENT` | variable | `ai-capex-tracker <contact email>` |
| `DATABRICKS_HOST` | variable | workspace url |
| `DATABRICKS_WAREHOUSE_ID` | variable | sql warehouse id |
| `GOOGLE_SHEET_ID` | variable | id from the sheet url |
| `DATABRICKS_CLIENT_ID` | secret | service principal oauth client id |
| `DATABRICKS_CLIENT_SECRET` | secret | service principal oauth secret |

google auth is keyless: the workflow's oidc token is exchanged for short lived credentials on
the `capex-sheet-writer` service account (workload identity federation), limited to this repo.

## run locally

```bash
uv run ingest/pull_sec.py
```

set `SEC_USER_AGENT="ai-capex-tracker you@example.com"` first, the sec rejects requests
without a contact email.

```bash
uv run build.py
```

writes `data/capex.duckdb` and `data/gold/quarterly_capex.csv`, exits non zero if a check fails.

```bash
DATABRICKS_CONFIG_PROFILE=capex DATABRICKS_WAREHOUSE_ID=<id> uv run run_databricks.py
```

## data notes

- capex is `PaymentsToAcquirePropertyPlantAndEquipment`, except amazon, which moved to
  `PaymentsToAcquireProductiveAssets` in 2017 and restated earlier years on the new tag.
  silver keeps whichever value the most recent filing reported.
- cash flow statements are fiscal year to date. a quarter is ytd minus the prior quarter's ytd
  in the same fiscal year, and Q4 is the 10-K annual value minus Q3 ytd.
- fiscal years differ (microsoft ends june, oracle ends may). each quarter is also mapped to
  the calendar quarter holding its midpoint so companies line up on one axis.
- source: sec edgar companyfacts api, `data.sec.gov/api/xbrl/companyfacts`.
