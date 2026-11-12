"""Order Operations and Lifecycle Console."""

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

st.set_page_config(page_title="Order Operations - SellerOps", page_icon="🛒", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Order Operations & Pipeline",
    subtitle="Live tracking of 100,000 order transactions, multi-seller lines, lifecycle states, and payment flows.",
    badge="100,000 Orders",
)

# Top KPIs
order_metrics = db.query_df("""
    SELECT
        COUNT(*) as total_orders,
        ROUND(COALESCE(SUM(total_amount_cents), 0) / 100.0, 2) as total_gmv,
        ROUND(COALESCE(AVG(total_amount_cents), 0) / 100.0, 2) as aov,
        ROUND(SUM(CASE WHEN order_status = 'CANCELLED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cancel_rate,
        ROUND(SUM(CASE WHEN order_status = 'RETURNED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as return_rate
    FROM orders;
""")
o_tot = int(order_metrics["total_orders"].iloc[0] or 0)
o_gmv = float(order_metrics["total_gmv"].iloc[0] or 0.0)
o_aov = float(order_metrics["aov"].iloc[0] or 0.0)
o_cr = float(order_metrics["cancel_rate"].iloc[0] or 0.0)
o_rr = float(order_metrics["return_rate"].iloc[0] or 0.0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Orders", f"{o_tot:,}", "Pipeline Total")
with c2:
    render_metric_card("Total GMV", f"${o_gmv:,.2f}", "Gross Sales")
with c3:
    render_metric_card("Average Order Value", f"${o_aov:.2f}", "Basket Size")
with c4:
    render_metric_card("Cancellation Rate", f"{o_cr:.2f}%", "Target: < 2.50%")
with c5:
    render_metric_card("Return Rate", f"{o_rr:.2f}%", "Within Return Window")

st.markdown("---")

# Filter Controls
f1, f2 = st.columns([1, 1])
with f1:
    statuses = ["PLACED", "CONFIRMED", "PARTIALLY_SHIPPED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
    selected_statuses = st.multiselect("Filter Order Lifecycle Status", statuses, default=statuses)
with f2:
    pay_methods = db.query_df("SELECT DISTINCT payment_method FROM orders;")["payment_method"].tolist()
    selected_payment = st.multiselect("Filter Payment Method", pay_methods, default=pay_methods)

col_pay, col_status = st.columns(2)

with col_pay:
    st.subheader("Payment Method Volume Share ($)")
    pay_df = db.query_df("""
        SELECT payment_method, COUNT(*) as orders_count, ROUND(SUM(total_amount_cents) / 100.0, 2) as volume
        FROM orders
        GROUP BY payment_method
        ORDER BY volume DESC;
    """)
    filtered_pay = pay_df[pay_df["payment_method"].isin(selected_payment)]
    if not filtered_pay.empty:
        fig_pay = px.pie(
            filtered_pay,
            names="payment_method",
            values="volume",
            color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["danger"]],
            hole=0.45,
        )
        apply_plotly_white_layout(fig_pay)
        st.plotly_chart(fig_pay, use_container_width=True)
    else:
        render_empty_state("No Payment Data", "Select at least one payment method.")

with col_status:
    st.subheader("Order Counts by Lifecycle Status")
    status_df = db.query_df("""
        SELECT order_status, COUNT(*) as order_count
        FROM orders
        GROUP BY order_status
        ORDER BY order_count DESC;
    """)
    filtered_status = status_df[status_df["order_status"].isin(selected_statuses)]
    if not filtered_status.empty:
        fig_status = px.bar(
            filtered_status,
            x="order_status",
            y="order_count",
            color="order_status",
            color_discrete_sequence=px.colors.qualitative.Plotly,
            labels={"order_status": "Lifecycle State", "order_count": "Orders"},
        )
        apply_plotly_white_layout(fig_status)
        st.plotly_chart(fig_status, use_container_width=True)
    else:
        render_empty_state("No Status Data", "Select at least one lifecycle status.")

st.markdown("---")

# Multi-Seller Order Lines Inspection
st.subheader("Multi-Seller Order Lines Sample")
order_lines_sample = db.query_df("""
    SELECT
        ol.order_line_id,
        ol.order_id,
        ol.seller_id,
        ol.listing_id,
        ol.quantity,
        ROUND(ol.unit_price_cents / 100.0, 2) as unit_price_dollars,
        ROUND(ol.gross_amount_cents / 100.0, 2) as gross_dollars,
        ol.line_status
    FROM order_lines ol
    LIMIT 50;
""")
st.dataframe(order_lines_sample, use_container_width=True)

csv_orders = order_lines_sample.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download Sample Order Lines (CSV)",
    data=csv_orders,
    file_name="sample_order_lines.csv",
    mime="text/csv",
)
