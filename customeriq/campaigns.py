"""Consent-aware campaign eligibility and local email draft generation."""

import calendar
from pathlib import Path
from string import Template

import pandas as pd

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
CAMPAIGNS = ["Welcome", "Anniversary", "Win-back"]


def anniversary_date(join_date, as_of):
    """Next anniversary on or after as_of; Feb 29 becomes Feb 28 in non-leap years."""
    joined, today = pd.Timestamp(join_date), pd.Timestamp(as_of).normalize()
    year = max(today.year, joined.year + 1)
    day = min(joined.day, calendar.monthrange(year, joined.month)[1])
    candidate = pd.Timestamp(year, joined.month, day)
    if candidate < today:
        year += 1
        candidate = pd.Timestamp(year, joined.month, min(joined.day, calendar.monthrange(year, joined.month)[1]))
    return candidate


def eligible_customers(
    df: pd.DataFrame, campaign: str, as_of, welcome_days=7, anniversary_days=30, winback_days=90
) -> pd.DataFrame:
    today = pd.Timestamp(as_of).normalize()
    out = df.loc[df["marketing_opt_in"]].copy()
    tenure = (today - out["join_date"]).dt.days
    if campaign == "Welcome":
        mask = tenure.between(0, welcome_days)
    elif campaign == "Anniversary":
        out["anniversary_date"] = pd.to_datetime(out["join_date"].map(lambda d: anniversary_date(d, today)))
        out["anniversary_years"] = out["anniversary_date"].dt.year - out["join_date"].dt.year
        mask = (out["anniversary_date"] - today).dt.days.between(0, anniversary_days)
    elif campaign == "Win-back":
        mask = out["last_purchase_date"].notna() & (today - out["last_purchase_date"]).dt.days.ge(winback_days)
    else:
        raise ValueError(f"Unknown campaign: {campaign}")
    return out.loc[mask].reset_index(drop=True)


def render_email(customer, campaign: str) -> dict:
    if campaign not in CAMPAIGNS:
        raise ValueError(f"Unknown campaign: {campaign}")
    slug = campaign.lower().replace("-", "_")
    values = {
        "first_name": customer["first_name"],
        "membership_tier": customer["membership_tier"],
        "anniversary_years": int(customer.get("anniversary_years", 1)),
        "brand": "CustomerIQ Demo",
    }
    content = Template((TEMPLATES / f"{slug}.txt").read_text(encoding="utf-8")).substitute(values)
    subject, body = content.split("\n\n", 1)
    return {
        "customer_id": customer["customer_id"],
        "to": customer["email"],
        "campaign": campaign,
        "subject": subject.removeprefix("Subject: "),
        "body": body.strip(),
    }


def campaign_export(eligible: pd.DataFrame, campaign: str) -> pd.DataFrame:
    return pd.DataFrame(
        [render_email(row, campaign) for _, row in eligible.iterrows()],
        columns=["customer_id", "to", "campaign", "subject", "body"],
    )
