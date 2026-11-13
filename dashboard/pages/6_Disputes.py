"""Disputes, Claims, and Chargebacks Console."""

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

st.set_page_config(page_title="Disputes & Claims - SellerOps", page_icon="⚖️", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Disputes, Claims & Chargeback Protection",
    subtitle="Auditing 10,000 customer dispute claims, chargeback liabilities, adjudication events, and clawback enforcement.",
    badge="10,000 Disputes",
)

# 1. Macro Dispute KPIs
disp_metrics = db.query_df("""
    SELECT
        COUNT(*) as total_disputes,
        ROUND(COALESCE(SUM(disputed_amount_cents), 0) / 100.0, 2) as total_disputed_val,
        SUM(CASE WHEN status = 'RESOLVED_BUYER_FAVOR' THEN 1 ELSE 0 END) as buyer_won,
        SUM(CASE WHEN status = 'CHARGEBACK_LOST' THEN 1 ELSE 0 END) as cb_lost,
        ROUND(SUM(CASE WHEN status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as loss_rate
    FROM disputes;
""")
tot_d = int(disp_metrics["total_disputes"].iloc[0] or 0)
tot_val = float(disp_metrics["total_disputed_val"].iloc[0] or 0.0)
loss_r = float(disp_metrics["loss_rate"].iloc[0] or 0.0)

# Check Anomaly 4: Unclawbacked disputes
ano4_df = db.query_df("""
    SELECT COUNT(*) as unclawbacked_count
    FROM disputes
    WHERE status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST') AND clawback_applied = 0;
""")
unclawbacked = int(ano4_df["unclawbacked_count"].iloc[0] or 0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Disputes", f"{tot_d:,}", "Dispute Volume")
with c2:
    render_metric_card("Total Disputed Value", format_inr_rupees(tot_val), "Gross Claim Exposure")
with c3:
    render_metric_card("Platform Loss Rate", f"{loss_r:.1f}%", "Buyer Favor / CB Lost", delta_color="warning" if loss_r > 35 else "neutral")
with c4:
    render_metric_card("Dispute Frequency", "10.0%", "Per 100k Orders Baseline")
with c5:
    render_metric_card("Unclawbacked Claims", f"{unclawbacked}", "Anomaly 4 Violations", delta_color="danger" if unclawbacked > 0 else "success")

st.markdown("---")

# 2. Interactive Filter Controls
st.markdown("#### Filter Dispute Claims")
f_reason, f_status, f_claw, f_search = st.columns([1.5, 1.2, 1, 1.5])
with f_reason:
    all_reasons = db.query_df("SELECT DISTINCT dispute_reason FROM disputes ORDER BY dispute_reason;")["dispute_reason"].tolist()
    selected_reasons = st.multiselect("Claim Reason", all_reasons, default=all_reasons)
with f_status:
    all_statuses = ["OPEN", "UNDER_REVIEW", "RESOLVED_BUYER_FAVOR", "RESOLVED_SELLER_FAVOR", "CHARGEBACK_LOST", "CHARGEBACK_WON"]
    selected_statuses = st.multiselect("Dispute Status", all_statuses, default=all_statuses)
with f_claw:
    claw_filter = st.selectbox("Clawback Applied?", ["All", "Clawback Applied (1)", "Not Clawed Back (0)"])
with f_search:
    search_query = st.text_input("🔍 Search Dispute, Order, or Seller ID", placeholder="e.g. DSP-2026- or ORD-")

# Query disputes
query_where = []
if selected_reasons:
    r_in = ", ".join(f"'{r}'" for r in selected_reasons)
    query_where.append(f"d.dispute_reason IN ({r_in})")
if selected_statuses:
    s_in = ", ".join(f"'{s}'" for s in selected_statuses)
    query_where.append(f"d.status IN ({s_in})")
if claw_filter == "Clawback Applied (1)":
    query_where.append("d.clawback_applied = 1")
elif claw_filter == "Not Clawed Back (0)":
    query_where.append("d.clawback_applied = 0")

where_clause = " WHERE " + " AND ".join(query_where) if query_where else ""

disputes_df = db.query_df(f"""
    SELECT
        d.dispute_id,
        d.order_id,
        d.order_line_id,
        d.seller_id,
        s.name as seller_name,
        d.customer_id,
        d.dispute_date,
        d.dispute_reason,
        ROUND(d.disputed_amount_cents / 100.0, 2) as disputed_amount_inr,
        d.status as dispute_status,
        d.resolution_date,
        CASE WHEN d.clawback_applied = 1 THEN 'YES ✅' ELSE 'NO ⚠️' END as clawback_status,
        d.clawback_applied
    FROM disputes d
    JOIN sellers s ON d.seller_id = s.seller_id
    {where_clause}
    ORDER BY d.dispute_date DESC
    LIMIT 1000;
""")

if search_query.strip():
    q = search_query.strip().lower()
    disputes_df = disputes_df[
        disputes_df["dispute_id"].str.lower().str.contains(q)
        | disputes_df["order_id"].str.lower().str.contains(q)
        | disputes_df["seller_id"].str.lower().str.contains(q)
        | disputes_df["seller_name"].str.lower().str.contains(q)
    ]

# 3. Macro Visuals
col_reason_chart, col_outcome_chart = st.columns(2)

with col_reason_chart:
    st.subheader("Dispute Claim Reasons Breakdown")
    reason_df = db.query_df("""
        SELECT dispute_reason, COUNT(*) as count, ROUND(SUM(disputed_amount_cents) / 100.0, 2) as total_val
        FROM disputes
        GROUP BY dispute_reason
        ORDER BY count DESC;
    """)
    fig_reason = px.bar(
        reason_df,
        x="count",
        y="dispute_reason",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"count": "Disputes Count", "dispute_reason": "Claim Reason"},
    )
    apply_plotly_white_layout(fig_reason)
    st.plotly_chart(fig_reason, use_container_width=True)

