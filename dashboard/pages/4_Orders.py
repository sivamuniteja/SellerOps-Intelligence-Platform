"""Order Operations and Multi-Seller Pipeline Console."""

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
    format_inr_rupees,
    COLORS,
)

st.set_page_config(page_title="Order Operations - SellerOps", page_icon="🛒", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Order Operations & Multi-Seller Pipeline",
    subtitle="Live tracking of 100,000 order transactions, multi-seller lines, split fulfillments, and customer sentiment.",
    badge="100,000 Orders",
)

# 1. Macro Order KPIs
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

# Multi-seller metric
ms_count = db.query_df("""
    SELECT COUNT(*) as multi_seller_orders
    FROM (
        SELECT order_id
        FROM order_lines
        GROUP BY order_id
        HAVING COUNT(DISTINCT seller_id) > 1
    );
""")
o_ms = int(ms_count["multi_seller_orders"].iloc[0] or 0)
ms_pct = round(o_ms * 100.0 / o_tot, 1) if o_tot > 0 else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Orders", f"{o_tot:,}", "Pipeline Total")
with c2:
    render_metric_card("Total GMV", format_inr_rupees(o_gmv), f"AOV: {format_inr_rupees(o_aov)}")
with c3:
    render_metric_card("Multi-Seller Orders", f"{o_ms:,}", f"{ms_pct}% Split Basket Rate")
with c4:
    render_metric_card("Cancellation Rate", f"{o_cr:.2f}%", "Pre-fulfillment", delta_color="warning" if o_cr > 2.0 else "neutral")
with c5:
    render_metric_card("Return Rate", f"{o_rr:.2f}%", "Post-delivery Returns", delta_color="danger" if o_rr > 3.0 else "neutral")

st.markdown("---")

# 2. Interactive Filter Controls
st.markdown("#### Filter Order Pipeline")
f1, f2, f3, f4 = st.columns([1, 1, 1.5, 1.5])
with f1:
    all_statuses = ["PLACED", "CONFIRMED", "PARTIALLY_SHIPPED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]
    selected_statuses = st.multiselect("Order Status", all_statuses, default=["CONFIRMED", "SHIPPED", "DELIVERED"])
with f2:
    pay_methods = db.query_df("SELECT DISTINCT payment_method FROM orders;")["payment_method"].tolist()
    selected_payment = st.multiselect("Payment Method", pay_methods, default=pay_methods)
with f3:
    amount_range = st.slider("Order Amount Range (₹)", 0.0, 3000.0, (0.0, 3000.0), step=25.0)
with f4:
    search_query = st.text_input("🔍 Search Order ID or Customer ID", placeholder="e.g. ORD-2026-000001 or CUST-005778")

# Fetch orders based on filters
query_where = []
if selected_statuses:
    stat_in = ", ".join(f"'{s}'" for s in selected_statuses)
    query_where.append(f"o.order_status IN ({stat_in})")
if selected_payment:
    pay_in = ", ".join(f"'{p}'" for p in selected_payment)
    query_where.append(f"o.payment_method IN ({pay_in})")

min_cents = int(amount_range[0] * 100)
max_cents = int(amount_range[1] * 100)
query_where.append(f"o.total_amount_cents >= {min_cents} AND o.total_amount_cents <= {max_cents}")

where_clause = " WHERE " + " AND ".join(query_where) if query_where else ""

orders_df = db.query_df(f"""
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        ROUND(o.total_amount_cents / 100.0, 2) as order_total_dollars,
        o.payment_method,
        o.order_status,
        COUNT(DISTINCT ol.seller_id) as seller_count,
        COUNT(ol.order_line_id) as line_count
    FROM orders o
    JOIN order_lines ol ON o.order_id = ol.order_id
    {where_clause}
    GROUP BY o.order_id
    ORDER BY o.order_date DESC
    LIMIT 1000;
""")

if search_query.strip():
    q = search_query.strip().lower()
    orders_df = orders_df[
        orders_df["order_id"].str.lower().str.contains(q)
        | orders_df["customer_id"].str.lower().str.contains(q)
    ]

# 3. Macro Pipeline Visuals
col_pay, col_status = st.columns(2)

with col_pay:
    st.subheader("Payment Method Volume Share (₹)")
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

# 4. Master Order Directory Table
st.subheader("Order Directory (with Multi-Seller Breakdown)")
if not orders_df.empty:
    display_cols = [
        "order_id",
        "customer_id",
        "order_date",
        "order_total_dollars",
        "order_status",
        "seller_count",
        "line_count",
        "payment_method",
    ]
    st.dataframe(
        orders_df[display_cols].head(100),
        use_container_width=True,
    )
    csv_orders = orders_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Orders (CSV)",
        data=csv_orders,
        file_name="orders_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Orders Match Filters", "Adjust your filters or clear search query above.")

st.markdown("---")

# 5. Deep-Dive Drill-Down: Detailed Order & Multi-Seller Line Breakdown
st.subheader("🔍 Order Deep-Dive & Multi-Seller Line Inspection")

