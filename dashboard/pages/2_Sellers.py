"""Seller Performance and Compliance Console."""

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

st.set_page_config(page_title="Sellers Console - SellerOps", page_icon="👥", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Seller Operations & Risk Management",
    subtitle="Monitor 2,000 sellers across SLA performance tiers, risk scores, and probation statuses.",
    badge="2,000 Managed Sellers",
)

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

# Filter Controls
st.markdown("#### Filter Seller Directory")
f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
with f_col1:
    all_tiers = list(tier_counts.keys())
    selected_tiers = st.multiselect("Seller Tier", all_tiers, default=all_tiers)
with f_col2:
    all_statuses = ["ACTIVE", "PROBATION", "SUSPENDED", "UNDER_REVIEW"]
    selected_statuses = st.multiselect("Seller Status", all_statuses, default=all_statuses)
with f_col3:
    risk_range = st.slider("Risk Score Range (0 - 100)", 0.0, 100.0, (0.0, 100.0), step=1.0)

col_hist, col_scatter = st.columns(2)

with col_hist:
    st.subheader("Seller Risk Score Distribution (0 - 100)")
    sellers_df = db.query_df("SELECT seller_id, name, tier, status, risk_score, rating, onboarding_date FROM sellers;")
    filtered_sellers = sellers_df[
        (sellers_df["tier"].isin(selected_tiers))
        & (sellers_df["status"].isin(selected_statuses))
        & (sellers_df["risk_score"] >= risk_range[0])
        & (sellers_df["risk_score"] <= risk_range[1])
    ]

    if not filtered_sellers.empty:
        fig_hist = px.histogram(
            filtered_sellers,
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
    else:
        render_empty_state("No Sellers Match Filters", "Adjust tier or status filters above.")

with col_scatter:
    st.subheader("Customer Rating vs Risk Score")
    if not filtered_sellers.empty:
        sample_size = min(500, len(filtered_sellers))
        fig_scatter = px.scatter(
            filtered_sellers.sample(sample_size, random_state=42),
            x="risk_score",
            y="rating",
            color="tier",
            color_discrete_map={
                "ENTERPRISE": COLORS["primary"],
                "PREFERRED": COLORS["success"],
                "STANDARD": COLORS["text_secondary"],
                "PROBATION": COLORS["warning"],
                "SUSPENDED": COLORS["danger"],
            },
            labels={"risk_score": "Risk Score", "rating": "Avg Customer Rating (1-5)"},
        )
        apply_plotly_white_layout(fig_scatter)
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        render_empty_state("No Scatter Data", "Select at least one tier to view rating correlation.")

st.markdown("---")

# Seller Table
st.subheader("Filtered Seller Directory")
if not filtered_sellers.empty:
    st.dataframe(
        filtered_sellers.sort_values(by="risk_score", ascending=False).head(100),
        use_container_width=True,
    )
    csv_sellers = filtered_sellers.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Sellers (CSV)",
        data=csv_sellers,
        file_name="sellers_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state()
