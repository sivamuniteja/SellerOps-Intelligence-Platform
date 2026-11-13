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
    format_inr_rupees,
    COLORS,
)
from src.validation.anomaly_detection import AnomalyDetectionEngine

st.set_page_config(page_title="Commissions Engine - SellerOps", page_icon="💰", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Seller Commissions & Platform Revenue",
    subtitle="Auditing category-level take rates, tier fee discounts, fixed order line fees, and duplicate commission flags.",
    badge="Revenue Engine",
)

# 1. Macro Commission KPIs
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

# Detect Anomaly 2 double commission violations
detector = AnomalyDetectionEngine(db)
ano2_detected = detector.detect_double_commissions()
double_comm_count = len(ano2_detected)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Commission Revenue", format_inr_rupees(tot_comm), "Total Net Platform Fees")
with c2:
    render_metric_card("Effective Take Rate", f"{take_rate:.2f}%", "Blended Platform Rate")
with c3:
    render_metric_card("Average Category Rate", f"{avg_rate:.2f}%", "Base Category Schedule")
with c4:
    render_metric_card("Fixed Handling Fee", "₹0.30", "Per Settled Order Line (30 Paise)")
with c5:
    render_metric_card("Duplicate Charges", f"{double_comm_count}", "Anomaly 2 Breaches", delta_color="danger" if double_comm_count > 0 else "success")

st.markdown("---")

# 2. Interactive Filter Controls
st.markdown("#### Filter Commission Ledger")
f_cat, f_tier, f_search = st.columns([1.5, 1.5, 2])
with f_cat:
    all_categories = db.query_df("SELECT DISTINCT category FROM commission_rules ORDER BY category;")["category"].tolist()
    selected_categories = st.multiselect("Category", all_categories, default=all_categories)
with f_tier:
    all_tiers = ["ENTERPRISE", "PREFERRED", "STANDARD", "PROBATION", "SUSPENDED"]
    selected_tiers = st.multiselect("Seller Tier", all_tiers, default=all_tiers)
with f_search:
    search_query = st.text_input("🔍 Search Entry ID, Order Line ID, or Seller ID", placeholder="e.g. CML- or ORDLN-")

# Query commission ledger
query_where = []
if selected_categories:
    cat_in = ", ".join(f"'{c}'" for c in selected_categories)
    query_where.append(f"cr.category IN ({cat_in})")
if selected_tiers:
    tier_in = ", ".join(f"'{t}'" for t in selected_tiers)
    query_where.append(f"cr.seller_tier IN ({tier_in})")

where_clause = " WHERE " + " AND ".join(query_where) if query_where else ""

ledger_df = db.query_df(f"""
    SELECT
        c.entry_id,
        c.order_line_id,
        c.seller_id,
        s.name as seller_name,
        cr.category,
        cr.seller_tier,
        c.rule_id,
        ROUND(c.gross_amount_cents / 100.0, 2) as gross_inr,
        ROUND(c.rate_basis_points / 100.0, 2) as rate_percent,
        ROUND(c.variable_fee_cents / 100.0, 2) as variable_fee_inr,
        ROUND(c.fixed_fee_cents / 100.0, 2) as fixed_fee_inr,
        ROUND(c.total_commission_cents / 100.0, 2) as total_commission_inr,
        ROUND(c.total_commission_cents * 100.0 / NULLIF(c.gross_amount_cents, 0), 2) as actual_take_rate_pct
    FROM commission_ledger c
    JOIN sellers s ON c.seller_id = s.seller_id
    JOIN commission_rules cr ON c.rule_id = cr.rule_id
    {where_clause}
    ORDER BY c.created_at DESC
    LIMIT 1000;
""")

if search_query.strip():
    q = search_query.strip().lower()
    ledger_df = ledger_df[
        ledger_df["entry_id"].str.lower().str.contains(q)
        | ledger_df["order_line_id"].str.lower().str.contains(q)
        | ledger_df["seller_id"].str.lower().str.contains(q)
        | ledger_df["seller_name"].str.lower().str.contains(q)
    ]

