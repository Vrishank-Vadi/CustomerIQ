import pandas as pd
import pytest


@pytest.fixture
def customer():
    return {
        "customer_id": "001",
        "first_name": "Demo",
        "last_name": "Example",
        "email": "demo@example.com",
        "membership_tier": "Gold",
        "join_date": "2025-01-01",
        "last_purchase_date": "2026-09-20",
        "total_spend": "1200",
        "purchase_count": "8",
        "marketing_opt_in": "true",
        "updated_at": "2026-10-12",
        "country": "Canada",
    }


@pytest.fixture
def frame(customer):
    return pd.DataFrame([customer])
