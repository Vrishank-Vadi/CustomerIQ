# Verification record

Verified locally on **October 12, 2026 (America/Chicago)** using Python 3.12.14 on Windows, Streamlit 1.65.0, Pandas 2.3.3, NumPy 2.2.6, Plotly 6.9.0, and Microsoft Edge through Playwright 1.63.0.

## Automated suite

```text
python -m pytest -q
57 passed
```

Coverage includes identity resolution (including transitive matches), latest-snapshot tie-breaking, opt-out precedence, malformed CSVs, numerical limits, rejected dates, empty datasets, revenue metrics, all six segment boundaries, RFM scores, campaign rules, leap years and year boundaries, personalized templates, batch exports, and Streamlit navigation and filter interactions.

## Running application

Started the real Streamlit server on `127.0.0.1:8501` and exercised it with a browser, in addition to Streamlit's simulated AppTest checks:

- Loaded the Overview dashboard and all three interactive charts.
- Selected the Quality challenge and inspected duplicate records.
- Uploaded `customers_dirty.csv` through the file input.
- Downloaded and parsed the cleaned CSV: **600 rows**, **$799,415.00** lifetime revenue.
- Exported all **six customer segments** and checked the customer count.
- Switched among Welcome, Anniversary, and Win-back; verified personalized subjects and downloaded each campaign's drafts.
- Uploaded an invalid schema and confirmed a readable error without a crash.
- Uploaded the empty import template and confirmed the zero-row state.
- Loaded a **390 × 844** mobile viewport; captured the responsive layout.
- Observed **no browser JavaScript errors** during the smoke workflow.

Screenshots in `docs/screenshots/` are actual captures of the running application. They are not design mockups. Desktop captures use a 1600 × 1500 viewport.

## Batch pipeline

```bash
python -m customeriq --input data/customers_dirty.csv --as-of 2026-10-12 --output exports/demo
```

Observed report:

```json
{
  "as_of": "2026-10-12",
  "input_rows": 630,
  "clean_customers": 600,
  "duplicates_removed": 24,
  "quarantined_rows": 6,
  "lifetime_revenue_usd": 799415.0,
  "campaign_drafts": {
    "Welcome": 5,
    "Anniversary": 42,
    "Win-back": 319
  },
  "delivery_mode": "draft_only"
}
```

## Reproduction and limits

Run `python scripts/browser_smoke.py --channel msedge` against a separately running server, or install Playwright Chromium and omit `--channel`. Run tests from the repository root. The tests use deterministic synthetic fixtures; changing the bundled generator inputs changes the expected totals.

GitHub Actions is configured to run the automated suite on Python 3.12 and 3.13 on Ubuntu. Its live status is available from the README badge. Local browser checks are separate from CI and require a running app and browser installation. No email was sent. Publication on GitHub provides the source repository; it does not deploy a hosted Streamlit service.
