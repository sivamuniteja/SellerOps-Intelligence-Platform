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
    COLORS,
)

st.set_page_config(page_title="Product Listings - SellerOps", page_icon="📦", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Product Listings & Catalog Management",
    subtitle="Auditing 20,000 product listings across pricing bands, category takes, and seller suspensions.",
    badge="Catalog Audit",
)

# High level KPIs
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

# Check Anomaly 3 breaches
ano3_df = db.query_df("""
    SELECT COUNT(*) as breach_count
    FROM listings l
    JOIN sellers s ON l.seller_id = s.seller_id
    WHERE s.status = 'SUSPENDED' AND l.status = 'ACTIVE';
""")
breaches = int(ano3_df["breach_count"].iloc[0] or 0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Listings", f"{total_l:,}", "Catalog Size")
with c2:
    render_metric_card("Active Listings", f"{act_l:,}", "Ready to Buy")
with c3:
    render_metric_card("Average Price", f"${avg_p:.2f}", "Across 8 Categories")
with c4:
    render_metric_card("Out of Stock", f"{oos_l:,}", "Zero Inventory")
with c5:
    render_metric_card("Suspension Breaches", f"{breaches}", "Active under Suspended Sellers (Anomaly 3)", delta_color="danger")

st.markdown("---")

# Category and Status Filters
f_col1, f_col2 = st.columns(2)
with f_col1:
    categories = db.query_df("SELECT DISTINCT category FROM listings ORDER BY category;")["category"].tolist()
    selected_categories = st.multiselect("Filter Product Categories", categories, default=categories)
with f_col2:
    statuses = ["ACTIVE", "OUT_OF_STOCK", "SUSPENDED", "ARCHIVED"]
    selected_statuses = st.multiselect("Filter Listing Status", statuses, default=statuses)

col_box, col_cat_dist = st.columns([3, 2])

with col_box:
    st.subheader("Price Range Distribution by Category ($)")
    sample_listings = db.query_df("""
        SELECT category, ROUND(price_cents / 100.0, 2) as price_dollars, inventory_count, status
        FROM listings
        LIMIT 5000;
    """)
    filtered_listings = sample_listings[
        (sample_listings["category"].isin(selected_categories))
        & (sample_listings["status"].isin(selected_statuses))
    ]

    if not filtered_listings.empty:
        fig_box = px.box(
            filtered_listings,
            x="category",
            y="price_dollars",
            color="category",
            color_discrete_sequence=px.colors.qualitative.Plotly,
            labels={"price_dollars": "Item Price ($)", "category": "Product Category"},
        )
        apply_plotly_white_layout(fig_box)
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        render_empty_state("No Listings Match Filters", "Please select at least one category and status.")

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

# Anomaly 3 Active Breaches Inspection Table
st.subheader("⚠️ Critical Exception Audit: Active Listings Under Suspended Sellers")
breach_details = db.query_df("""
    SELECT
        l.listing_id,
        l.title as listing_title,
        l.category,
        ROUND(l.price_cents / 100.0, 2) as price_dollars,
        l.status as listing_status,
        s.seller_id,
        s.name as seller_name,
        s.status as seller_status,
        s.risk_score
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
