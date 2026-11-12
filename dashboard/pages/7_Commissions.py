"""Commission Engine and Platform Revenue Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Commissions Engine - SellerOps", page_icon="💰", layout="wide")
apply_theme()
db = get_database()

st.title("Seller Commissions & Platform Revenue")
st.markdown("Auditing category-level take rates, tier fee discounts, fixed fees, and duplicate commission flags.")

comm_metrics = db.query_df("""
    SELECT
        ROUND(SUM(gross_amount), 2) as total_gross,
        ROUND(SUM(commission_amount), 2) as total_comm,
        ROUND(AVG(commission_rate) * 100.0, 2) as avg_rate,
        ROUND(SUM(commission_amount) * 100.0 / SUM(gross_amount), 2) as effective_take_rate
    FROM order_settlements;
""")
tot_comm = comm_metrics["total_comm"].iloc[0]
take_rate = comm_metrics["effective_take_rate"].iloc[0]
avg_rate = comm_metrics["avg_rate"].iloc[0]

# Check Anomaly 2: Double commission
ano2_df = db.query_df("""
    SELECT COUNT(*) as double_comm_count
    FROM order_settlements
    WHERE commission_amount > (gross_amount * commission_rate * 1.5);
""")
double_comm = ano2_df["double_comm_count"].iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Commission Revenue", f"${tot_comm:,.2f}", "Total Net Platform Fees")
with c2:
    render_metric_card("Effective Take Rate", f"{take_rate:.2f}%", "Blended Platform Rate")
with c3:
    render_metric_card("Average Category Rate", f"{avg_rate:.2f}%", "Base Category Schedule")
with c4:
    render_metric_card("Fixed Fee Per Order", "$0.30", "Transaction Processing")
with c5:
    render_metric_card("Duplicate Charges", f"{double_comm}", "Anomaly 2 Breaches", delta_color="danger")

st.markdown("---")

col_cat, col_scatter = st.columns(2)

with col_cat:
    st.subheader("Effective Take Rate by Category (%)")
    cat_take_df = db.query_df("""
        SELECT
            l.category,
            ROUND(SUM(s.commission_amount) * 100.0 / SUM(s.gross_amount), 2) as cat_take_rate,
            ROUND(SUM(s.commission_amount), 2) as comm_total
        FROM order_settlements s
        JOIN orders o ON s.order_id = o.order_id
        JOIN listings l ON o.listing_id = l.listing_id
        GROUP BY l.category
        ORDER BY cat_take_rate DESC;
    """)
    fig_cat_take = px.bar(
        cat_take_df,
        x="cat_take_rate",
        y="category",
        orientation="h",
        text="cat_take_rate",
        color="cat_take_rate",
        color_continuous_scale=["#93C5FD", COLORS["primary"]],
        labels={"cat_take_rate": "Effective Take Rate (%)", "category": "Product Category"},
    )
    fig_cat_take.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    apply_plotly_white_layout(fig_cat_take)
    fig_cat_take.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_cat_take, use_container_width=True)

with col_scatter:
    st.subheader("Commission vs Gross Order Amount ($)")
    sample_comm = db.query_df("""
        SELECT gross_amount, commission_amount, commission_rate
        FROM order_settlements
        LIMIT 1000;
    """)
    fig_scatter = px.scatter(
        sample_comm,
        x="gross_amount",
        y="commission_amount",
        color_discrete_sequence=[COLORS["primary"]],
        opacity=0.6,
        labels={"gross_amount": "Order Gross Amount ($)", "commission_amount": "Total Commission ($)"},
    )
    apply_plotly_white_layout(fig_scatter)
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")
st.subheader("Commission Settlement Ledger")

f1, f2 = st.columns(2)
with f1:
    show_duplicates_only = st.checkbox("Show Double Commission Anomalies Only (Anomaly 2)", value=False)
with f2:
    search_order = st.text_input("Search Settlement ID or Order ID", "")

q = """
    SELECT
        s.settlement_id,
        s.order_id,
        s.seller_id,
        s.gross_amount,
        ROUND(s.commission_rate * 100.0, 2) as rate_pct,
        s.commission_amount,
        s.reserve_amount,
        s.net_seller_amount,
        CASE
            WHEN s.commission_amount > (s.gross_amount * s.commission_rate * 1.5) THEN 'DOUBLE_FEE_ALERT'
            ELSE 'NORMAL'
        END as audit_flag
    FROM order_settlements s
    WHERE 1=1
"""
params = []
if show_duplicates_only:
    q += " AND s.commission_amount > (s.gross_amount * s.commission_rate * 1.5)"
if search_order:
    q += " AND (s.settlement_id LIKE ? OR s.order_id LIKE ?)"
    params.extend([f"%{search_order}%", f"%{search_order}%"])

q += " ORDER BY s.commission_amount DESC LIMIT 200;"

table_df = db.query_df(q, tuple(params))
st.dataframe(table_df, use_container_width=True)
