"""Disputes, Claims, and Chargebacks Console."""

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

st.set_page_config(page_title="Disputes & Claims - SellerOps", page_icon="⚖️", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Disputes, Claims & Chargeback Protection",
    subtitle="Auditing 10,000 customer dispute claims, chargeback liabilities, and clawback enforcement.",
    badge="10,000 Disputes",
)

# High level KPIs
disp_metrics = db.query_df("""
    SELECT
        COUNT(*) as total_disputes,
        ROUND(COALESCE(SUM(disputed_amount_cents), 0) / 100.0, 2) as total_disputed_val,
        SUM(CASE WHEN status = 'RESOLVED_BUYER_FAVOR' THEN 1 ELSE 0 END) as buyer_won,
        SUM(CASE WHEN status = 'CHARGEBACK_LOST' THEN 1 ELSE 0 END) as cb_lost,
        ROUND(SUM(CASE WHEN status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as loss_rate
    FROM disputes;
""")
tot_d = int(disp_metrics["total_disputes"].iloc[0] or 0)
tot_val = float(disp_metrics["total_disputed_val"].iloc[0] or 0.0)
loss_r = float(disp_metrics["loss_rate"].iloc[0] or 0.0)

# Check Anomaly 4: Unclawbacked disputes
ano4_df = db.query_df("""
    SELECT COUNT(*) as unclawbacked_count
    FROM disputes
    WHERE status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') AND clawback_applied = 0;
""")
unclawbacked = int(ano4_df["unclawbacked_count"].iloc[0] or 0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Disputes", f"{tot_d:,}", "Dispute Volume")
with c2:
    render_metric_card("Total Disputed Value", f"${tot_val:,.2f}", "Claims Exposure")
with c3:
    render_metric_card("Platform Loss Rate", f"{loss_r:.1f}%", "Buyer Favor / CB Lost")
with c4:
    render_metric_card("Dispute Frequency", "10.0%", "Per 100k Orders")
with c5:
    render_metric_card("Unclawbacked Claims", f"{unclawbacked}", "Anomaly 4 Violations", delta_color="danger")

st.markdown("---")

# Filter Controls
col_reason, col_status = st.columns(2)

with col_reason:
    st.subheader("Dispute Claim Reasons Breakdown")
    reason_df = db.query_df("""
        SELECT dispute_reason, COUNT(*) as count, ROUND(SUM(disputed_amount_cents) / 100.0, 2) as total_val
        FROM disputes
        GROUP BY dispute_reason
        ORDER BY count DESC;
    """)
    fig_reason = px.bar(
        reason_df,
        x="count",
        y="dispute_reason",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"count": "Number of Disputes", "dispute_reason": "Claim Reason"},
    )
    apply_plotly_white_layout(fig_reason)
    st.plotly_chart(fig_reason, use_container_width=True)

with col_status:
    st.subheader("Dispute Adjudication Outcomes")
    outcome_df = db.query_df("""
        SELECT status, COUNT(*) as count
        FROM disputes
        GROUP BY status
        ORDER BY count DESC;
    """)
    fig_outcome = px.pie(
        outcome_df,
        names="status",
        values="count",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["danger"], COLORS["text_secondary"]],
        hole=0.45,
    )
    apply_plotly_white_layout(fig_outcome)
    st.plotly_chart(fig_outcome, use_container_width=True)

st.markdown("---")

# Anomaly 4 Unclawbacked Disputes Table
st.subheader("⚠️ Unclawbacked Dispute Violations (Anomaly 4: Lost Claims Without Payout Deduction)")
unclawbacked_table = db.query_df("""
    SELECT
        d.dispute_id,
        d.order_id,
        d.order_line_id,
        d.seller_id,
        d.customer_id,
        d.dispute_date,
        d.dispute_reason,
        ROUND(d.disputed_amount_cents / 100.0, 2) as disputed_dollars,
        d.status as dispute_status,
        d.clawback_applied
    FROM disputes d
    WHERE d.status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST')
      AND d.clawback_applied = 0;
""")

if not unclawbacked_table.empty:
    st.dataframe(unclawbacked_table, use_container_width=True)
    csv_disp = unclawbacked_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Unclawbacked Disputes Audit (CSV)",
        data=csv_disp,
        file_name="unclawbacked_disputes.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Settlement: 100% of lost disputes have been clawed back.")
