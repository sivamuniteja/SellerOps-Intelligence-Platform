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
    subtitle="Monitor 2,000 sellers across SLA performance tiers, risk scores, fulfillment compliance, and suspension history.",
    badge="2,000 Managed Sellers",
)

# 1. Tier & Standing KPIs
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

# 2. Filter Controls
st.markdown("#### Filter Seller Directory")
f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1.5, 1.5])
with f_col1:
    all_tiers = ["ENTERPRISE", "PREFERRED", "STANDARD", "PROBATION", "SUSPENDED"]
    selected_tiers = st.multiselect("Seller Tier", all_tiers, default=all_tiers)
with f_col2:
    all_statuses = ["ACTIVE", "PROBATION", "SUSPENDED", "UNDER_REVIEW"]
    selected_statuses = st.multiselect("Seller Status", all_statuses, default=all_statuses)
with f_col3:
    risk_range = st.slider("Risk Score Range (0 - 100)", 0.0, 100.0, (0.0, 100.0), step=1.0)
with f_col4:
    search_query = st.text_input("🔍 Search Seller ID or Name", placeholder="e.g. SELL-000001 or Hall Inc")

# 3. Macro Visualizations
col_hist, col_scatter = st.columns(2)

base_sellers = db.query_df("""
    SELECT 
        s.seller_id,
        s.name,
        s.tier,
        s.status,
        s.risk_score,
        s.rating,
        s.onboarding_date,
        COALESCE(l.listing_count, 0) as listing_count,
        COALESCE(o.order_count, 0) as order_count,
        ROUND(COALESCE(c.total_commission_cents, 0) / 100.0, 2) as total_commission_inr,
        ROUND(COALESCE(f.on_time_pct, 100.0), 1) as fulfillment_pct,
        ROUND(COALESCE(d.dispute_count, 0) * 100.0 / NULLIF(COALESCE(o.order_count, 0), 0), 2) as dispute_rate_pct,
        COALESCE(p.payout_status_summary, 'NO_PAYOUTS') as payout_status
    FROM sellers s
    LEFT JOIN (SELECT seller_id, COUNT(*) as listing_count FROM listings GROUP BY seller_id) l ON s.seller_id = l.seller_id
    LEFT JOIN (SELECT seller_id, COUNT(DISTINCT order_id) as order_count FROM order_lines GROUP BY seller_id) o ON s.seller_id = o.seller_id
    LEFT JOIN (SELECT seller_id, SUM(total_commission_cents) as total_commission_cents FROM commission_ledger GROUP BY seller_id) c ON s.seller_id = c.seller_id
    LEFT JOIN (
        SELECT seller_id, 
               ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as on_time_pct 
        FROM fulfillments 
        GROUP BY seller_id
    ) f ON s.seller_id = f.seller_id
    LEFT JOIN (SELECT seller_id, COUNT(*) as dispute_count FROM disputes GROUP BY seller_id) d ON s.seller_id = d.seller_id
    LEFT JOIN (
        SELECT seller_id, 
               CASE 
                   WHEN SUM(CASE WHEN payout_status = 'HELD' THEN 1 ELSE 0 END) > 0 THEN 'HELD'
                   WHEN SUM(CASE WHEN payout_status = 'PENDING' THEN 1 ELSE 0 END) > 0 THEN 'PENDING'
                   WHEN SUM(CASE WHEN payout_status = 'PAID' THEN 1 ELSE 0 END) > 0 THEN 'PAID'
                   ELSE 'SCHEDULED'
               END as payout_status_summary
        FROM payouts
        GROUP BY seller_id
    ) p ON s.seller_id = p.seller_id;
""")

filtered_sellers = base_sellers[
    (base_sellers["tier"].isin(selected_tiers))
    & (base_sellers["status"].isin(selected_statuses))
    & (base_sellers["risk_score"] >= risk_range[0])
    & (base_sellers["risk_score"] <= risk_range[1])
]

if search_query.strip():
    q = search_query.strip().lower()
    filtered_sellers = filtered_sellers[
        filtered_sellers["seller_id"].str.lower().str.contains(q)
        | filtered_sellers["name"].str.lower().str.contains(q)
    ]

with col_hist:
    st.subheader("Seller Risk Score Distribution (0 - 100)")
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

# 4. Master Seller Directory Table
st.subheader("Filtered Seller Directory")
if not filtered_sellers.empty:
    display_cols = [
        "seller_id",
        "name",
        "tier",
        "status",
        "risk_score",
        "listing_count",
        "order_count",
        "fulfillment_pct",
        "dispute_rate_pct",
        "rating",
        "total_commission_inr",
        "payout_status",
    ]
    st.dataframe(
        filtered_sellers.sort_values(by="risk_score", ascending=False)[display_cols].head(100),
        use_container_width=True,
    )
    csv_sellers = filtered_sellers[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Sellers Directory (CSV)",
        data=csv_sellers,
        file_name="sellers_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Sellers Match Criteria", "Clear or loosen the filters above.")

