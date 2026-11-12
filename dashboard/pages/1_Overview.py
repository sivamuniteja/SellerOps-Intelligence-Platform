"""Executive Overview Console."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Executive Overview - SellerOps", page_icon="📊", layout="wide")
apply_theme()
db = get_database()

st.title("Executive Overview")
st.markdown("Macro-level marketplace performance, order lifecycles, and platform revenue metrics.")

# Top KPIs
kpi_query = """
    SELECT
        ROUND(SUM(gross_amount), 2) as total_gmv,
        COUNT(order_id) as total_orders,
        ROUND(AVG(gross_amount), 2) as aov
    FROM orders;
"""
kpi_df = db.query_df(kpi_query)
gmv = kpi_df["total_gmv"].iloc[0] or 0.0
orders = kpi_df["total_orders"].iloc[0] or 0
aov = kpi_df["aov"].iloc[0] or 0.0

comm_df = db.query_df("SELECT ROUND(SUM(commission_amount), 2) as total_comm FROM order_settlements;")
comm = comm_df["total_comm"].iloc[0] or 0.0

sla_df = db.query_df("SELECT ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as on_time_rate FROM fulfillments;")
on_time_rate = sla_df["on_time_rate"].iloc[0] or 0.0

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Gross Merchandise Value", f"${gmv:,.2f}", "Total Platform GMV")
with c2:
    render_metric_card("Total Orders", f"{orders:,}", f"AOV: ${aov:.2f}")
with c3:
    render_metric_card("Commission Revenue", f"${comm:,.2f}", f"Take Rate: {(comm/gmv*100):.2f}%")
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
            ROUND(SUM(gross_amount), 2) as monthly_gmv,
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
        SELECT l.category, ROUND(SUM(o.gross_amount), 2) as total_sales
        FROM orders o
        JOIN listings l ON o.listing_id = l.listing_id
        GROUP BY l.category
        ORDER BY total_sales DESC;
    """)
    fig_cat = px.bar(
        cat_df,
        x="total_sales",
        y="category",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"total_sales": "GMV ($)", "category": "Product Category"},
    )
    apply_plotly_white_layout(fig_cat)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_carrier:
    st.subheader("Carrier SLA Performance")
    carrier_df = db.query_df("""
        SELECT
            carrier,
            SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) as on_time,
            SUM(CASE WHEN sla_status = 'LATE' THEN 1 ELSE 0 END) as late
        FROM fulfillments
        WHERE carrier IS NOT NULL AND sla_status IN ('ON_TIME', 'LATE')
        GROUP BY carrier;
    """)
    fig_carrier = px.bar(
        carrier_df,
        x="carrier",
        y=["on_time", "late"],
        barmode="stack",
        color_discrete_sequence=[COLORS["success"], COLORS["danger"]],
        labels={"value": "Shipments", "carrier": "Logistics Partner"},
    )
    apply_plotly_white_layout(fig_carrier)
    st.plotly_chart(fig_carrier, use_container_width=True)
