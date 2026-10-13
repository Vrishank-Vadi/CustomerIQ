import pandas as pd
import pytest

from customeriq.analytics import segment_customers, tier_summary
from customeriq.data import clean_customers

AS_OF = pd.Timestamp("2026-10-12")


@pytest.mark.parametrize(
    "recency,tenure,orders,spend,segment",
    [
        (60, 365, 8, 1000, "Champions"),
        (5, 30, 1, 80, "New customers"),
        (60, 365, 5, 500, "Loyal"),
        (90, 365, 2, 200, "Active"),
        (91, 365, 2, 200, "At risk"),
        (180, 365, 2, 200, "At risk"),
        (181, 365, 2, 200, "Dormant"),
    ],
)
def test_segment_boundaries(customer, recency, tenure, orders, spend, segment):
    row = dict(
        customer,
        join_date=(AS_OF - pd.Timedelta(days=tenure)).date().isoformat(),
        last_purchase_date=(AS_OF - pd.Timedelta(days=recency)).date().isoformat(),
        purchase_count=orders,
        total_spend=spend,
    )
    data = clean_customers(pd.DataFrame([row]), AS_OF).clean
    assert segment_customers(data, AS_OF).iloc[0].segment == segment


def test_rfm_boundaries_and_no_purchase_fallback(customer):
    a = dict(customer, purchase_count=15, total_spend=2000)
    b = dict(
        customer, customer_id="002", email="two@example.com", purchase_count=0, total_spend=0, last_purchase_date=""
    )
    data = segment_customers(clean_customers(pd.DataFrame([a, b]), AS_OF).clean, AS_OF)
    assert data.iloc[0].rfm_score == "555"
    assert data.iloc[1].rfm_score == "111"
    assert data.iloc[1].recency_days == (AS_OF - pd.Timestamp(b["join_date"])).days


def test_tier_math_and_empty(frame):
    data = clean_customers(frame, AS_OF).clean
    summary = tier_summary(data).set_index("membership_tier")
    assert summary.loc["Gold", "revenue"] == 1200
    assert summary.loc["Gold", "average_order_value"] == 150
    assert summary.loc["Gold", "revenue_share"] == 1
    assert summary.loc["Bronze", "revenue_per_customer"] == 0
    assert tier_summary(data.head(0)).revenue_share.sum() == 0


def test_empty_segmentation(frame):
    empty = clean_customers(frame.head(0), AS_OF).clean
    assert segment_customers(empty, AS_OF).empty
