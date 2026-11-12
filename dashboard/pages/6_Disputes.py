"""Disputes, Claims, and Chargebacks Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Disputes & Claims - SellerOps", page_icon="⚖️", layout="wide")
apply_theme()
db = get_database()

st.title("Disputes, Claims & Chargeback Protection")
st.markdown("Auditing 10,000 customer dispute claims, chargeback liabilities, and clawback enforcement.")

disp_metrics = db.query_df("""
    SELECT
        COUNT(*) as total_disputes,
        ROUND(SUM(disputed_amount), 2) as total_disputed_val,
        SUM(CASE WHEN status = 'RESOLVED_BUYER_FAVOR' THEN 1 ELSE 0 END) as buyer_won,
        SUM(CASE WHEN status = 'CHARGEBACK_LOST' THEN 1 ELSE 0 END) as cb_lost,
        ROUND(SUM(CASE WHEN status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as loss_rate
    FROM disputes;
""")
tot_d = disp_metrics["total_disputes"].iloc[0]
tot_val = disp_metrics["total_disputed_val"].iloc[0]
loss_r = disp_metrics["loss_rate"].iloc[0]

# Check Anomaly 4
ano4_df = db.query_df("""
    SELECT COUNT(*) as unclawbacked_count
    FROM disputes
    WHERE status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') AND clawback_applied = 0;
""")
unclawbacked = ano4_df["unclawbacked_count"].iloc[0]

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

col_reason, col_status = st.columns(2)

with col_reason:
    st.subheader("Root Cause Distribution")
    reason_df = db.query_df("""
        SELECT dispute_reason, COUNT(*) as count, ROUND(SUM(disputed_amount), 2) as exposure
        FROM disputes
        GROUP BY dispute_reason
        ORDER BY count DESC;
    """)
    fig_reason = px.bar(
        reason_df,
        x="count",
        y="dispute_reason",
        orientation="h",
        color="dispute_reason",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        labels={"count": "Dispute Count", "dispute_reason": "Reason Code"},
    )
    apply_plotly_white_layout(fig_reason)
    fig_reason.update_layout(showlegend=False)
    st.plotly_chart(fig_reason, use_container_width=True)

with col_status:
    st.subheader("Dispute Outcome Statuses")
    status_df = db.query_df("""
        SELECT status, COUNT(*) as count
        FROM disputes
        GROUP BY status;
    """)
    fig_st = px.pie(
        status_df,
        names="status",
        values="count",
        color="status",
        color_discrete_map={
            "RESOLVED_BUYER_FAVOR": COLORS["danger"],
            "CHARGEBACK_LOST": "#7F1D1D",
            "RESOLVED_SELLER_FAVOR": COLORS["success"],
            "UNDER_REVIEW": COLORS["warning"],
            "OPEN": COLORS["primary"],
        },
        hole=0.4,
    )
    apply_plotly_white_layout(fig_st)
    st.plotly_chart(fig_st, use_container_width=True)

st.markdown("---")
st.subheader("Dispute Records Explorer & Clawback Audit")

f1, f2, f3 = st.columns(3)
with f1:
    sel_reason = st.selectbox("Reason Filter", ["ALL"] + list(reason_df["dispute_reason"]))
with f2:
    sel_disp_status = st.selectbox("Outcome Status Filter", ["ALL"] + list(status_df["status"]))
with f3:
    unclawbacked_only = st.checkbox("Show Unclawbacked Losses Only (Anomaly 4)", value=False)

q = """
    SELECT
        d.dispute_id,
        d.order_id,
        d.seller_id,
        d.customer_id,
        d.dispute_date,
        d.dispute_reason,
        d.disputed_amount,
        d.status,
        d.resolution_date,
        CASE WHEN d.clawback_applied = 1 THEN 'YES' ELSE 'NO (BUG)' END as clawback_status
    FROM disputes d
    WHERE 1=1
"""
params = []
if sel_reason != "ALL":
    q += " AND d.dispute_reason = ?"
    params.append(sel_reason)
if sel_disp_status != "ALL":
    q += " AND d.status = ?"
    params.append(sel_disp_status)
if unclawbacked_only:
    q += " AND d.status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') AND d.clawback_applied = 0"

q += " ORDER BY d.disputed_amount DESC LIMIT 200;"

table_df = db.query_df(q, tuple(params))
st.dataframe(table_df, use_container_width=True)
