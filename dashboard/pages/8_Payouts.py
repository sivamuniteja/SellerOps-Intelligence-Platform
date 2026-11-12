"""Payout Batches and Disbursement Operations Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Payout Batches - SellerOps", page_icon="💳", layout="wide")
apply_theme()
db = get_database()

st.title("Seller Payout Batches & Disbursements")
st.markdown("Auditing net payout disbursements, rolling reserve holds, eligibility rules, and disbursement cycles.")

payout_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_batches,
        ROUND(SUM(gross_sales), 2) as total_gross_settled,
        ROUND(SUM(total_reserve_held), 2) as total_reserve_held,
        ROUND(SUM(net_payout_amount), 2) as total_net_disbursed
    FROM payout_batches;
""")
tot_b = payout_kpis["total_batches"].iloc[0]
tot_net = payout_kpis["total_net_disbursed"].iloc[0]
tot_res = payout_kpis["total_reserve_held"].iloc[0]

# Check Anomaly 1: Premature payouts
ano1_df = db.query_df("""
    SELECT COUNT(*) as premature_count
    FROM payout_lines pl
    JOIN orders o ON pl.order_id = o.order_id
    JOIN order_settlements s ON pl.order_id = s.order_id
    JOIN payout_batches pb ON pl.payout_id = pb.payout_id
    WHERE o.order_status != 'DELIVERED' OR pb.batch_date < s.reserve_release_date;
""")
premature = ano1_df["premature_count"].iloc[0]

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

col_status, col_tier = st.columns(2)

with col_status:
    st.subheader("Payout Batch Status Breakdown")
    status_df = db.query_df("""
        SELECT payout_status, COUNT(*) as count, ROUND(SUM(net_payout_amount), 2) as volume
        FROM payout_batches
        GROUP BY payout_status;
    """)
    fig_st = px.pie(
        status_df,
        names="payout_status",
        values="volume",
        color="payout_status",
        color_discrete_map={
            "PAID": COLORS["success"],
            "HELD": COLORS["warning"],
            "SCHEDULED": COLORS["primary"],
            "PROCESSING": "#60A5FA",
            "FAILED": COLORS["danger"],
        },
        hole=0.4,
    )
    apply_plotly_white_layout(fig_st)
    st.plotly_chart(fig_st, use_container_width=True)

with col_tier:
    st.subheader("Disbursement Volume by Seller Tier ($)")
    tier_payout = db.query_df("""
        SELECT s.tier, ROUND(SUM(pb.net_payout_amount), 2) as net_payout
        FROM payout_batches pb
        JOIN sellers s ON pb.seller_id = s.seller_id
        GROUP BY s.tier
        ORDER BY net_payout DESC;
    """)
    fig_tp = px.bar(
        tier_payout,
        x="tier",
        y="net_payout",
        color="tier",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["text_secondary"], COLORS["warning"], COLORS["danger"]],
        labels={"net_payout": "Net Disbursed ($)", "tier": "Seller Tier"},
    )
    apply_plotly_white_layout(fig_tp)
    fig_tp.update_layout(showlegend=False)
    st.plotly_chart(fig_tp, use_container_width=True)

st.markdown("---")
st.subheader("Payout Batches Explorer & Premature Payout Audit")

f1, f2 = st.columns(2)
with f1:
    show_premature_only = st.checkbox("Show Premature Disbursements Only (Anomaly 1)", value=False)
with f2:
    search_batch = st.text_input("Search Payout ID or Seller ID", "")

if show_premature_only:
    q = """
        SELECT
            pl.line_id,
            pl.payout_id,
            pl.order_id,
            pb.seller_id,
            pb.batch_date,
            s.reserve_release_date,
            o.order_status,
            pl.order_amount,
            pl.net_line_amount,
            'PREMATURE_PAYOUT_DETECTED' as audit_alert
        FROM payout_lines pl
        JOIN orders o ON pl.order_id = o.order_id
        JOIN order_settlements s ON pl.order_id = s.order_id
        JOIN payout_batches pb ON pl.payout_id = pb.payout_id
        WHERE o.order_status != 'DELIVERED' OR pb.batch_date < s.reserve_release_date
        ORDER BY pl.net_line_amount DESC LIMIT 200;
    """
    table_df = db.query_df(q)
else:
    q = """
        SELECT
            p.payout_id,
            p.seller_id,
            s.name as seller_name,
            s.tier as seller_tier,
            p.batch_date,
            p.total_orders_count,
            p.gross_sales,
            p.total_commission,
            p.total_reserve_held,
            p.net_payout_amount,
            p.payout_status,
            p.reconciliation_status
        FROM payout_batches p
        JOIN sellers s ON p.seller_id = s.seller_id
        WHERE 1=1
    """
    params = []
    if search_batch:
        q += " AND (p.payout_id LIKE ? OR p.seller_id LIKE ?)"
        params.extend([f"%{search_batch}%", f"%{search_batch}%"])
    q += " ORDER BY p.batch_date DESC LIMIT 200;"
    table_df = db.query_df(q, tuple(params))

st.dataframe(table_df, use_container_width=True)
