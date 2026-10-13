"""Run with: streamlit run app.py"""

from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from customeriq.analytics import COLORS, SEGMENTS, segment_customers, tier_summary
from customeriq.campaigns import CAMPAIGNS, campaign_export, eligible_customers, render_email
from customeriq.data import TIERS, clean_customers, export_csv, read_csv

ROOT = Path(__file__).resolve().parent
DEMO_DATE = date(2026, 10, 12)
st.set_page_config(page_title="CustomerIQ · Customer intelligence", page_icon="◈", layout="wide")
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"], .stApp {font-family:'DM Sans',sans-serif;}
.stApp {background:#f7f9fb;color:#172d3b;}
h1,h2,h3 {font-family:'Manrope',sans-serif!important;letter-spacing:-.035em;}
h1 {font-size:2.5rem!important;font-weight:800!important;padding-bottom:.4rem!important;}
h3 {font-size:1.18rem!important;}
.block-container {max-width:1480px;padding-top:2.4rem;padding-bottom:3rem;}
[data-testid="stSidebar"] {background:#102c39;}
[data-testid="stSidebar"] hr {border-color:#34505c;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding:8px 2px;}
[data-testid="stMetric"] {background:white;border:1px solid #e2e8ec;border-radius:12px;padding:20px 22px;}
[data-testid="stMetricLabel"] {color:#667e8c;font-size:.82rem;}
[data-testid="stMetricValue"] {font-family:'Manrope',sans-serif;font-size:2rem;font-weight:800;}
[data-testid="stVerticalBlockBorderWrapper"] > div {border-radius:12px!important;}
.eyebrow {font-size:.72rem;font-weight:700;letter-spacing:.16em;color:#718791;margin-bottom:12px;}
.subtitle {font-size:1rem;color:#6c818b;margin-bottom:24px;}
.badge {display:inline-block;background:#dff2ec;border:1px solid #c6e9de;color:#117560;border-radius:30px;padding:5px 12px;font-size:.72rem;font-weight:700;letter-spacing:.06em;}
.brand {font-family:'Manrope',sans-serif;font-size:1.8rem;font-weight:800;letter-spacing:-.07em;margin:8px 0 0;}
.brand span {color:#64d0b0;}
.brand-caption {font-size:.72rem;letter-spacing:.12em;color:#9fb9c5!important;margin-bottom:28px;}
.sidebar-foot {font-size:.75rem;color:#96afba!important;line-height:1.65;}
.callout {background:#eaf4f1;border-left:3px solid #0f8a71;padding:17px 22px;border-radius:0 8px 8px 0;margin:8px 0 20px;color:#335b50;}
.mail {background:#fff;border:1px solid #e0e7eb;border-radius:12px;padding:28px;white-space:pre-wrap;line-height:1.8;color:#344c58;font-size:.95rem;}
</style>
""",
    unsafe_allow_html=True,
)


def chart(fig, height=330):
    fig.update_layout(
        template="plotly_white",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, Arial", color="#526a77", size=12),
        margin=dict(l=5, r=15, t=15, b=15),
        legend_title_text="",
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(gridcolor="#edf1f3", zeroline=False)
    fig.update_yaxes(gridcolor="#edf1f3", zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def download(label, frame, filename, key):
    st.download_button(label, export_csv(frame), filename, "text/csv", key=key, width="stretch", on_click="ignore")


with st.sidebar:
    st.markdown(
        '<div class="brand">◈ Customer<span>IQ</span></div><div class="brand-caption">CUSTOMER INTELLIGENCE</div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Workspace", ["Overview", "Data Studio", "Segments", "Campaigns"], label_visibility="collapsed", key="page"
    )
    st.divider()
    source = st.selectbox("Data source", ["Synthetic demo", "Quality challenge", "Import CSV"], key="source")
    as_of = st.date_input(
        "Analysis date", value=DEMO_DATE, help="All recency, validation, and campaign rules use this date."
    )
    st.caption("Demo snapshot · October 12, 2026")
    st.divider()
    st.markdown(
        '<div class="sidebar-foot">PORTFOLIO EDITION<br>Built with Python, Pandas & Streamlit.<br><br>Sample records are entirely synthetic.<br>Campaigns create drafts only.</div>',
        unsafe_allow_html=True,
    )

payload = None
if source == "Import CSV":
    with st.sidebar:
        uploaded = st.file_uploader("Upload customer CSV", type="csv", help="UTF-8 · up to 10 MB and 50,000 rows")
        st.download_button(
            "Download CSV template",
            (ROOT / "data/import_template.csv").read_bytes(),
            "import_template.csv",
            "text/csv",
            on_click="ignore",
        )
    if uploaded is not None:
        payload = uploaded.getvalue()
else:
    payload = (
        ROOT / "data" / ("customers_clean.csv" if source == "Synthetic demo" else "customers_dirty.csv")
    ).read_bytes()

titles = {
    "Overview": (
        "Your customers, in focus.",
        "Understand value, spot opportunities, and turn customer data into action.",
    ),
    "Data Studio": (
        "Better data. Clearer decisions.",
        "Import, inspect, and clean customer snapshots with a complete audit trail.",
    ),
    "Segments": ("Know who needs what.", "Explainable customer segments, grounded in recency, frequency, and value."),
    "Campaigns": (
        "Make the next touchpoint count.",
        "Build consent-aware audiences and personalized lifecycle email drafts.",
    ),
}
left, right = st.columns([5, 1])
with left:
    st.markdown(f'<div class="eyebrow">WORKSPACE / {page.upper()}</div>', unsafe_allow_html=True)
with right:
    st.markdown('<span class="badge">● &nbsp; LOCAL ANALYSIS</span>', unsafe_allow_html=True)
st.title(titles[page][0])
st.markdown(f'<div class="subtitle">{titles[page][1]}</div>', unsafe_allow_html=True)
if payload is None:
    st.info("Upload a synthetic customer CSV in the sidebar to start. Use the template for the required column names.")
    st.stop()
try:
    raw = read_csv(payload)
    result = clean_customers(raw, as_of)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

data = segment_customers(result.clean, as_of)
if result.removed_duplicates or len(result.rejected):
    st.info(
        f"Analysis uses {len(data):,} clean customers. {result.removed_duplicates:,} duplicate snapshots removed; {len(result.rejected):,} invalid rows quarantined. See Data Studio for the audit."
    )

if page == "Data Studio":
    cols = st.columns(4)
    for col, label, value in zip(
        cols,
        ["SOURCE ROWS", "CLEAN CUSTOMERS", "DUPLICATES REMOVED", "ROWS QUARANTINED"],
        [result.input_rows, len(data), result.removed_duplicates, len(result.rejected)],
    ):
        col.metric(label, f"{value:,}")
    st.markdown("### Cleaning workspace")
    st.caption(
        f"{result.normalized_cells:,} whitespace/case/blank-country cells normalized. Clean rows are used automatically across all views."
    )
    tab1, tab2, tab3, tab4 = st.tabs(["Clean customers", "Duplicate audit", "Quarantined rows", "Source preview"])
    with tab1:
        st.dataframe(result.clean, hide_index=True, width="stretch")
        download("Download clean CSV", result.clean.drop(columns="source_row"), "customeriq_clean.csv", "clean")
    with tab2:
        st.caption(
            "Connected records share a customer ID or normalized email. Newest updated_at wins; last source row breaks ties. Spend is never summed. Any opt-out in a valid identity group wins."
        )
        st.dataframe(
            result.duplicates.sort_values(["identity_group", "source_row"]),
            hide_index=True,
            width="stretch",
            column_order=[
                "identity_group",
                "resolution",
                "source_row",
                "customer_id",
                "email",
                "total_spend",
                "updated_at",
                "marketing_opt_in",
            ],
            column_config={
                "total_spend": st.column_config.NumberColumn("Lifetime spend", format="$%.2f"),
                "updated_at": st.column_config.DateColumn("Snapshot date", format="YYYY-MM-DD"),
            },
        )
        download("Download duplicate audit", result.duplicates, "customeriq_duplicates.csv", "dupes")
    with tab3:
        st.caption(
            "Fix the reported issues in the source CSV and import it again. No invalid row is silently repaired into a valid customer."
        )
        st.dataframe(
            result.rejected,
            hide_index=True,
            width="stretch",
            column_order=[
                "source_row",
                "issues",
                "customer_id",
                "email",
                "membership_tier",
                "total_spend",
                "purchase_count",
            ],
        )
        download("Download quarantine report", result.rejected, "customeriq_quarantine.csv", "rejects")
    with tab4:
        st.dataframe(raw.head(500), hide_index=True, width="stretch")
        st.caption("Preview limited to 500 rows. Source data is never overwritten.")
    with st.expander("CSV contract & cleaning rules"):
        st.write(
            "One row represents a lifetime customer snapshot, not a transaction. Dates must be YYYY-MM-DD and on or before the analysis date. Amounts are nonnegative USD numbers without currency symbols. Country is optional; all other template fields are required."
        )
        st.write(
            "Recognized tiers: Bronze, Silver, Gold, Platinum. Consent: true/false, yes/no, or 1/0. Blank purchase dates are allowed only for zero-purchase customers with zero spend. Identity matching uses exact trimmed IDs or case-insensitive emails; names alone never match."
        )
elif data.empty:
    st.warning("No valid customers remain. Inspect Data Studio or select another dataset or analysis date.")
else:
    f1, f2 = st.columns([2, 2])
    tiers = f1.multiselect("Membership tiers", TIERS, default=TIERS, key="tiers")
    countries = sorted(data["country"].unique())
    selected_countries = f2.multiselect("Markets", countries, default=countries, key=f"countries_{source}")
    filtered = data[data["membership_tier"].isin(tiers) & data["country"].isin(selected_countries)].copy()
    st.caption(f"{len(filtered):,} of {len(data):,} customers · As of {as_of:%b %d, %Y} · Lifetime revenue in USD")
    if filtered.empty:
        st.info("No customers match these filters. Select at least one populated tier and market.")
        st.stop()

    if page == "Overview":
        revenue = filtered["total_spend"].sum()
        risk = filtered[filtered["segment"].isin(["At risk", "Dormant"])]
        cols = st.columns(4)
        cols[0].metric("CUSTOMERS", f"{len(filtered):,}")
        cols[1].metric("LIFETIME REVENUE", f"${revenue:,.0f}")
        cols[2].metric("REVENUE / CUSTOMER", f"${revenue / len(filtered):,.0f}")
        cols[3].metric(
            "AT RISK + DORMANT",
            f"{len(risk):,}",
            help="Customers whose last purchase (or signup when never purchased) was over 90 days ago.",
        )
        st.write("")
        a, b = st.columns([1.3, 1])
        summary = tier_summary(filtered)
        with a, st.container(border=True):
            st.markdown("### Revenue by membership")
            st.caption("Where customer value is concentrated")
            fig = px.bar(
                summary,
                y="membership_tier",
                x="revenue",
                orientation="h",
                text="revenue",
                color="membership_tier",
                color_discrete_map=dict(zip(TIERS, ["#a0b6c3", "#5d929f", "#219580", "#105a50"])),
            )
            fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside", cliponaxis=False)
            fig.update_layout(
                showlegend=False,
                xaxis_title="Lifetime revenue (USD)",
                yaxis_title=None,
                xaxis_range=[0, summary.revenue.max() * 1.25 or 1],
            )
            chart(fig)
        with b, st.container(border=True):
            st.markdown("### Your customer mix")
            st.caption("Lifecycle segments at a glance")
            mix = filtered["segment"].value_counts().rename_axis("segment").reset_index(name="customers")
            fig = px.pie(
                mix, values="customers", names="segment", hole=0.72, color="segment", color_discrete_map=COLORS
            )
            fig.update_traces(textinfo="none", marker=dict(line=dict(color="#f7f9fb", width=3)))
            fig.update_layout(
                legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
                annotations=[
                    dict(text=f"<b>{len(filtered):,}</b><br>customers", x=0.5, y=0.5, showarrow=False, font_size=20)
                ],
            )
            chart(fig)
        a, b = st.columns([1.3, 1])
        with a, st.container(border=True):
            st.markdown("### Customer acquisition")
            st.caption("Signup cohorts · counts by month, not a revenue time series")
            cohort = (
                filtered.assign(month=filtered.join_date.dt.to_period("M").dt.to_timestamp())
                .groupby("month")
                .size()
                .reset_index(name="customers")
            )
            fig = px.area(cohort, x="month", y="customers", color_discrete_sequence=["#168672"])
            fig.update_layout(xaxis_title=None, yaxis_title="New customers")
            chart(fig, 240)
        with b, st.container(border=True):
            st.markdown("### Next best conversations")
            eligible = eligible_customers(filtered, "Win-back", as_of)
            st.markdown(
                f'<div class="callout"><b>{len(eligible):,} customers ready for a win-back draft</b><br>Opted in, with no purchase in at least 90 days.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                eligible.sort_values("total_spend", ascending=False)[
                    ["first_name", "membership_tier", "total_spend"]
                ].head(5),
                hide_index=True,
                width="stretch",
                column_config={
                    "first_name": "Customer",
                    "membership_tier": "Tier",
                    "total_spend": st.column_config.NumberColumn("Lifetime value", format="$%.2f"),
                },
            )
        with st.expander("Membership revenue detail"):
            st.dataframe(summary, hide_index=True, width="stretch")
            download("Export tier analysis", summary, "customeriq_tiers.csv", "tiers_export")

    elif page == "Segments":
        a, b = st.columns([1.6, 1])
        with a, st.container(border=True):
            st.markdown("### Recency meets customer value")
            fig = px.scatter(
                filtered,
                x="recency_days",
                y="total_spend",
                color="segment",
                size="purchase_count",
                size_max=24,
                hover_data=["customer_id", "membership_tier"],
                color_discrete_map=COLORS,
                category_orders={"segment": SEGMENTS},
            )
            fig.update_layout(
                xaxis_title="Days since purchase (or signup)",
                yaxis_title="Lifetime revenue (USD)",
                legend=dict(orientation="h", y=-0.2),
            )
            chart(fig, 420)
        with b, st.container(border=True):
            st.markdown("### Segment playbook")
            for name, action in [
                ("Champions", "Recognize and reward your highest-value active members."),
                ("New customers", "Welcome them and guide the first few purchases."),
                ("Loyal", "Keep frequent customers engaged with member benefits."),
                ("Active", "Build a repeat-purchase habit."),
                ("At risk", "Reconnect before the relationship cools."),
                ("Dormant", "Invite a return with a thoughtful win-back."),
            ]:
                st.markdown(f"**{name}** · {(filtered.segment == name).sum():,}")
                st.caption(action)
        chosen = st.multiselect("Explore segments", SEGMENTS, default=SEGMENTS)
        audience = filtered[filtered.segment.isin(chosen)]
        st.dataframe(
            audience[
                [
                    "customer_id",
                    "first_name",
                    "membership_tier",
                    "segment",
                    "recency_days",
                    "purchase_count",
                    "total_spend",
                    "rfm_score",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
        download("Export selected segments", audience, "customeriq_segments.csv", "segments_export")
        with st.expander("How segments and RFM scores are calculated"):
            st.write(
                "First matching rule wins: Champions = spend ≥ $1,000 and recency ≤ 60 days; New customers = signup ≤ 30 days; Loyal = ≥ 5 orders and recency ≤ 60; Active = recency ≤ 90; At risk = recency ≤ 180; Dormant = recency > 180. Recency falls back to signup for non-buyers."
            )
            st.write(
                "R scores 5→1 use recency ≤30, ≤60, ≤90, ≤180, >180 days. F scores use ≥15, ≥8, ≥4, ≥2, <2 orders. M scores use ≥$2,000, ≥$1,000, ≥$500, ≥$100, <$100. These fixed business rules are descriptive, not a predictive model."
            )

    elif page == "Campaigns":
        campaign = st.radio("Lifecycle campaign", CAMPAIGNS, horizontal=True, key="campaign")
        with st.expander("Audience rules", expanded=True):
            welcome_days = 7
            anniversary_days = 30
            winback_days = 90
            if campaign == "Welcome":
                welcome_days = st.slider("Days since signup", 0, 30, 7)
                st.caption("Includes signup today through the selected number of days ago.")
            elif campaign == "Anniversary":
                anniversary_days = st.slider("Upcoming anniversary window (days)", 0, 90, 30)
                st.caption(
                    "First and later membership anniversaries, including today. February 29 anniversaries use February 28 in non-leap years."
                )
            else:
                winback_days = st.slider("Minimum days since purchase", 30, 365, 90)
                st.caption("Only previous purchasers qualify. Customers who never purchased are excluded.")
        eligible = eligible_customers(filtered, campaign, as_of, welcome_days, anniversary_days, winback_days)
        c1, c2, c3 = st.columns(3)
        c1.metric("ELIGIBLE CUSTOMERS", f"{len(eligible):,}")
        c2.metric("OPT-OUTS EXCLUDED", f"{(~filtered.marketing_opt_in).sum():,}")
        c3.metric("DELIVERY MODE", "Draft only")
        st.write("")
        if eligible.empty:
            st.info("No opted-in customers qualify. Adjust the audience window or filters.")
        else:
            a, b = st.columns([1, 1.4])
            with a:
                st.markdown("### Audience")
                st.dataframe(
                    eligible[["customer_id", "first_name", "membership_tier"]],
                    hide_index=True,
                    width="stretch",
                    height=260,
                )
                download(
                    "Export personalized email drafts",
                    campaign_export(eligible, campaign),
                    f"customeriq_{campaign.lower()}_drafts.csv",
                    "campaign_export",
                )
            with b:
                st.markdown("### Email preview")
                customer_id = st.selectbox("Preview customer", eligible.customer_id.tolist())
                row = eligible.loc[eligible.customer_id.eq(customer_id)].iloc[0]
                email = render_email(row, campaign)
                st.caption(f"To: {email['to']}")
                st.markdown(f"**{escape(email['subject'])}**")
                st.markdown(f'<div class="mail">{escape(email["body"])}</div>', unsafe_allow_html=True)
        st.caption(
            "Drafts are generated locally. No email provider, API key, scheduling service, or delivery integration is configured. Campaign audiences can overlap; review before use."
        )

st.divider()
st.caption(
    "CustomerIQ  /  Customer intelligence, made actionable.     •     Synthetic demo data     •     Portfolio edition"
)
