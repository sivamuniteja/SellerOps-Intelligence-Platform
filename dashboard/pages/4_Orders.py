"""Order Operations and Lifecycle Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Order Operations - SellerOps", page_icon="🛒", layout="wide")
apply_theme()
db = get_database()

st.title("Order Operations & Pipeline")
st.markdown("Live tracking of 100,000 order transactions, lifecycle states, and payment flows.")

# Top KPIs
order_metrics = db.query_df("""
    SELECT
        COUNT(*) as total_orders,
        ROUND(SUM(gross_amount), 2) as total_gmv,
        ROUND(AVG(gross_amount), 2) as aov,
        ROUND(SUM(CASE WHEN order_status = 'CANCELLED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cancel_rate,
        ROUND(SUM(CASE WHEN order_status = 'RETURNED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as return_rate
    FROM orders;
""")
o_tot = order_metrics["total_orders"].iloc[0]
o_gmv = order_metrics["total_gmv"].iloc[0]
o_aov = order_metrics["aov"].iloc[0]
o_cr = order_metrics["cancel_rate"].iloc[0]
o_rr = order_metrics["return_rate"].iloc[0]

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

col_pay, col_status = st.columns(2)

with col_pay:
    st.subheader("Payment Method Share")
    pay_df = db.query_df("""
        SELECT payment_method, COUNT(*) as orders_count, ROUND(SUM(gross_amount), 2) as volume
        FROM orders
        GROUP BY payment_method;
    """)
    fig_pay = px.pie(
        pay_df,
        names="payment_method",
        values="volume",
        color_discrete_sequence=px.colors.qualitative.Safe,
        hole=0.4,
    )
    apply_plotly_white_layout(fig_pay)
    st.plotly_chart(fig_pay, use_container_width=True)

with col_status:
    st.subheader("Orders Lifecycle Flow")
    status_flow = db.query_df("""
        SELECT order_status, COUNT(*) as count
        FROM orders
        GROUP BY order_status
        ORDER BY count DESC;
    """)
    fig_flow = px.bar(
        status_flow,
        x="order_status",
        y="count",
        color="order_status",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["danger"], COLORS["text_secondary"]],
    )
    apply_plotly_white_layout(fig_flow)
    fig_flow.update_layout(showlegend=False)
    st.plotly_chart(fig_flow, use_container_width=True)

st.markdown("---")
st.subheader("Live Order Explorer")

f1, f2, f3 = st.columns(3)
with f1:
    status_options = ["ALL"] + sorted(list(status_flow["order_status"]))
    sel_st = st.selectbox("Order Status Filter", status_options)
with f2:
    sel_pay = st.selectbox("Payment Method Filter", ["ALL"] + sorted(list(pay_df["payment_method"])))
with f3:
    order_search = st.text_input("Search Order ID or Customer ID", "")

q = """
    SELECT
        o.order_id,
        o.order_date,
        o.customer_id,
        c.name as customer_name,
        o.seller_id,
        o.listing_id,
        o.quantity,
        o.unit_price,
        o.gross_amount,
        o.payment_method,
        o.order_status
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE 1=1
"""
params = []
if sel_st != "ALL":
    q += " AND o.order_status = ?"
    params.append(sel_st)
if sel_pay != "ALL":
    q += " AND o.payment_method = ?"
    params.append(sel_pay)
if order_search:
    q += " AND (o.order_id LIKE ? OR o.customer_id LIKE ?)"
    params.extend([f"%{order_search}%", f"%{order_search}%"])

q += " ORDER BY o.order_date DESC LIMIT 200;"

orders_table = db.query_df(q, tuple(params))
st.dataframe(orders_table, use_container_width=True)
