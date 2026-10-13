import pandas as pd
import pytest

from customeriq.data import MAX_BYTES, clean_customers, export_csv, read_csv
from scripts.generate_data import dirty_sample, generate_customers

AS_OF = "2026-10-12"


def test_quality_challenge_preserves_revenue():
    source = generate_customers()
    result = clean_customers(dirty_sample(source), AS_OF)
    assert result.input_rows == 630
    assert len(result.clean) == 600
    assert len(result.rejected) == 6
    assert result.removed_duplicates == 24
    assert result.clean.total_spend.sum() == pytest.approx(source.total_spend.sum())
    assert result.normalized_cells == 70


def test_transitive_identity_resolution_and_optout(customer):
    rows = [
        customer,
        dict(
            customer,
            customer_id="002",
            email=" DEMO@EXAMPLE.COM ",
            total_spend="900",
            marketing_opt_in="false",
            updated_at="2026-10-01",
        ),
        dict(customer, customer_id="002", email="other@example.com", total_spend="1000", updated_at="2026-10-02"),
    ]
    result = clean_customers(pd.DataFrame(rows), AS_OF)
    assert len(result.clean) == 1
    assert result.clean.iloc[0].total_spend == 1200
    assert not result.clean.iloc[0].marketing_opt_in
    assert result.removed_duplicates == 2
    assert result.duplicates.identity_group.nunique() == 1


def test_tie_uses_last_source_row(customer):
    result = clean_customers(pd.DataFrame([customer, dict(customer, total_spend="1500")]), AS_OF)
    assert result.clean.iloc[0].total_spend == 1500


@pytest.mark.parametrize(
    "column,value",
    [
        ("email", "bad"),
        ("customer_id", ""),
        ("membership_tier", "Diamond"),
        ("join_date", "2027-01-01"),
        ("join_date", "2025-02-30"),
        ("join_date", "2025-1-1"),
        ("last_purchase_date", "2024-01-01"),
        ("updated_at", "2026-01-01"),
        ("total_spend", "-1"),
        ("total_spend", "inf"),
        ("purchase_count", "2.5"),
        ("total_spend", "1e300"),
        ("purchase_count", "1e30"),
        ("marketing_opt_in", "perhaps"),
        ("last_purchase_date", ""),
    ],
)
def test_invalid_rows_are_quarantined(customer, column, value):
    result = clean_customers(pd.DataFrame([dict(customer, **{column: value})]), AS_OF)
    assert result.clean.empty
    assert len(result.rejected) == 1
    assert result.rejected.iloc[0].issues


def test_zero_purchase_and_unknown_country(customer):
    item = dict(customer, purchase_count="0", total_spend="0", last_purchase_date="")
    del item["country"]
    result = clean_customers(pd.DataFrame([item]), AS_OF)
    assert len(result.clean) == 1
    assert result.clean.iloc[0].country == "Unknown"


def test_csv_roundtrip_and_leading_zero(frame):
    result = clean_customers(read_csv(export_csv(frame)), AS_OF)
    assert result.clean.iloc[0].customer_id == "001"
    assert len(clean_customers(result.clean, AS_OF).clean) == 1


def test_unknown_columns_cannot_override_audit(frame):
    frame["source_row"] = 999
    frame["segment"] = "Fake"
    result = clean_customers(frame, AS_OF)
    assert result.clean.iloc[0].source_row == 2
    assert "segment" not in result.clean


def test_formula_export_escape():
    text = export_csv(pd.DataFrame({"name": ["=1+1", "  @SUM(A1)", "normal"]})).decode("utf-8-sig")
    assert "'=1+1" in text
    assert "'  @SUM(A1)" in text


@pytest.mark.parametrize(
    "payload",
    [b"", b"\xff", b"email, EMAIL\na,b", b"x" * (MAX_BYTES + 1), b"id,email\n1,a@example.com,extra"],
    ids=["empty", "encoding", "duplicate-columns", "oversized", "extra-fields"],
)
def test_bad_csv_is_reported(payload):
    with pytest.raises(ValueError):
        read_csv(payload)


def test_missing_schema():
    with pytest.raises(ValueError, match="Missing required columns"):
        clean_customers(pd.DataFrame({"email": ["demo@example.com"]}), AS_OF)


def test_empty_schema_only(frame):
    result = clean_customers(frame.head(0), AS_OF)
    assert result.clean.empty
    assert result.removed_duplicates == 0


def test_generated_data_is_repeatable_and_synthetic():
    a, b = generate_customers(), generate_customers()
    pd.testing.assert_frame_equal(a, b)
    assert a.email.str.endswith("@example.com").all()
    assert a.first_name.str.startswith("Member").all()
