"""Explainable segmentation and customer-snapshot revenue metrics."""

import numpy as np
import pandas as pd

from customeriq.data import TIERS

SEGMENTS = ["Champions", "New customers", "Loyal", "Active", "At risk", "Dormant"]
COLORS = {
    "Champions": "#0f766e",
    "New customers": "#50b7a6",
    "Loyal": "#5478ba",
    "Active": "#a1b6d9",
    "At risk": "#e8ad55",
    "Dormant": "#cc7372",
}


def segment_customers(df: pd.DataFrame, as_of) -> pd.DataFrame:
    out = df.copy()
    today = pd.Timestamp(as_of).normalize()
    out["tenure_days"] = (today - out["join_date"]).dt.days
    out["recency_days"] = (today - out["last_purchase_date"].fillna(out["join_date"])).dt.days
    r, f, m = out["recency_days"], out["purchase_count"], out["total_spend"]
    out["segment"] = np.select(
        [r.le(60) & m.ge(1000), out["tenure_days"].le(30), r.le(60) & f.ge(5), r.le(90), r.le(180)],
        SEGMENTS[:-1],
        default="Dormant",
    )
    out["r_score"] = np.select([r.le(30), r.le(60), r.le(90), r.le(180)], [5, 4, 3, 2], default=1)
    out["f_score"] = np.select([f.ge(15), f.ge(8), f.ge(4), f.ge(2)], [5, 4, 3, 2], default=1)
    out["m_score"] = np.select([m.ge(2000), m.ge(1000), m.ge(500), m.ge(100)], [5, 4, 3, 2], default=1)
    out["rfm_score"] = out["r_score"].astype(str) + out["f_score"].astype(str) + out["m_score"].astype(str)
    return out


def tier_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("membership_tier").agg(
        customers=("customer_id", "size"), revenue=("total_spend", "sum"), orders=("purchase_count", "sum")
    )
    grouped = grouped.reindex(TIERS, fill_value=0)
    grouped["revenue_per_customer"] = grouped["revenue"].div(grouped["customers"].replace(0, np.nan)).fillna(0)
    grouped["average_order_value"] = grouped["revenue"].div(grouped["orders"].replace(0, np.nan)).fillna(0)
    total = grouped["revenue"].sum()
    grouped["revenue_share"] = grouped["revenue"] / total if total else 0.0
    return grouped.reset_index()