# 3. Macro Visuals
col_cat_chart, col_fees_chart = st.columns(2)

with col_cat_chart:
    st.subheader("Commission Revenue by Category (₹)")
    cat_comm = db.query_df("""
        SELECT
            cr.category,
            ROUND(SUM(c.total_commission_cents) / 100.0, 2) as commission_revenue,
            ROUND(SUM(c.total_commission_cents) * 100.0 / NULLIF(SUM(c.gross_amount_cents), 0), 2) as effective_rate
        FROM commission_ledger c
        JOIN commission_rules cr ON c.rule_id = cr.rule_id
        GROUP BY cr.category
        ORDER BY commission_revenue DESC;
    """)
    fig_cat = px.bar(
        cat_comm,
        x="commission_revenue",
        y="category",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"commission_revenue": "Commission Revenue (₹)", "category": "Product Category"},
    )
    apply_plotly_white_layout(fig_cat)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_fees_chart:
    st.subheader("Fee Component Breakdown (Variable vs Fixed)")
    fee_split = db.query_df("""
        SELECT
            ROUND(SUM(variable_fee_cents) / 100.0, 2) as variable_fees,
            ROUND(SUM(fixed_fee_cents) / 100.0, 2) as fixed_fees
        FROM commission_ledger;
    """)
    split_data = pd.DataFrame([
        {"Fee Component": "Variable Take Rate", "Amount": fee_split["variable_fees"].iloc[0]},
        {"Fee Component": "Fixed Handling Fees (₹0.30)", "Amount": fee_split["fixed_fees"].iloc[0]},
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

# 4. Commission Rules Table
st.subheader("Applicable Commission Fee Schedules")
rules_df = db.query_df("""
    SELECT
        rule_id,
        category,
        seller_tier,
        ROUND(base_rate_basis_points / 100.0, 2) as base_rate_percent,
        ROUND(min_commission_cents / 100.0, 2) as min_commission_inr,
        ROUND(fixed_fee_cents / 100.0, 2) as fixed_fee_inr,
        effective_from,
        effective_to,
        is_active
    FROM commission_rules
    ORDER BY category, seller_tier;
""")
st.dataframe(rules_df, use_container_width=True)

st.markdown("---")

# 5. Master Commission Ledger Entries Directory Table
st.subheader("Commission Ledger Entries Directory")
if not ledger_df.empty:
    display_cols = [
        "entry_id",
        "order_line_id",
        "seller_name",
        "category",
        "seller_tier",
        "gross_inr",
        "rate_percent",
        "variable_fee_inr",
        "fixed_fee_inr",
        "total_commission_inr",
        "actual_take_rate_pct",
    ]
    st.dataframe(
        ledger_df[display_cols].head(100),
        use_container_width=True,
    )
    csv_ledger = ledger_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Commission Ledger (CSV)",
        data=csv_ledger,
        file_name="commission_ledger_entries.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Ledger Entries Match Filters", "Adjust category or seller tier filters above.")

st.markdown("---")

# 6. Anomaly 2: Duplicate Commission Violations Table
st.subheader("⚠️ Double Commission Violations (Anomaly 2: Platform Take-Rate Overcharge)")
if ano2_detected:
    ano2_rows = []
    for a in ano2_detected:
        d = a.get("details", {})
        ano2_rows.append({
            "entry_id": a["entity_id"],
            "order_line_id": d.get("order_line_id", ""),
            "seller_id": d.get("seller_id", ""),
            "gross_inr": round(d.get("gross_amount_cents", 0) / 100.0, 2),
            "actual_commission_inr": round(d.get("actual_commission_cents", 0) / 100.0, 2),
            "expected_commission_inr": round(d.get("expected_commission_cents", 0) / 100.0, 2),
            "overcharge_variance_inr": round(d.get("variance_cents", 0) / 100.0, 2),
            "severity": a["severity"],
            "expected_action": a["expected_corrective_action"],
        })
    df_ano2 = pd.DataFrame(ano2_rows)
    st.dataframe(df_ano2, use_container_width=True)

    csv_ano2 = df_ano2.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Double Commission Audit (CSV)",
        data=csv_ano2,
        file_name="double_commission_violations.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Accounting: All commission fees accurately match platform schedules with zero duplicates.")

