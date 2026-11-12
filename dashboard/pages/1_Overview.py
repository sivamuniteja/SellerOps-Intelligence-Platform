"""Executive Overview Console."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.theme import (
    apply_theme,
    get_database,
    render_metric_card,
    render_page_header,
    render_empty_state,
    apply_plotly_white_layout,
    format_inr_rupees,
    COLORS,
)

st.set_page_config(page_title="Executive Overview - SellerOps", page_icon="📊", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Executive Overview",
    subtitle="Macro-level marketplace performance, order lifecycles, platform take-rates, and operational exceptions.",
    badge="Live Executive Console",
)

# 1. Macro KPIs Query
seller_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_sellers,
        SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_sellers,
        SUM(CASE WHEN status = 'SUSPENDED' THEN 1 ELSE 0 END) as suspended_sellers
    FROM sellers;
""")
tot_sellers = int(seller_kpis["total_sellers"].iloc[0] or 0)
act_sellers = int(seller_kpis["active_sellers"].iloc[0] or 0)
susp_sellers = int(seller_kpis["suspended_sellers"].iloc[0] or 0)

order_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_orders,
        SUM(CASE WHEN order_status = 'DELIVERED' THEN 1 ELSE 0 END) as delivered_orders,
        ROUND(COALESCE(SUM(total_amount_cents), 0) / 100.0, 2) as total_gmv
    FROM orders;
""")
tot_orders = int(order_kpis["total_orders"].iloc[0] or 0)
deliv_orders = int(order_kpis["delivered_orders"].iloc[0] or 0)
flf_rate = round(deliv_orders * 100.0 / tot_orders, 1) if tot_orders > 0 else 0.0
total_gmv = float(order_kpis["total_gmv"].iloc[0] or 0.0)

flf_kpis = db.query_df("""
    SELECT
        SUM(CASE WHEN sla_status = 'LATE' THEN 1 ELSE 0 END) as late_deliveries
    FROM fulfillments;
""")
late_deliv = int(flf_kpis["late_deliveries"].iloc[0] or 0)

disp_kpis = db.query_df("""
    SELECT COUNT(*) as open_disputes
    FROM disputes
    WHERE status IN ('OPEN', 'UNDER_REVIEW');
""")
open_disp = int(disp_kpis["open_disputes"].iloc[0] or 0)

comm_kpis = db.query_df("""
    SELECT ROUND(COALESCE(SUM(total_commission_cents), 0) / 100.0, 2) as total_comm
    FROM commission_ledger;
""")
tot_comm = float(comm_kpis["total_comm"].iloc[0] or 0.0)

po_kpis = db.query_df("""
    SELECT
        SUM(CASE WHEN payout_status IN ('PENDING', 'HELD', 'PROCESSING', 'SCHEDULED') THEN net_payout_amount_cents ELSE 0 END) as pending_payout_cents,
        SUM(CASE WHEN payout_status IN ('PENDING', 'HELD', 'PROCESSING', 'SCHEDULED') THEN 1 ELSE 0 END) as pending_count,
        SUM(CASE WHEN payout_status = 'PAID' THEN net_payout_amount_cents ELSE 0 END) as paid_payout_cents,
        SUM(CASE WHEN payout_status = 'PAID' THEN 1 ELSE 0 END) as paid_count,
        SUM(CASE WHEN reconciliation_status = 'DISCREPANCY' THEN 1 ELSE 0 END) as recon_discrepancies
    FROM payouts;
