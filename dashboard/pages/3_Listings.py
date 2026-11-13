"""Product Listings and Catalog Console."""

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

st.set_page_config(page_title="Product Listings - SellerOps", page_icon="📦", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Product Listings & Catalog Management",
    subtitle="Auditing 20,000 product listings across pricing bands, inventory availability, and suspended seller violations.",
    badge="Catalog Audit",
)

# 1. Macro Catalog KPIs
stats_df = db.query_df("""
    SELECT
        COUNT(*) as total_listings,
        ROUND(AVG(price_cents) / 100.0, 2) as avg_price,
        SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_count,
        SUM(CASE WHEN status = 'OUT_OF_STOCK' THEN 1 ELSE 0 END) as oos_count
    FROM listings;
""")
total_l = int(stats_df["total_listings"].iloc[0] or 0)
avg_p = float(stats_df["avg_price"].iloc[0] or 0.0)
act_l = int(stats_df["active_count"].iloc[0] or 0)
oos_l = int(stats_df["oos_count"].iloc[0] or 0)

# Check Anomaly 3 breaches: Active listings under suspended sellers
ano3_df = db.query_df("""
    SELECT COUNT(*) as breach_count
    FROM listings l
    JOIN sellers s ON l.seller_id = s.seller_id
    WHERE s.status = 'SUSPENDED' AND l.status = 'ACTIVE';
""")
breaches = int(ano3_df["breach_count"].iloc[0] or 0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Listings", f"{total_l:,}", "Catalog SKUs")
with c2:
    render_metric_card("Active Listings", f"{act_l:,}", "Purchasable SKUs")
with c3:
    render_metric_card("Average Price", format_inr_rupees(avg_p), "Across 8 Categories")
with c4:
    render_metric_card("Out of Stock", f"{oos_l:,}", "Zero Inventory", delta_color="warning" if oos_l > 0 else "neutral")
with c5:
    render_metric_card("Suspension Breaches", f"{breaches}", "Active under Suspended (Anomaly 3)", delta_color="danger" if breaches > 0 else "success")

st.markdown("---")

# 2. Interactive Filter Controls
st.markdown("#### Filter Listings Catalog")
f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1, 1.5, 1.5])
with f_col1:
    all_categories = db.query_df("SELECT DISTINCT category FROM listings ORDER BY category;")["category"].tolist()
    selected_categories = st.multiselect("Category", all_categories, default=all_categories)
with f_col2:
    all_statuses = ["ACTIVE", "OUT_OF_STOCK", "SUSPENDED", "ARCHIVED"]
    selected_statuses = st.multiselect("Listing Status", all_statuses, default=all_statuses)
with f_col3:
    price_range = st.slider("Price Range (₹)", 0.0, 1000.0, (0.0, 1000.0), step=10.0)
with f_col4:
    search_query = st.text_input("🔍 Search Title, SKU, or Seller ID", placeholder="e.g. LIST- or SELL-000001")

# Fetch listings based on filters
query_where = []
if selected_categories:
    cat_in = ", ".join(f"'{c}'" for c in selected_categories)
    query_where.append(f"l.category IN ({cat_in})")
if selected_statuses:
    stat_in = ", ".join(f"'{s}'" for s in selected_statuses)
    query_where.append(f"l.status IN ({stat_in})")

min_cents = int(price_range[0] * 100)
max_cents = int(price_range[1] * 100)
query_where.append(f"l.price_cents >= {min_cents} AND l.price_cents <= {max_cents}")

where_clause = " WHERE " + " AND ".join(query_where) if query_where else ""

listings_df = db.query_df(f"""
    SELECT
        l.listing_id,
        l.seller_id,
        s.name as seller_name,
        s.status as seller_status,
        l.title as product_name,
        l.category,
        ROUND(l.price_cents / 100.0, 2) as price_inr,
        l.inventory_count as stock,
        l.status as listing_status,
        l.created_at
    FROM listings l
    JOIN sellers s ON l.seller_id = s.seller_id
    {where_clause}
    LIMIT 2000;
""")

if search_query.strip():
    q = search_query.strip().lower()
    listings_df = listings_df[
        listings_df["listing_id"].str.lower().str.contains(q)
        | listings_df["product_name"].str.lower().str.contains(q)
        | listings_df["seller_id"].str.lower().str.contains(q)
        | listings_df["seller_name"].str.lower().str.contains(q)
    ]

# 3. Category Distribution Charts
col_box, col_cat_dist = st.columns([3, 2])

with col_box:
    st.subheader("Price Range Distribution by Category (₹)")
    if not listings_df.empty:
        fig_box = px.box(
            listings_df.head(1000),
            x="category",
            y="price_inr",
            color="category",
            color_discrete_sequence=px.colors.qualitative.Plotly,
            labels={"price_inr": "Item Price (₹)", "category": "Product Category"},
        )
        apply_plotly_white_layout(fig_box)
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        render_empty_state("No Listings Match Filters", "Please adjust the filters above.")

