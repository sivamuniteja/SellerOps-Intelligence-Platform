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
    apply_plotly_white_layout,
    COLORS,
)

st.set_page_config(page_title="Executive Overview - SellerOps", page_icon="📊", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Executive Overview",
    subtitle="Macro-level marketplace performance, order lifecycles, and platform revenue metrics.",
    badge="Live Metrics",
)

# Top KPIs
kpi_query = """
    SELECT
        ROUND(COALESCE(SUM(total_amount_cents), 0) / 100.0, 2) as total_gmv,
        COUNT(order_id) as total_orders,
        ROUND(COALESCE(AVG(total_amount_cents), 0) / 100.0, 2) as aov
    FROM orders;
"""
kpi_df = db.query_df(kpi_query)
gmv = float(kpi_df["total_gmv"].iloc[0] or 0.0)
orders = int(kpi_df["total_orders"].iloc[0] or 0)
aov = float(kpi_df["aov"].iloc[0] or 0.0)

comm_df = db.query_df("SELECT ROUND(COALESCE(SUM(total_commission_cents), 0) / 100.0, 2) as total_comm FROM commission_ledger;")
comm = float(comm_df["total_comm"].iloc[0] or 0.0)

sla_df = db.query_df("SELECT ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as on_time_rate FROM fulfillments;")
on_time_rate = float(sla_df["on_time_rate"].iloc[0] or 0.0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Gross Merchandise Value", f"${gmv:,.2f}", "Total Platform GMV")
with c2:
    render_metric_card("Total Orders", f"{orders:,}", f"AOV: ${aov:.2f}")
with c3:
    render_metric_card("Commission Revenue", f"${comm:,.2f}", f"Take Rate: {(comm/gmv*100):.2f}%" if gmv > 0 else "0.0%")
with c4:
    render_metric_card("Fulfillment On-Time", f"{on_time_rate:.1f}%", "SLA Target: 96.0%")
with c5:
    render_metric_card("Active Sellers", f"{db.row_count('sellers'):,}", "2,000 Total Sellers")

st.markdown("---")

# Charts row 1: Monthly GMV trend & Order Status breakdown
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Monthly GMV Growth Trend")
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
        labels={"month": "Month", "monthly_gmv": "Gross Sales ($)"},
    )
    apply_plotly_white_layout(fig_trend)
    st.plotly_chart(fig_trend, use_container_width=True)

with col_right:
    st.subheader("Order Status Distribution")
    status_df = db.query_df("""
        SELECT order_status, COUNT(*) as count
        FROM orders
        GROUP BY order_status;
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

# Charts row 2: Category volume & SLA carrier comparison
col_cat, col_carrier = st.columns(2)

with col_cat:
    st.subheader("Sales Volume by Category")
    cat_df = db.query_df("""
        SELECT l.category, ROUND(SUM(ol.gross_amount_cents) / 100.0, 2) as total_sales
        FROM order_lines ol
        JOIN listings l ON ol.listing_id = l.listing_id
        GROUP BY l.category
        ORDER BY total_sales DESC;
    """)
    fig_cat = px.bar(
        cat_df,
        x="total_sales",
        y="category",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"category": "Category", "total_sales": "Gross Sales ($)"},
    )
    apply_plotly_white_layout(fig_cat)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_carrier:
    st.subheader("Carrier On-Time Delivery Rate (%)")
    carrier_df = db.query_df("""
        SELECT
            carrier,
            ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as on_time_pct,
            COUNT(*) as total_deliveries
        FROM fulfillments
        WHERE carrier IS NOT NULL
        GROUP BY carrier
        ORDER BY on_time_pct DESC;
    """)
    fig_carrier = px.bar(
        carrier_df,
        x="carrier",
        y="on_time_pct",
        color="on_time_pct",
        color_continuous_scale=[[0, COLORS["warning"]], [1, COLORS["success"]]],
        labels={"carrier": "Logistics Carrier", "on_time_pct": "On-Time Rate (%)"},
    )
    apply_plotly_white_layout(fig_carrier)
    st.plotly_chart(fig_carrier, use_container_width=True)

st.markdown("---")

# Recent High-Value Orders
st.subheader("Recent High-Value Order Transactions")
orders_sample = db.query_df("""
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        ROUND(o.total_amount_cents / 100.0, 2) as amount_dollars,
        o.payment_method,
        o.order_status
    FROM orders o
    ORDER BY o.total_amount_cents DESC
    LIMIT 25;
""")
st.dataframe(orders_sample, use_container_width=True)

csv_data = orders_sample.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download Recent Orders (CSV)",
    data=csv_data,
    file_name="recent_orders.csv",
    mime="text/csv",
)
