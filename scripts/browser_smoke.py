"""Exercise the running app and capture genuine browser screenshots.

Start Streamlit separately, then run this script. Install Chromium with
`python -m playwright install chromium`, or pass `--channel msedge`.
"""

import argparse
from pathlib import Path

import pandas as pd
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--channel", default=None)
    parser.add_argument("--screenshots", type=Path, default=ROOT / "docs/screenshots")
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=args.channel)
        page = browser.new_page(viewport={"width": 1600, "height": 1500}, device_scale_factor=1)
        page.set_default_timeout(30_000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        sidebar = page.get_by_test_id("stSidebar")

        def ready():
            expect(page.get_by_test_id("stException")).to_have_count(0)
            expect(
                page.get_by_text("CustomerIQ / Customer intelligence, made actionable.", exact=False)
            ).to_be_visible()
            expect(page.locator('[data-stale="true"]')).to_have_count(0)

        def shot(name):
            ready()
            page.get_by_test_id("stMain").evaluate("el => el.scrollTop = 0")
            # Canvas tables and Plotly need a paint after tab/container resize.
            page.wait_for_timeout(1000)
            page.screenshot(path=str(args.screenshots / name), full_page=True, animations="disabled")

        def navigate(name):
            sidebar.get_by_text(name, exact=True).click()

        def source(name):
            control = sidebar.get_by_role("combobox", name="Data source")
            control.click()
            page.get_by_role("option", name=name, exact=True).click()
            expect(control).to_have_value(name)

        expect(page.get_by_test_id("stMetricValue").first).to_have_text("600")
        expect(page.get_by_test_id("stPlotlyChart")).to_have_count(3)
        shot("overview.png")
        navigate("Data Studio")
        source("Quality challenge")
        expect(page.get_by_test_id("stMetricValue").nth(0)).to_have_text("630")
        expect(page.get_by_test_id("stMetricValue").nth(2)).to_have_text("24")
        expect(page.get_by_test_id("stMetricValue").nth(3)).to_have_text("6")
        page.get_by_role("tab", name="Duplicate audit").click()
        shot("data-studio.png")
        page.get_by_role("tab", name="Clean customers").click()
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Download clean CSV", exact=True).click()
        downloaded = pd.read_csv(download_info.value.path())
        assert len(downloaded) == 600
        assert round(downloaded.total_spend.sum(), 2) == 799415.00

        source("Import CSV")
        sidebar.locator('input[type="file"]').set_input_files(str(ROOT / "data/customers_dirty.csv"))
        expect(page.get_by_test_id("stMetricValue").nth(0)).to_have_text("630")
        expect(page.get_by_test_id("stMetricValue").nth(1)).to_have_text("600")
        print("PASS: CSV upload, cleaning, duplicate audit, and clean CSV download")

        navigate("Segments")
        expect(page.get_by_text("Recency meets customer value", exact=True)).to_be_visible()
        expect(page.get_by_test_id("stPlotlyChart")).to_have_count(1)
        shot("segments.png")
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Export selected segments", exact=True).click()
        segments = pd.read_csv(download_info.value.path())
        assert len(segments) == 600 and segments.segment.nunique() == 6
        print("PASS: segmentation chart and audience export")

        navigate("Campaigns")
        expect(page.get_by_text("Email preview", exact=True)).to_be_visible()
        for campaign in ["Welcome", "Anniversary", "Win-back"]:
            page.get_by_text(campaign, exact=True).click()
            expect(page.get_by_test_id("stMetricValue").nth(2)).to_have_text("Draft only")
            # Wait for each rerun to change the actual preview subject.
            subject = {
                "Welcome": "Welcome to the community,",
                "Anniversary": "Celebrating your membership anniversary,",
                "Win-back": "It's been a while,",
            }[campaign]
            expect(page.get_by_text(subject, exact=False)).to_be_visible()
            with page.expect_download() as download_info:
                page.get_by_role("button", name="Export personalized email drafts", exact=True).click()
            drafts = pd.read_csv(download_info.value.path())
            assert not drafts.empty
            assert drafts.campaign.eq(campaign).all()
            assert drafts.to.str.endswith("@example.com").all()
            assert not drafts.body.str.contains(r"\$first_name").any()
        shot("campaigns.png")
        print("PASS: welcome, anniversary, and win-back previews and exports")

        navigate("Data Studio")
        sidebar.locator('input[type="file"]').set_input_files(
            {"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"email\ndemo@example.com\n"}
        )
        expect(page.get_by_text("Missing required columns:", exact=False)).to_be_visible()
        expect(page.get_by_test_id("stException")).to_have_count(0)
        sidebar.locator('input[type="file"]').set_input_files(str(ROOT / "data/import_template.csv"))
        expect(page.get_by_test_id("stMetricValue").nth(0)).to_have_text("0")
        print("PASS: invalid schema and empty CSV handling")

        source("Synthetic demo")
        navigate("Overview")
        expect(page.get_by_test_id("stMetricValue").first).to_have_text("600")
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(args.url)
        expect(mobile.get_by_test_id("stMetricValue").first).to_have_text("600")
        expect(mobile.get_by_text("Your customers, in focus.", exact=True)).to_be_visible()
        mobile.screenshot(path=str(args.screenshots / "mobile.png"), full_page=True)
        assert not errors, errors
        print("PASS: mobile render; no browser JavaScript errors")
        browser.close()


if __name__ == "__main__":
    main()
