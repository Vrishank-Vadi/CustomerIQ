"""Generate repeatable synthetic snapshots; no personal data or external sources."""

import argparse
from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd

DEMO_DATE = date(2026, 10, 12)


def generate_customers(count=600, seed=42, as_of=DEMO_DATE):
    rng = random.Random(seed)
    rows = []
    for i in range(1, count + 1):
        tenure = rng.randint(1, 1095)
        if i % 25 == 0:
            tenure = rng.randint(0, 7)
        if i % 30 == 0:
            tenure = 365 - rng.randint(0, 29)
        joined = as_of - timedelta(days=tenure)
        recency = rng.randint(0, min(tenure, 340))
        orders = rng.randint(0, 28) if tenure > 30 else rng.randint(0, 2)
        tier = rng.choices(["Bronze", "Silver", "Gold", "Platinum"], [40, 30, 20, 10])[0]
        spend = round(
            orders * rng.uniform(25, 180) * {"Bronze": 0.65, "Silver": 1, "Gold": 1.4, "Platinum": 1.9}[tier], 2
        )
        rows.append(
            {
                "customer_id": f"CQ{i:05d}",
                "first_name": f"Member{i:03d}",
                "last_name": "Example",
                "email": f"member{i:05d}@example.com",
                "membership_tier": tier,
                "join_date": joined.isoformat(),
                "last_purchase_date": (as_of - timedelta(days=recency)).isoformat() if orders else "",
                "total_spend": spend,
                "purchase_count": orders,
                "marketing_opt_in": i % 5 != 0,
                "updated_at": as_of.isoformat(),
                "country": rng.choice(["United States", "Canada", "United Kingdom", "Australia", "Germany"]),
            }
        )
    # Make welcome examples consented and give the demo at least one of each segment.
    for i in [24, 49, 74]:
        if i < count:
            rows[i]["marketing_opt_in"] = True
    return pd.DataFrame(rows)


def dirty_sample(clean):
    dirty = clean.copy()
    for i in range(min(35, len(dirty))):
        dirty.loc[i, "email"] = " " + dirty.loc[i, "email"].upper() + " "
        dirty.loc[i, "membership_tier"] = dirty.loc[i, "membership_tier"].lower()
    duplicates = clean.iloc[:24].copy()
    duplicates["total_spend"] = (duplicates["total_spend"] * 0.8).round(2)
    duplicates["updated_at"] = duplicates["last_purchase_date"].where(
        duplicates["last_purchase_date"].ne(""), duplicates["join_date"]
    )
    invalid = clean.iloc[40:46].astype(object).copy()
    invalid.loc[invalid.index[0], "email"] = "missing-at-sign"
    invalid.loc[invalid.index[1], "total_spend"] = -40
    invalid.loc[invalid.index[2], "membership_tier"] = "Diamond"
    invalid.loc[invalid.index[3], "join_date"] = "not-a-date"
    invalid.loc[invalid.index[4], "purchase_count"] = 2.5
    invalid.loc[invalid.index[5], "marketing_opt_in"] = "maybe"
    # Originals come last to win a date-only updated_at tie with an older snapshot.
    return pd.concat([duplicates, dirty, invalid], ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEMO_DATE)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    if args.count < 50:
        parser.error("--count must be at least 50 for the quality-challenge dataset")
    args.output.mkdir(parents=True, exist_ok=True)
    clean = generate_customers(args.count, args.seed, args.as_of)
    clean.to_csv(args.output / "customers_clean.csv", index=False)
    dirty_sample(clean).to_csv(args.output / "customers_dirty.csv", index=False)
    clean.head(0).to_csv(args.output / "import_template.csv", index=False)
    print(f"Created {len(clean)} synthetic customers and a {len(clean) + 30}-row quality challenge.")


if __name__ == "__main__":
    main()
