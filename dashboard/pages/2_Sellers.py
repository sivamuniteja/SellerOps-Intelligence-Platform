"""Seller Performance and Compliance Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Sellers Console - SellerOps", page_icon="👥", layout="wide")
apply_theme()
db = get_database()

st.title("Seller Operations & Risk Management")
st.markdown("Monitor 2,000 sellers across SLA performance tiers, risk scores, and probation statuses.")

# Tier counts
tier_df = db.query_df("""
    SELECT tier, COUNT(*) as count, ROUND(AVG(risk_score), 1) as avg_risk, ROUND(AVG(rating), 2) as avg_rating
    FROM sellers
    GROUP BY tier;
""")
tier_counts = {r["tier"]: r for r in tier_df.to_dict(orient="records")}

t1, t2, t3, t4, t5 = st.columns(5)
with t1:
    ent = tier_counts.get("ENTERPRISE", {})
    render_metric_card("Enterprise", f"{ent.get('count', 0):,}", f"Avg Risk: {ent.get('avg_risk', 0.0)}")
with t2:
    pref = tier_counts.get("PREFERRED", {})
    render_metric_card("Preferred", f"{pref.get('count', 0):,}", f"Avg Risk: {pref.get('avg_risk', 0.0)}")
with t3:
    std = tier_counts.get("STANDARD", {})
    render_metric_card("Standard", f"{std.get('count', 0):,}", f"Avg Risk: {std.get('avg_risk', 0.0)}")
with t4:
    prob = tier_counts.get("PROBATION", {})
    render_metric_card("Probation", f"{prob.get('count', 0):,}", f"Avg Risk: {prob.get('avg_risk', 0.0)}", delta_color="warning")
with t5:
    susp = tier_counts.get("SUSPENDED", {})
    render_metric_card("Suspended", f"{susp.get('count', 0):,}", f"Avg Risk: {susp.get('avg_risk', 0.0)}", delta_color="danger")

st.markdown("---")

col_hist, col_scatter = st.columns(2)

with col_hist:
    st.subheader("Seller Risk Score Distribution (0 - 100)")
    sellers_df = db.query_df("SELECT seller_id, name, tier, status, risk_score, rating FROM sellers;")
    fig_hist = px.histogram(
        sellers_df,
        x="risk_score",
        nbins=25,
        color="tier",
        color_discrete_map={
            "ENTERPRISE": COLORS["primary"],
            "PREFERRED": COLORS["success"],
            "STANDARD": COLORS["text_secondary"],
            "PROBATION": COLORS["warning"],
            "SUSPENDED": COLORS["danger"],
        },
        labels={"risk_score": "Risk Score", "count": "Seller Count"},
    )
    apply_plotly_white_layout(fig_hist)
    st.plotly_chart(fig_hist, use_container_width=True)

with col_scatter:
    st.subheader("Customer Rating vs Risk Score")
    fig_scatter = px.scatter(
        sellers_df.sample(min(500, len(sellers_df))),
        x="risk_score",
        y="rating",
        color="tier",
        hover_data=["seller_id", "name"],
        color_discrete_map={
            "ENTERPRISE": COLORS["primary"],
            "PREFERRED": COLORS["success"],
            "STANDARD": COLORS["text_secondary"],
            "PROBATION": COLORS["warning"],
            "SUSPENDED": COLORS["danger"],
        },
        labels={"risk_score": "Risk Score", "rating": "Seller Rating (1-5)"},
    )
    apply_plotly_white_layout(fig_scatter)
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")
st.subheader("Seller Directory & Audit Explorer")

# Filter controls
f1, f2, f3 = st.columns(3)
with f1:
    selected_tier = st.selectbox("Filter by Tier", ["ALL"] + sorted(list(sellers_df["tier"].unique())))
with f2:
    selected_status = st.selectbox("Filter by Status", ["ALL"] + sorted(list(sellers_df["status"].unique())))
with f3:
    search_query = st.text_input("Search Seller ID or Name", "")

query = """
    SELECT
        s.seller_id,
        s.name,
        s.tier,
        s.status,
        s.risk_score,
        s.rating,
        s.country,
        s.onboarding_date,
        COUNT(o.order_id) as total_orders,
        COALESCE(ROUND(SUM(o.gross_amount), 2), 0.0) as gmv
    FROM sellers s
    LEFT JOIN orders o ON s.seller_id = o.seller_id
    WHERE 1=1
"""
params = []
if selected_tier != "ALL":
    query += " AND s.tier = ?"
    params.append(selected_tier)
if selected_status != "ALL":
    query += " AND s.status = ?"
    params.append(selected_status)
if search_query:
    query += " AND (s.seller_id LIKE ? OR s.name LIKE ?)"
    params.extend([f"%{search_query}%", f"%{search_query}%"])

query += " GROUP BY s.seller_id ORDER BY s.risk_score DESC LIMIT 200;"

table_df = db.query_df(query, tuple(params))
st.dataframe(table_df, use_container_width=True)
