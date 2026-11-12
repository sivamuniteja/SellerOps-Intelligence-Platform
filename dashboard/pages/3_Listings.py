"""Product Listings and Catalog Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Product Listings - SellerOps", page_icon="📦", layout="wide")
apply_theme()
db = get_database()

st.title("Product Listings & Catalog Management")
st.markdown("Auditing 20,000 product listings across pricing bands, category takes, and seller suspensions.")

# High level KPIs
stats_df = db.query_df("""
    SELECT
        COUNT(*) as total_listings,
        ROUND(AVG(price), 2) as avg_price,
        SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_count,
        SUM(CASE WHEN status = 'OUT_OF_STOCK' THEN 1 ELSE 0 END) as oos_count
    FROM listings;
""")
total_l = stats_df["total_listings"].iloc[0]
avg_p = stats_df["avg_price"].iloc[0]
act_l = stats_df["active_count"].iloc[0]
oos_l = stats_df["oos_count"].iloc[0]

# Check Anomaly 3 breaches
ano3_df = db.query_df("""
    SELECT COUNT(*) as breach_count
    FROM listings l
    JOIN sellers s ON l.seller_id = s.seller_id
    WHERE s.status = 'SUSPENDED' AND l.status = 'ACTIVE';
""")
breaches = ano3_df["breach_count"].iloc[0]

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
    render_metric_card("Suspension Breaches", f"{breaches}", "Active under Suspended Sellers", delta_color="danger")

st.markdown("---")

col_box, col_cat_dist = st.columns([3, 2])

with col_box:
    st.subheader("Price Range Distribution by Category ($)")
    sample_listings = db.query_df("SELECT category, price, inventory_count FROM listings LIMIT 2000;")
    fig_box = px.box(
        sample_listings,
        x="category",
        y="price",
        color="category",
        color_discrete_sequence=px.colors.qualitative.Prism,
    )
    apply_plotly_white_layout(fig_box)
    fig_box.update_layout(showlegend=False)
    st.plotly_chart(fig_box, use_container_width=True)

with col_cat_dist:
    st.subheader("Listings per Category")
    cat_counts = db.query_df("SELECT category, COUNT(*) as count FROM listings GROUP BY category ORDER BY count DESC;")
    fig_cat_bar = px.bar(
        cat_counts,
        x="count",
        y="category",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
    )
    apply_plotly_white_layout(fig_cat_bar)
    st.plotly_chart(fig_cat_bar, use_container_width=True)

st.markdown("---")
st.subheader("Catalog Search & Policy Filter")

f1, f2, f3 = st.columns(3)
with f1:
    cats = ["ALL"] + sorted(list(cat_counts["category"]))
    sel_cat = st.selectbox("Category Filter", cats)
with f2:
    show_breaches_only = st.checkbox("Show Suspended Seller Breaches Only (Anomaly 3)", value=False)
with f3:
    search_term = st.text_input("Search Title or Listing ID", "")

query = """
    SELECT
        l.listing_id,
        l.seller_id,
        s.name as seller_name,
        s.status as seller_status,
        l.title,
        l.category,
        l.price,
        l.inventory_count,
        l.status as listing_status,
        l.created_at
    FROM listings l
    JOIN sellers s ON l.seller_id = s.seller_id
    WHERE 1=1
"""
params = []
if sel_cat != "ALL":
    query += " AND l.category = ?"
    params.append(sel_cat)
if show_breaches_only:
    query += " AND s.status = 'SUSPENDED' AND l.status = 'ACTIVE'"
if search_term:
    query += " AND (l.listing_id LIKE ? OR l.title LIKE ?)"
    params.extend([f"%{search_term}%", f"%{search_term}%"])

query += " ORDER BY l.price DESC LIMIT 200;"

table_df = db.query_df(query, tuple(params))
st.dataframe(table_df, use_container_width=True)
