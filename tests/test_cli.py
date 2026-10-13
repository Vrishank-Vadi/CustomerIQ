import json
from pathlib import Path

import pandas as pd
import pytest

from customeriq.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def test_batch_exports_and_audit(tmp_path):
    main(["--input", str(ROOT / "data/customers_dirty.csv"), "--as-of", "2026-10-12", "--output", str(tmp_path)])
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["clean_customers"] == 600
    assert report["duplicates_removed"] == 24
    assert report["quarantined_rows"] == 6
    assert report["lifetime_revenue_usd"] == 799415.0
    for campaign in ["welcome", "anniversary", "win_back"]:
        drafts = pd.read_csv(tmp_path / f"{campaign}_drafts.csv")
        assert not drafts.empty
        assert drafts.to.str.endswith("@example.com").all()


def test_batch_invalid_input_does_not_write(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["--input", str(tmp_path / "missing.csv"), "--as-of", "2026-10-12", "--output", str(tmp_path / "out")])
    assert exc.value.code == 2
    assert not (tmp_path / "out").exists()
