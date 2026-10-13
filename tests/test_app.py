from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_app_navigation_and_quality_challenge():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert app.metric[0].value == "600"
    for page in ["Data Studio", "Segments", "Campaigns"]:
        app.sidebar.radio(key="page").set_value(page).run()
        assert not app.exception
    app.sidebar.radio(key="page").set_value("Data Studio").run()
    app.sidebar.selectbox(key="source").set_value("Quality challenge").run()
    assert not app.exception
    assert [m.value for m in app.metric] == ["630", "600", "24", "6"]


def test_filters_empty_state_and_campaign_types():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.multiselect(key="tiers").set_value([]).run()
    assert not app.exception
    assert "No customers match" in app.info[0].value
    app.multiselect(key="tiers").set_value(["Gold"]).run()
    assert not app.exception
    assert int(app.metric[0].value) < 600
    app.sidebar.radio(key="page").set_value("Campaigns").run()
    for campaign in ["Anniversary", "Win-back", "Welcome"]:
        app.radio(key="campaign").set_value(campaign).run()
        assert not app.exception
        assert app.metric[2].value == "Draft only"


def test_import_prompt_and_all_invalid_date():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.selectbox(key="source").set_value("Import CSV").run()
    assert not app.exception
    assert "Upload a synthetic customer CSV" in app.info[0].value
    app.sidebar.selectbox(key="source").set_value("Synthetic demo").run()
    from datetime import date

    app.sidebar.date_input[0].set_value(date(2020, 1, 1)).run()
    assert not app.exception
    assert "No valid customers" in app.warning[0].value