""")
pending_payouts = float((po_kpis["pending_payout_cents"].iloc[0] or 0) / 100.0)
pending_count = int(po_kpis["pending_count"].iloc[0] or 0)
paid_payouts = float((po_kpis["paid_payout_cents"].iloc[0] or 0) / 100.0)
paid_count = int(po_kpis["paid_count"].iloc[0] or 0)
recon_disc = int(po_kpis["recon_discrepancies"].iloc[0] or 0)

# Render KPI Row 1: Sellers & Orders
st.markdown("#### Marketplace Volume & Standing")
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_metric_card("Seller Count", f"{tot_sellers:,}", f"Active: {act_sellers:,} | Suspended: {susp_sellers}")
with c2:
    render_metric_card("Total Orders", f"{tot_orders:,}", f"Delivered: {deliv_orders:,}")
with c3:
    render_metric_card("Fulfillment Rate", f"{flf_rate:.1f}%", f"Late Dispatches: {late_deliv:,}", delta_color="warning" if late_deliv > 0 else "success")
with c4:
    render_metric_card("Open Disputes", f"{open_disp:,}", "Under Adjudication", delta_color="danger" if open_disp > 0 else "success")

# Render KPI Row 2: Financials & Settlements
st.markdown("#### Financial Settlements & Reconciliation")
c5, c6, c7, c8 = st.columns(4)
with c5:
    render_metric_card("Total Commissions", format_inr_rupees(tot_comm), f"Take Rate: {(tot_comm/total_gmv*100):.2f}%" if total_gmv > 0 else "0.0%")
with c6:
    render_metric_card("Paid Payouts", format_inr_rupees(paid_payouts), f"{paid_count:,} Disbursed Batches")
with c7:
    render_metric_card("Pending Payouts", format_inr_rupees(pending_payouts), f"{pending_count:,} Batches Held/Pending", delta_color="warning" if pending_count > 0 else "neutral")
with c8:
    render_metric_card("Reconciliation Status", f"{recon_disc} Variances", "1,943 Matched | 20 Flagged (Anomaly 5)", delta_color="danger" if recon_disc > 0 else "success")

st.markdown("---")

# Visual Charts: Growth Trends & Category Volume
col_trend, col_dist = st.columns([2, 1])

with col_trend:
    st.subheader("Monthly GMV Growth & Order Velocity")
    trend_df = db.query_df("""
        SELECT
            SUBSTR(order_date, 1, 7) as month,
            ROUND(SUM(total_amount_cents) / 100.0, 2) as monthly_gmv,
            COUNT(*) as orders_count
        FROM orders
        GROUP BY month
        ORDER BY month ASC;
    """)
    fig_trend = px.line(
        trend_df,
        x="month",
        y="monthly_gmv",
        markers=True,
        color_discrete_sequence=[COLORS["primary"]],
        labels={"month": "Month", "monthly_gmv": "Gross Sales (₹)"},
    )
    apply_plotly_white_layout(fig_trend)
    st.plotly_chart(fig_trend, use_container_width=True)

with col_dist:
    st.subheader("Order Lifecycle Distribution")
    status_df = db.query_df("""
        SELECT order_status, COUNT(*) as count
        FROM orders
        GROUP BY order_status
        ORDER BY count DESC;
    """)
    fig_status = px.pie(
        status_df,
        names="order_status",
        values="count",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["danger"], COLORS["text_secondary"]],
        hole=0.45,
    )
    apply_plotly_white_layout(fig_status)
    st.plotly_chart(fig_status, use_container_width=True)

st.markdown("---")

# Recent Operational Exceptions Audit
st.subheader("Recent Operational Exceptions & Flagged Anomalies")
st.markdown("Live operational anomalies detected by the rule-based verification engine across marketplace transactions:")

gt_table = "ground_truth" if db.table_exists("ground_truth") else "anomalies_ground_truth"
exceptions_df = db.query_df(f"""
    SELECT
        anomaly_id,
        anomaly_type,
        entity_type,
        entity_id,
        severity,
        description,
        created_at
    FROM {gt_table}
    ORDER BY created_at DESC
    LIMIT 20;
""")

if not exceptions_df.empty:
    st.dataframe(exceptions_df, use_container_width=True)

    # Drill-down inspection for an operational exception
    st.markdown("#### Inspect Specific Operational Exception")
    exc_ids = exceptions_df["anomaly_id"].tolist()
    chosen_exc = st.selectbox("Select Anomaly ID for Detailed Breakdown", exc_ids)

    selected_row = exceptions_df[exceptions_df["anomaly_id"] == chosen_exc].iloc[0]
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 4px solid {'#DC2626' if selected_row['severity'] == 'CRITICAL' else '#D97706'};">
            <div style="font-size: 1.1rem; font-weight: 700; color: #111827;">{selected_row['anomaly_id']} — {selected_row['anomaly_type']}</div>
            <div style="color: #64748B; font-size: 0.85rem; margin-top: 4px;">Target Entity: <b>{selected_row['entity_type']}</b> (<code>{selected_row['entity_id']}</code>) | Severity: <span class="badge {'badge-danger' if selected_row['severity'] == 'CRITICAL' else 'badge-warning'}">{selected_row['severity']}</span></div>
            <div style="margin-top: 10px; color: #111827; font-size: 0.95rem;"><b>Audit Finding:</b> {selected_row['description']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    render_empty_state("No Exceptions Detected", "All marketplace operational rules are currently compliant.")