st.markdown("---")

# 7. Deep-Dive Drill-Down: Detailed Commission Calculation Formula Breakdown
st.subheader("🔍 Commission Entry Deep-Dive & Formula Verification")

if not ledger_df.empty:
    entry_options = [
        f"{r['entry_id']} — {format_inr_rupees(r['total_commission_inr'])} (Gross: {format_inr_rupees(r['gross_inr'])}, Line: {r['order_line_id']})"
        for r in ledger_df.head(50).to_dict(orient="records")
    ]
    selected_entry_str = st.selectbox("Select Ledger Entry for Fee Formula Audit", entry_options)
    selected_entry_id = selected_entry_str.split(" — ")[0]

    entry_rec = db.query_df(f"""
        SELECT 
            c.entry_id,
            c.order_line_id,
            c.seller_id,
            s.name as seller_name,
            cr.rule_id,
            cr.category,
            cr.seller_tier,
            ROUND(c.gross_amount_cents / 100.0, 2) as gross_inr,
            ROUND(c.rate_basis_points / 100.0, 2) as rate_percent,
            ROUND(c.variable_fee_cents / 100.0, 2) as variable_fee_inr,
            ROUND(c.fixed_fee_cents / 100.0, 2) as fixed_fee_inr,
            ROUND(c.total_commission_cents / 100.0, 2) as total_commission_inr,
            ROUND(cr.min_commission_cents / 100.0, 2) as min_commission_inr,
            c.created_at
        FROM commission_ledger c
        JOIN sellers s ON c.seller_id = s.seller_id
        JOIN commission_rules cr ON c.rule_id = cr.rule_id
        WHERE c.entry_id = '{selected_entry_id}';
    """).iloc[0]

    c_e1, c_e2, c_e3, c_e4 = st.columns(4)
    with c_e1:
        render_metric_card("Entry ID", entry_rec["entry_id"], f"Rule: {entry_rec['rule_id']}")
    with c_e2:
        render_metric_card("Order Line ID", entry_rec["order_line_id"], f"Seller: {entry_rec['seller_name']}")
    with c_e3:
        render_metric_card("Gross Sales Amount", format_inr_rupees(entry_rec['gross_inr']), f"Category: {entry_rec['category']}")
    with c_e4:
        render_metric_card("Platform Take", format_inr_rupees(entry_rec['total_commission_inr']), f"Tier: {entry_rec['seller_tier']}")

    st.markdown(
        f"""
        <div class="metric-card" style="margin-top: 15px;">
            <h5 style="margin-top: 0; color: #111827;">Deterministic Formula Audit:</h5>
            <p style="margin-bottom: 6px; font-family: monospace; font-size: 0.95rem;">
                <b>Variable Take:</b> Gross ({format_inr_rupees(entry_rec['gross_inr'])}) × Rate ({entry_rec['rate_percent']:.2f}%) = <b>{format_inr_rupees(entry_rec['variable_fee_inr'])}</b><br>
                <b>Fixed Handling Fee:</b> <b>{format_inr_rupees(entry_rec['fixed_fee_inr'])}</b><br>
                <b>Base Sum:</b> {format_inr_rupees(entry_rec['variable_fee_inr'])} + {format_inr_rupees(entry_rec['fixed_fee_inr'])} = <b>{format_inr_rupees(entry_rec['variable_fee_inr'] + entry_rec['fixed_fee_inr'])}</b><br>
                <b>Category Minimum Guarantee:</b> {format_inr_rupees(entry_rec['min_commission_inr'])}<br>
                <b>Final Charged Commission:</b> <span style="color: #2563EB; font-weight: bold;">{format_inr_rupees(entry_rec['total_commission_inr'])}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    render_empty_state("No Entry Selected", "Select or loosen filter criteria above.")