if not orders_df.empty:
    order_options = [
        f"{r['order_id']} — {format_inr_rupees(r['order_total_dollars'])} ({r['order_status']}, {r['seller_count']} Sellers, {r['order_date'][:10]})"
        for r in orders_df.head(50).to_dict(orient="records")
    ]
    selected_order_str = st.selectbox("Select Order for Detailed Adjudication", order_options)
    selected_order_id = selected_order_str.split(" — ")[0]

    order_info = db.query_df(f"""
        SELECT 
            o.order_id,
            o.order_date,
            ROUND(o.total_amount_cents / 100.0, 2) as total_dollars,
            o.order_status,
            o.payment_method,
            c.customer_id,
            c.name as customer_name,
            c.email as customer_email,
            c.city || ', ' || c.state as customer_location
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_id = '{selected_order_id}';
    """).iloc[0]

    c_o1, c_o2, c_o3, c_o4 = st.columns(4)
    with c_o1:
        render_metric_card("Order ID", order_info["order_id"], f"Date: {order_info['order_date']}")
    with c_o2:
        render_metric_card("Customer", order_info["customer_name"], order_info["customer_location"])
    with c_o3:
        render_metric_card(
            "Total Amount", 
            format_inr_rupees(order_info['total_dollars']), 
            f"Payment: {order_info['payment_method']}"
        )
    with c_o4:
        render_metric_card(
            "Order Status", 
            order_info["order_status"], 
            "Lifecycle Verified",
            delta_color="success" if order_info["order_status"] == "DELIVERED" else "neutral"
        )

    tab_lines, tab_flf, tab_rev = st.tabs([
        "🛒 Multi-Seller Order Lines Breakdown",
        "🚚 Split Fulfillment Packages",
        "⭐ Customer Review & Feedback"
    ])

    with tab_lines:
        st.markdown(f"#### Order Lines for `{selected_order_id}`")
        lines_df = db.query_df(f"""
            SELECT 
                ol.order_line_id,
                ol.line_number,
                ol.seller_id,
                s.name as seller_name,
                s.tier as seller_tier,
                ol.listing_id,
                l.title as product_title,
                l.category,
                ol.quantity,
                ROUND(ol.unit_price_cents / 100.0, 2) as unit_price_dollars,
                ROUND(ol.gross_amount_cents / 100.0, 2) as line_gross_dollars,
                ol.line_status
            FROM order_lines ol
            JOIN sellers s ON ol.seller_id = s.seller_id
            JOIN listings l ON ol.listing_id = l.listing_id
            WHERE ol.order_id = '{selected_order_id}'
            ORDER BY ol.line_number ASC;
        """)
        if not lines_df.empty:
            st.dataframe(lines_df, use_container_width=True)
            # Arithmetic verification check
            lines_sum = lines_df["line_gross_dollars"].sum()
            variance = abs(lines_sum - order_info["total_dollars"])
            if variance < 0.01:
                st.success(f"✅ Exact Mathematical Consistency: Sum of order lines ({format_inr_rupees(lines_sum)}) matches order header total ({format_inr_rupees(order_info['total_dollars'])}).")
            else:
                st.error(f"🚨 Arithmetic Mismatch: Order lines sum ({format_inr_rupees(lines_sum)}) differs from header ({format_inr_rupees(order_info['total_dollars'])}) by {format_inr_rupees(variance)}!")
        else:
            render_empty_state("No Lines Found", "No child order lines recorded.")

    with tab_flf:
        st.markdown(f"#### Fulfillment Records for `{selected_order_id}`")
        flf_df = db.query_df(f"""
            SELECT 
                f.fulfillment_id,
                f.order_line_id,
                f.seller_id,
                s.name as seller_name,
                f.carrier,
                f.tracking_number,
                f.dispatched_at,
                f.expected_delivery_at,
                f.delivered_at,
                f.sla_status,
                f.transit_days
            FROM fulfillments f
            JOIN sellers s ON f.seller_id = s.seller_id
            WHERE f.order_id = '{selected_order_id}'
            ORDER BY f.dispatched_at ASC;
        """)
        if not flf_df.empty:
            st.dataframe(flf_df, use_container_width=True)
        else:
            render_empty_state("No Fulfillments", "This order is pending shipment or cancelled before dispatch.")

    with tab_rev:
        st.markdown(f"#### Customer Review for `{selected_order_id}`")
        rev_df = db.query_df(f"""
            SELECT 
                r.review_id,
                r.order_line_id,
                r.seller_id,
                s.name as seller_name,
                r.rating,
                r.comment
            FROM customer_reviews r
            JOIN sellers s ON r.seller_id = s.seller_id
            WHERE r.order_id = '{selected_order_id}';
        """)
        if not rev_df.empty:
            for _, r in rev_df.iterrows():
                stars = "★" * int(r["rating"]) + "☆" * (5 - int(r["rating"]))
                st.markdown(
                    f"""
                    <div class="metric-card" style="margin-bottom: 12px;">
                        <div style="font-size: 1.1rem; color: #D97706; margin-bottom: 4px;">{stars} ({r['rating']} / 5)</div>
                        <div style="color: #111827; font-weight: 500; margin-bottom: 6px;">"{r['comment']}"</div>
                        <div style="font-size: 0.85rem; color: #64748B;">Seller: {r['seller_name']} ({r['seller_id']}) | Review ID: {r['review_id']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            render_empty_state("No Customer Review", "Customer has not submitted a review for this order.")
else:
    render_empty_state("No Order Selected", "Select or loosen filter criteria above.")