with col_outcome_chart:
    st.subheader("Dispute Adjudication Outcomes")
    outcome_df = db.query_df("""
        SELECT status, COUNT(*) as count
        FROM disputes
        GROUP BY status
        ORDER BY count DESC;
    """)
    fig_outcome = px.pie(
        outcome_df,
        names="status",
        values="count",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["danger"], COLORS["text_secondary"]],
        hole=0.45,
    )
    apply_plotly_white_layout(fig_outcome)
    st.plotly_chart(fig_outcome, use_container_width=True)

st.markdown("---")

# 4. Master Dispute Directory Table
st.subheader("Dispute Claims Directory")
if not disputes_df.empty:
    display_cols = [
        "dispute_id",
        "order_id",
        "order_line_id",
        "seller_name",
        "dispute_date",
        "dispute_reason",
        "disputed_amount_inr",
        "dispute_status",
        "resolution_date",
        "clawback_status",
    ]
    st.dataframe(
        disputes_df[display_cols].head(100),
        use_container_width=True,
    )
    csv_disp = disputes_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Disputes (CSV)",
        data=csv_disp,
        file_name="disputes_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Disputes Found", "Zero disputes match current filter settings.")

st.markdown("---")

# 5. Anomaly 4 Unclawbacked Disputes Table
st.subheader("⚠️ Unclawbacked Dispute Violations (Anomaly 4: Lost Claims Without Payout Deduction)")
unclawbacked_table = db.query_df("""
    SELECT
        d.dispute_id,
        d.order_id,
        d.order_line_id,
        d.seller_id,
        s.name as seller_name,
        d.dispute_date,
        d.dispute_reason,
        ROUND(d.disputed_amount_cents / 100.0, 2) as disputed_inr,
        d.status as dispute_status,
        d.resolution_date,
        d.clawback_applied
    FROM disputes d
    JOIN sellers s ON d.seller_id = s.seller_id
    WHERE d.status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST')
      AND d.clawback_applied = 0;
""")

if not unclawbacked_table.empty:
    st.dataframe(unclawbacked_table, use_container_width=True)
    csv_ano4 = unclawbacked_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Unclawbacked Disputes Audit (CSV)",
        data=csv_ano4,
        file_name="unclawbacked_disputes_audit.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Settlement: 100% of finalized lost disputes have had clawback deductions enforced.")

st.markdown("---")

