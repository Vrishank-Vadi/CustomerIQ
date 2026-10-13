import pandas as pd
import pytest

from customeriq.campaigns import anniversary_date, campaign_export, eligible_customers, render_email
from customeriq.data import clean_customers

AS_OF = "2026-10-12"


def test_welcome_boundary_and_consent(customer):
    rows = [
        dict(
            customer,
            customer_id=str(i),
            email=f"test{i}@example.com",
            join_date=joined,
            last_purchase_date="",
            total_spend=0,
            purchase_count=0,
            marketing_opt_in=consent,
        )
        for i, (joined, consent) in enumerate(
            [("2026-10-12", "true"), ("2026-10-05", "true"), ("2026-10-04", "true"), ("2026-10-10", "false")]
        )
    ]
    data = clean_customers(pd.DataFrame(rows), AS_OF).clean
    assert eligible_customers(data, "Welcome", AS_OF).customer_id.tolist() == ["0", "1"]


def test_winback_boundary_excludes_nonbuyers(customer):
    rows = [
        dict(customer, customer_id="a", email="a@example.com", last_purchase_date="2026-07-14"),
        dict(customer, customer_id="b", email="b@example.com", last_purchase_date="2026-07-15"),
        dict(customer, customer_id="c", email="c@example.com", last_purchase_date="", total_spend=0, purchase_count=0),
    ]
    data = clean_customers(pd.DataFrame(rows), AS_OF).clean
    assert eligible_customers(data, "Win-back", AS_OF).customer_id.tolist() == ["a"]


@pytest.mark.parametrize(
    "joined,today,expected",
    [
        ("2024-02-29", "2025-02-20", "2025-02-28"),
        ("2024-02-29", "2028-02-20", "2028-02-29"),
        ("2025-01-05", "2026-12-20", "2027-01-05"),
        ("2025-10-12", AS_OF, AS_OF),
        (AS_OF, AS_OF, "2027-10-12"),
    ],
)
def test_anniversary_calendar(joined, today, expected):
    assert anniversary_date(joined, today) == pd.Timestamp(expected)


def test_anniversary_audience_and_personalization(customer):
    row = dict(customer, join_date="2024-10-20")
    data = clean_customers(pd.DataFrame([row]), AS_OF).clean
    audience = eligible_customers(data, "Anniversary", AS_OF)
    assert len(audience) == 1
    mail = render_email(audience.iloc[0], "Anniversary")
    assert "2-year" in mail["body"]
    assert "Demo" in mail["subject"]
    assert "$first_name" not in mail["body"]


@pytest.mark.parametrize("campaign", ["Welcome", "Anniversary", "Win-back"])
def test_templates_and_empty_audiences(frame, campaign):
    data = clean_customers(frame, AS_OF).clean
    mail = render_email(data.iloc[0], campaign)
    assert mail["to"] == "demo@example.com"
    assert "Gold" in mail["body"]
    empty = eligible_customers(data.head(0), campaign, AS_OF)
    assert campaign_export(empty, campaign).columns.tolist() == ["customer_id", "to", "campaign", "subject", "body"]


def test_unknown_campaign(frame):
    with pytest.raises(ValueError):
        eligible_customers(clean_customers(frame, AS_OF).clean, "Unknown", AS_OF)
