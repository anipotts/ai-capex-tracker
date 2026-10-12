# ai-capex-tracker

Quarterly capex for the AI hyperscalers (Microsoft, Alphabet, Amazon, Meta, Oracle), built from SEC EDGAR XBRL filings and published to a Tableau Public dashboard.

## Stack
- Python 3.12 with `uv` (`pyproject.toml`, `uv.lock`); DuckDB locally, Databricks SQL warehouse in CI.
- Pipeline: `ingest/` → `data/raw` → bronze → `sql/01_silver_*` → `sql/02_gold_*` → `sql/03_checks.sql` → `publish/google_sheet.py`.

## Commands
- Local build: `uv run python build.py`
- Databricks run: `uv run python run_databricks.py`

## Rules
- The same SQL must run in DuckDB and Databricks; test both when changing `sql/`.
- Every query in `sql/03_checks.sql` returns bad rows; empty output means pass. Keep it passing.
- `.github/workflows/refresh.yml` runs weekly and commits gold CSV to the `data` branch. `main` only takes pull requests.
- Credentials live in GitHub Actions variables and secrets (see README). Never commit them.