# 6. Deep-Dive Drill-Down: Dispute Details & Adjudication Events
st.subheader("🔍 Dispute Deep-Dive & Adjudication Audit Trail")

if not disputes_df.empty:
    disp_options = [
        f"{r['dispute_id']} — {r['dispute_reason']} ({format_inr_rupees(r['disputed_amount_inr'])}, {r['dispute_status']})"
        for r in disputes_df.head(50).to_dict(orient="records")
    ]
    selected_disp_str = st.selectbox("Select Dispute for Claim Adjudication History", disp_options)
    selected_disp_id = selected_disp_str.split(" — ")[0]

    disp_rec = db.query_df(f"""
        SELECT 
            d.dispute_id,
            d.order_id,
            d.order_line_id,
            d.seller_id,
            s.name as seller_name,
            d.customer_id,
            d.dispute_date,
            d.dispute_reason,
            ROUND(d.disputed_amount_cents / 100.0, 2) as disputed_inr,
            d.status as dispute_status,
            d.resolution_date,
            d.clawback_applied
        FROM disputes d
        JOIN sellers s ON d.seller_id = s.seller_id
        WHERE d.dispute_id = '{selected_disp_id}';
    """).iloc[0]

    c_d1, c_d2, c_d3, c_d4 = st.columns(4)
    with c_d1:
        render_metric_card("Dispute ID", disp_rec["dispute_id"], f"Filed: {disp_rec['dispute_date']}")
    with c_d2:
        render_metric_card(
            "Claim Status", 
            disp_rec["dispute_status"], 
            f"Resolved: {disp_rec['resolution_date'] or 'In Progress'}",
            delta_color="danger" if disp_rec["dispute_status"] in ["RESOLVED_BUYER_FAVOR", "CHARGEBACK_LOST"] else "neutral"
        )
    with c_d3:
        render_metric_card("Disputed Value", format_inr_rupees(disp_rec['disputed_inr']), f"Seller: {disp_rec['seller_name']}")
    with c_d4:
        is_unclaw = disp_rec["dispute_status"] in ["RESOLVED_BUYER_FAVOR", "CHARGEBACK_LOST"] and disp_rec["clawback_applied"] == 0
        render_metric_card(
            "Clawback Enforcement", 
            "ENFORCED ✅" if disp_rec["clawback_applied"] == 1 else ("VIOLATION 🚨" if is_unclaw else "N/A (Pending/Won)"),
            f"Clawback Flag: {disp_rec['clawback_applied']}",
            delta_color="danger" if is_unclaw else "success"
        )

    tab_events, tab_order_line = st.tabs([
        "📜 Adjudication Event History",
        "🛒 Disputed Order Line Details"
    ])

    with tab_events:
        st.markdown(f"#### Dispute Adjudication Events for `{selected_disp_id}`")
        events_df = db.query_df(f"""
            SELECT 
                event_id,
                previous_status,
                new_status,
                actor,
                notes,
                created_at
            FROM dispute_events
            WHERE dispute_id = '{selected_disp_id}'
            ORDER BY created_at ASC;
        """)
        if not events_df.empty:
            st.dataframe(events_df, use_container_width=True)
        else:
            render_empty_state("No Event Trail", "No adjudication state events recorded for this dispute.")

    with tab_order_line:
        st.markdown(f"#### Disputed Order Line: `{disp_rec['order_line_id']}`")
        line_info = db.query_df(f"""
            SELECT 
                ol.order_line_id,
                ol.order_id,
                ol.listing_id,
                l.title as product_title,
                l.category,
                ol.quantity,
                ROUND(ol.unit_price_cents / 100.0, 2) as unit_price_inr,
                ROUND(ol.gross_amount_cents / 100.0, 2) as line_gross_inr,
                ol.line_status
            FROM order_lines ol
            JOIN listings l ON ol.listing_id = l.listing_id
            WHERE ol.order_line_id = '{disp_rec['order_line_id']}';
        """)
        if not line_info.empty:
            st.dataframe(line_info, use_container_width=True)
        else:
            render_empty_state("Order Line Missing", "Unable to locate underlying order line.")
else:
    render_empty_state("No Dispute Selected", "Select or loosen filter criteria above.")
