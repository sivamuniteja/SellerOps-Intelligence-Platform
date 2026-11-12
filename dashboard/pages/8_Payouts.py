"""Payout Batches and Disbursement Operations Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import (
    apply_theme,
    get_database,
    render_metric_card,
    render_page_header,
    render_empty_state,
    apply_plotly_white_layout,
    COLORS,
)

st.set_page_config(page_title="Payout Batches - SellerOps", page_icon="💳", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Seller Payout Batches & Disbursements",
    subtitle="Auditing net payout disbursements, rolling reserve holds, eligibility rules, and disbursement cycles.",
    badge="Banking & Settlements",
)

payout_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_batches,
        ROUND(COALESCE(SUM(gross_sales_cents), 0) / 100.0, 2) as total_gross_settled,
        ROUND(COALESCE(SUM(total_reserve_held_cents), 0) / 100.0, 2) as total_reserve_held,
        ROUND(COALESCE(SUM(net_payout_amount_cents), 0) / 100.0, 2) as total_net_disbursed
    FROM payouts;
""")
tot_b = int(payout_kpis["total_batches"].iloc[0] or 0)
tot_net = float(payout_kpis["total_net_disbursed"].iloc[0] or 0.0)
tot_res = float(payout_kpis["total_reserve_held"].iloc[0] or 0.0)

# Check Anomaly 1: Premature payouts
ano1_df = db.query_df("""
    SELECT COUNT(*) as premature_count
    FROM payout_lines pl
    JOIN order_lines ol ON pl.order_line_id = ol.order_line_id
    JOIN reserve_ledger r ON pl.order_line_id = r.order_line_id
    JOIN payouts p ON pl.payout_id = p.payout_id
    WHERE ol.line_status != 'DELIVERED' OR p.batch_date < r.release_scheduled_date;
""")
premature = int(ano1_df["premature_count"].iloc[0] or 0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Net Disbursed", f"${tot_net:,.2f}", "Total Net Payouts")
with c2:
    render_metric_card("Rolling Reserve Held", f"${tot_res:,.2f}", "Risk Collateral")
with c3:
    render_metric_card("Total Payout Batches", f"{tot_b:,}", "Disbursement Cycles")
with c4:
    render_metric_card("Settled Order Lines", f"{db.row_count('payout_lines'):,}", "Line Items")
with c5:
    render_metric_card("Premature Disbursements", f"{premature}", "Anomaly 1 Violations", delta_color="danger")

st.markdown("---")

# Filter Controls
col_status_filter, _ = st.columns([2, 2])
with col_status_filter:
    p_statuses = ["PAID", "HELD", "PROCESSING", "SCHEDULED", "FAILED"]
    selected_p_statuses = st.multiselect("Filter Payout Status", p_statuses, default=["PAID", "HELD"])

col_monthly, col_status_pie = st.columns(2)

with col_monthly:
    st.subheader("Monthly Net Disbursement Volume ($)")
    monthly_df = db.query_df("""
        SELECT
            SUBSTR(batch_date, 1, 7) as month,
            ROUND(SUM(net_payout_amount_cents) / 100.0, 2) as net_disbursed,
            COUNT(*) as batch_count
        FROM payouts
        GROUP BY month
        ORDER BY month ASC;
    """)
    if not monthly_df.empty:
        fig_monthly = px.bar(
            monthly_df,
            x="month",
            y="net_disbursed",
            color_discrete_sequence=[COLORS["primary"]],
            labels={"month": "Month", "net_disbursed": "Net Disbursed ($)"},
        )
        apply_plotly_white_layout(fig_monthly)
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        render_empty_state()

with col_status_pie:
    st.subheader("Payout Batch Status Breakdown")
    status_df = db.query_df("""
        SELECT payout_status, COUNT(*) as count
        FROM payouts
        GROUP BY payout_status;
    """)
    filtered_status_pie = status_df[status_df["payout_status"].isin(selected_p_statuses)]
    if not filtered_status_pie.empty:
        fig_status = px.pie(
            filtered_status_pie,
            names="payout_status",
            values="count",
            color_discrete_sequence=[COLORS["success"], COLORS["warning"], COLORS["primary"], COLORS["danger"]],
            hole=0.45,
        )
        apply_plotly_white_layout(fig_status)
        st.plotly_chart(fig_status, use_container_width=True)
    else:
        render_empty_state("No Payout Status Match", "Select at least one payout status.")

st.markdown("---")

# Anomaly 1 Audit Table
st.subheader("⚠️ Premature Payout Disbursements (Anomaly 1: Paid Prior to Delivery or Hold Release)")
premature_table = db.query_df("""
    SELECT
        pl.line_id,
        pl.payout_id,
        pl.order_line_id,
        ol.line_status,
        r.release_scheduled_date,
        p.batch_date,
        ROUND(pl.net_line_amount_cents / 100.0, 2) as net_amount_dollars
    FROM payout_lines pl
    JOIN order_lines ol ON pl.order_line_id = ol.order_line_id
    JOIN reserve_ledger r ON pl.order_line_id = r.order_line_id
    JOIN payouts p ON pl.payout_id = p.payout_id
    WHERE ol.line_status != 'DELIVERED'
       OR p.batch_date < r.release_scheduled_date;
""")

if not premature_table.empty:
    st.dataframe(premature_table, use_container_width=True)
    csv_prem = premature_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Premature Payouts (CSV)",
        data=csv_prem,
        file_name="premature_payout_disbursements.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Disbursements: 100% of payout lines satisfied delivery and hold maturity criteria.")
