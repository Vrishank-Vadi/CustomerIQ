"""Headless automation: clean a CSV and generate all three campaign draft files."""

import argparse
from datetime import date
import json
from pathlib import Path

from customeriq.analytics import segment_customers, tier_summary
from customeriq.campaigns import CAMPAIGNS, campaign_export, eligible_customers
from customeriq.data import clean_customers, export_csv, read_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Customer snapshot CSV")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True, help="Analysis date: YYYY-MM-DD")
    parser.add_argument("--output", type=Path, required=True, help="Directory for CSV drafts and a JSON audit report")
    args = parser.parse_args(argv)
    try:
        result = clean_customers(read_csv(args.input.read_bytes()), args.as_of)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    enriched = segment_customers(result.clean, args.as_of)
    args.output.mkdir(parents=True, exist_ok=True)
    files = {
        "clean_customers": result.clean.drop(columns="source_row"),
        "duplicate_audit": result.duplicates,
        "quarantine": result.rejected,
        "segments": enriched,
        "tier_revenue": tier_summary(enriched),
    }
    audiences = {}
    for campaign in CAMPAIGNS:
        eligible = eligible_customers(enriched, campaign, args.as_of)
        audiences[campaign] = len(eligible)
        files[campaign.lower().replace("-", "_") + "_drafts"] = campaign_export(eligible, campaign)
    for name, frame in files.items():
        (args.output / f"{name}.csv").write_bytes(export_csv(frame))
    report = {
        "as_of": args.as_of.isoformat(),
        "input_rows": result.input_rows,
        "clean_customers": len(result.clean),
        "duplicates_removed": result.removed_duplicates,
        "quarantined_rows": len(result.rejected),
        "lifetime_revenue_usd": round(float(result.clean.total_spend.sum()), 2),
        "campaign_drafts": audiences,
        "delivery_mode": "draft_only",
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