with col_cat_dist:
    st.subheader("Catalog Density by Category")
    cat_density = db.query_df("""
        SELECT category, COUNT(*) as count
        FROM listings
        GROUP BY category
        ORDER BY count DESC;
    """)
    fig_bar = px.bar(
        cat_density,
        x="count",
        y="category",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"count": "Number of SKUs", "category": "Category"},
    )
    apply_plotly_white_layout(fig_bar)
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# 4. Master Listing Directory Table
st.subheader("Product Listing Directory")
if not listings_df.empty:
    display_cols = [
        "listing_id",
        "seller_id",
        "seller_name",
        "product_name",
        "category",
        "price_inr",
        "stock",
        "listing_status",
    ]
    st.dataframe(
        listings_df[display_cols].head(100),
        use_container_width=True,
    )
    csv_listings = listings_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Listings (CSV)",
        data=csv_listings,
        file_name="product_listings_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Listings Found", "Zero listings match current search and filter settings.")

st.markdown("---")

# 5. Anomaly 3 Active Breaches Inspection Table
st.subheader("⚠️ Critical Anomaly 3: Active Listings Under Suspended Sellers")
breach_details = db.query_df("""
    SELECT
        l.listing_id,
        l.seller_id,
        s.name as seller_name,
        s.status as seller_status,
        s.risk_score,
        l.title as product_name,
        l.category,
        ROUND(l.price_cents / 100.0, 2) as price_inr,
        l.inventory_count as stock,
        l.status as listing_status
    FROM listings l
    JOIN sellers s ON l.seller_id = s.seller_id
    WHERE s.status = 'SUSPENDED' AND l.status = 'ACTIVE';
""")

if not breach_details.empty:
    st.dataframe(breach_details, use_container_width=True)
    csv_breaches = breach_details.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Suspended Seller Breaches (CSV)",
        data=csv_breaches,
        file_name="suspended_seller_breaches.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Compliance: Zero active listings detected under suspended sellers.")

st.markdown("---")

# 6. Deep-Dive Drill-Down: Listing Detail & Sales History
st.subheader("🔍 Listing Deep-Dive & Sales Velocity")

if not listings_df.empty:
    listing_options = [
        f"{r['listing_id']} — {r['product_name'][:40]} ({format_inr_rupees(r['price_inr'])}, {r['listing_status']})"
        for r in listings_df.head(50).to_dict(orient="records")
    ]
    selected_listing_str = st.selectbox("Select Listing for Deep-Dive Audit", listing_options)
    selected_listing_id = selected_listing_str.split(" — ")[0]

    item_row = db.query_df(f"""
        SELECT 
            l.listing_id,
            l.seller_id,
            s.name as seller_name,
            s.status as seller_status,
            s.tier as seller_tier,
            s.rating as seller_rating,
            s.risk_score as seller_risk_score,
            l.title as product_name,
            l.category,
            ROUND(l.price_cents / 100.0, 2) as price_inr,
            l.inventory_count as stock,
            l.status as listing_status,
            l.created_at
        FROM listings l
        JOIN sellers s ON l.seller_id = s.seller_id
        WHERE l.listing_id = '{selected_listing_id}';
    """).iloc[0]

    c_i1, c_i2, c_i3, c_i4 = st.columns(4)
    with c_i1:
        render_metric_card("Product SKU", item_row["listing_id"], item_row["category"])
    with c_i2:
        render_metric_card("Price & Stock", format_inr_rupees(item_row['price_inr']), f"Units in Stock: {item_row['stock']}")
    with c_i3:
        render_metric_card(
            "Listing Status", 
            item_row["listing_status"], 
            f"Created: {item_row['created_at'][:10]}",
            delta_color="success" if item_row["listing_status"] == "ACTIVE" else "warning"
        )
    with c_i4:
        is_breach = item_row["seller_status"] == "SUSPENDED" and item_row["listing_status"] == "ACTIVE"
        render_metric_card(
            "Seller Status", 
            f"{item_row['seller_name']} ({item_row['seller_status']})", 
            f"Anomaly 3 Violation: {'YES 🚨' if is_breach else 'NO ✅'}",
            delta_color="danger" if is_breach else "success"
        )

    st.markdown(f"#### Order Sales History for `{selected_listing_id}`")
    sales_df = db.query_df(f"""
        SELECT 
            ol.order_line_id,
            ol.order_id,
            o.order_date,
            o.customer_id,
            ol.quantity,
            ROUND(ol.unit_price_cents / 100.0, 2) as unit_price_inr,
            ROUND(ol.gross_amount_cents / 100.0, 2) as line_gross_inr,
            ol.line_status
        FROM order_lines ol
        JOIN orders o ON ol.order_id = o.order_id
        WHERE ol.listing_id = '{selected_listing_id}'
        ORDER BY o.order_date DESC
        LIMIT 50;
    """)
    if not sales_df.empty:
        st.dataframe(sales_df, use_container_width=True)
    else:
        render_empty_state("No Direct Orders", "This SKU has not yet been ordered or appears in no settled order lines.")
else:
    render_empty_state("No Listing Selected", "Select or loosen filter criteria above.")
