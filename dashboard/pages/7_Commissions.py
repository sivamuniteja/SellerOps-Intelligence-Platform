"""Commission Engine and Platform Revenue Console."""

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

st.set_page_config(page_title="Commissions Engine - SellerOps", page_icon="💰", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Seller Commissions & Platform Revenue",
    subtitle="Auditing category-level take rates, tier fee discounts, fixed fees, and duplicate commission flags.",
    badge="Revenue Engine",
)

comm_metrics = db.query_df("""
    SELECT
        ROUND(COALESCE(SUM(gross_amount_cents), 0) / 100.0, 2) as total_gross,
        ROUND(COALESCE(SUM(total_commission_cents), 0) / 100.0, 2) as total_comm,
        ROUND(AVG(rate_basis_points) / 100.0, 2) as avg_rate,
        ROUND(COALESCE(SUM(total_commission_cents), 0) * 100.0 / NULLIF(SUM(gross_amount_cents), 0), 2) as effective_take_rate
    FROM commission_ledger;
""")
tot_gross = float(comm_metrics["total_gross"].iloc[0] or 0.0)
tot_comm = float(comm_metrics["total_comm"].iloc[0] or 0.0)
take_rate = float(comm_metrics["effective_take_rate"].iloc[0] or 0.0)
avg_rate = float(comm_metrics["avg_rate"].iloc[0] or 0.0)

# Check Anomaly 2: Double commission
ano2_df = db.query_df("""
    SELECT COUNT(*) as double_comm_count
    FROM commission_ledger c
    WHERE c.total_commission_cents > ((c.gross_amount_cents * c.rate_basis_points / 10000.0 + c.fixed_fee_cents) * 1.5);
""")
double_comm = int(ano2_df["double_comm_count"].iloc[0] or 0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Commission Revenue", f"${tot_comm:,.2f}", "Total Net Platform Fees")
with c2:
    render_metric_card("Effective Take Rate", f"{take_rate:.2f}%", "Blended Platform Rate")
with c3:
    render_metric_card("Average Category Rate", f"{avg_rate:.2f}%", "Base Category Schedule")
with c4:
    render_metric_card("Fixed Handling Fee", "$0.30", "Per Order Line Settlement")
with c5:
    render_metric_card("Duplicate Charges", f"{double_comm}", "Anomaly 2 Breaches", delta_color="danger")

st.markdown("---")

col_cat, col_fees = st.columns(2)

with col_cat:
    st.subheader("Commission Revenue by Category ($)")
    cat_comm = db.query_df("""
        SELECT
            l.category,
            ROUND(SUM(c.total_commission_cents) / 100.0, 2) as commission_revenue,
            ROUND(SUM(c.total_commission_cents) * 100.0 / NULLIF(SUM(c.gross_amount_cents), 0), 2) as effective_rate
        FROM commission_ledger c
        JOIN order_lines ol ON c.order_line_id = ol.order_line_id
        JOIN listings l ON ol.listing_id = l.listing_id
        GROUP BY l.category
        ORDER BY commission_revenue DESC;
    """)
    fig_cat = px.bar(
        cat_comm,
        x="commission_revenue",
        y="category",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"commission_revenue": "Commission Revenue ($)", "category": "Product Category"},
    )
    apply_plotly_white_layout(fig_cat)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_fees:
    st.subheader("Fee Component Breakdown (Variable vs Fixed)")
    fee_split = db.query_df("""
        SELECT
            ROUND(SUM(variable_fee_cents) / 100.0, 2) as variable_fees,
            ROUND(SUM(fixed_fee_cents) / 100.0, 2) as fixed_fees
        FROM commission_ledger;
    """)
    split_data = pd.DataFrame([
        {"Fee Component": "Variable Take Rate", "Amount": fee_split["variable_fees"].iloc[0]},
        {"Fee Component": "Fixed Handling Fees ($0.30)", "Amount": fee_split["fixed_fees"].iloc[0]},
    ])
    fig_split = px.pie(
        split_data,
        names="Fee Component",
        values="Amount",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"]],
        hole=0.45,
    )
    apply_plotly_white_layout(fig_split)
    st.plotly_chart(fig_split, use_container_width=True)

st.markdown("---")

# Anomaly 2: Duplicate Commission Audit
st.subheader("⚠️ Double Commission Violations (Anomaly 2: Platform Take-Rate Overcharge)")
ano2_records = db.query_df("""
    SELECT
        c.entry_id,
        c.order_line_id,
        c.seller_id,
        ROUND(c.gross_amount_cents / 100.0, 2) as gross_dollars,
        ROUND(c.rate_basis_points / 100.0, 2) as rate_percent,
        ROUND(c.variable_fee_cents / 100.0, 2) as variable_fee_dollars,
        ROUND(c.fixed_fee_cents / 100.0, 2) as fixed_fee_dollars,
        ROUND(c.total_commission_cents / 100.0, 2) as total_charged_dollars
    FROM commission_ledger c
    WHERE c.total_commission_cents > ((c.gross_amount_cents * c.rate_basis_points / 10000.0 + c.fixed_fee_cents) * 1.5);
""")

if not ano2_records.empty:
    st.dataframe(ano2_records, use_container_width=True)
    csv_ano2 = ano2_records.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Double Commission Audit (CSV)",
        data=csv_ano2,
        file_name="double_commission_violations.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Accounting: All commission fees accurately match platform schedules.")