st.markdown("---")

# 5. Deep-Dive Drill-Down: Detailed Seller Profile
st.subheader("🔍 Seller Deep-Dive & Historical Audit")

if not filtered_sellers.empty:
    seller_options = [
        f"{r['seller_id']} — {r['name']} ({r['status']}, {r['tier']})"
        for r in filtered_sellers.sort_values(by="risk_score", ascending=False).head(50).to_dict(orient="records")
    ]
    selected_seller_str = st.selectbox("Select Seller for Full Operational Audit", seller_options)
    selected_seller_id = selected_seller_str.split(" — ")[0]

    seller_rec = db.query_df(f"SELECT * FROM sellers WHERE seller_id = '{selected_seller_id}';").iloc[0]

    c_s1, c_s2, c_s3, c_s4 = st.columns(4)
    with c_s1:
        render_metric_card("Seller Name", seller_rec["name"], f"ID: {seller_rec['seller_id']}")
    with c_s2:
        render_metric_card(
            "Standing Status",
            seller_rec["status"],
            f"Tier: {seller_rec['tier']}",
            delta_color="danger" if seller_rec["status"] == "SUSPENDED" else ("warning" if seller_rec["status"] == "PROBATION" else "success")
        )
    with c_s3:
        render_metric_card("Risk Score", f"{seller_rec['risk_score']:.1f} / 100", f"Rating: {seller_rec['rating']:.2f} ⭐")
    with c_s4:
        render_metric_card("Onboarding Date", str(seller_rec["onboarding_date"]), "Account Active")

    tab_events, tab_listings, tab_orders, tab_payouts = st.tabs([
        "📜 Status Lifecycle Audit Log",
        "📦 Active Catalog Listings",
        "🛒 Recent Order Lines",
        "💳 Settlement & Payout History"
    ])

    with tab_events:
        st.markdown(f"#### Status Audit Trail for `{selected_seller_id}`")
        events_df = db.query_df(f"""
            SELECT event_id, previous_status, new_status, reason, created_at
            FROM seller_status_events
            WHERE seller_id = '{selected_seller_id}'
            ORDER BY created_at DESC;
        """)
        if not events_df.empty:
            st.dataframe(events_df, use_container_width=True)
        else:
            render_empty_state("No Status Changes", "This seller has maintained their initial onboarding status with zero suspension events.")

    with tab_listings:
        st.markdown(f"#### Catalog Listings for `{selected_seller_id}`")
        listings_df = db.query_df(f"""
            SELECT 
                listing_id, 
                title, 
                category, 
                ROUND(price_cents / 100.0, 2) as price_inr, 
                inventory_count, 
                status, 
                created_at
            FROM listings
            WHERE seller_id = '{selected_seller_id}'
            ORDER BY created_at DESC;
        """)
        if not listings_df.empty:
            st.dataframe(listings_df, use_container_width=True)
        else:
            render_empty_state("No Listings", "This seller currently has no active or archived listings.")

    with tab_orders:
        st.markdown(f"#### Order Lines Fulfilled by `{selected_seller_id}`")
        orders_df = db.query_df(f"""
            SELECT 
                ol.order_line_id,
                ol.order_id,
                o.order_date,
                ol.listing_id,
                ol.quantity,
                ROUND(ol.unit_price_cents / 100.0, 2) as unit_price_inr,
                ROUND(ol.gross_amount_cents / 100.0, 2) as gross_inr,
                ol.line_status
            FROM order_lines ol
            JOIN orders o ON ol.order_id = o.order_id
            WHERE ol.seller_id = '{selected_seller_id}'
            ORDER BY o.order_date DESC
            LIMIT 50;
        """)
        if not orders_df.empty:
            st.dataframe(orders_df, use_container_width=True)
        else:
            render_empty_state("No Order Lines", "Zero order lines found for this seller.")

    with tab_payouts:
        st.markdown(f"#### Payout Batches for `{selected_seller_id}`")
        payouts_df = db.query_df(f"""
            SELECT 
                payout_id,
                batch_date,
                total_lines_count,
                ROUND(gross_sales_cents / 100.0, 2) as gross_inr,
                ROUND(total_commission_cents / 100.0, 2) as commission_inr,
                ROUND(total_reserve_held_cents / 100.0, 2) as reserve_inr,
                ROUND(total_disputes_deducted_cents / 100.0, 2) as disputes_inr,
                ROUND(net_payout_amount_cents / 100.0, 2) as net_payout_inr,
                payout_status,
                reconciliation_status
            FROM payouts
            WHERE seller_id = '{selected_seller_id}'
            ORDER BY batch_date DESC;
        """)
        if not payouts_df.empty:
            st.dataframe(payouts_df, use_container_width=True)
        else:
            render_empty_state("No Payout Batches", "Zero payout batches generated for this seller yet.")
else:
    render_empty_state("No Seller Selected", "Select at least one seller above to inspect detailed audit logs.")
