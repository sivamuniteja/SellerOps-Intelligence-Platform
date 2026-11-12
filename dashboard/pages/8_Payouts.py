"""Payout Batches and Disbursement Operations Console."""

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

st.set_page_config(page_title="Payout Batches - SellerOps", page_icon="💳", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Seller Payout Batches & Disbursements",
    subtitle="Auditing net payout disbursements, rolling reserve holds, eligibility rules, and disbursement cycles.",
    badge="Banking & Settlements",
)

# 1. Macro Payout KPIs
payout_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_batches,
        ROUND(COALESCE(SUM(gross_sales_cents), 0) / 100.0, 2) as total_gross_settled,
        ROUND(COALESCE(SUM(total_reserve_held_cents), 0) / 100.0, 2) as total_reserve_held,
        ROUND(COALESCE(SUM(net_payout_amount_cents), 0) / 100.0, 2) as total_net_disbursed
    FROM payouts;
""")
tot_b = int(payout_kpis["total_batches"].iloc[0] or 0)
tot_net = float(payout_kpis["total_net_disbursed"].iloc[0] or 0.0)
tot_res = float(payout_kpis["total_reserve_held"].iloc[0] or 0.0)

# Check Anomaly 1: Premature payouts
detector = AnomalyDetectionEngine(db)
ano1_detected = detector.detect_premature_payouts()
premature_count = len(ano1_detected)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Net Disbursed", format_inr_rupees(tot_net), "Total Net Payouts")
with c2:
    render_metric_card("Rolling Reserve Held", format_inr_rupees(tot_res), "Risk Collateral Held")
with c3:
    render_metric_card("Total Payout Batches", f"{tot_b:,}", "Disbursement Cycles")
with c4:
    render_metric_card("Settled Order Lines", f"{db.row_count('payout_lines'):,}", "Line Items")
with c5:
    render_metric_card("Premature Disbursements", f"{premature_count}", "Anomaly 1 Violations", delta_color="danger" if premature_count > 0 else "success")

st.markdown("---")

# 2. Interactive Filter Controls
st.markdown("#### Filter Payout Batches")
col_s1, col_s2, col_s3 = st.columns([1.5, 1.5, 2])
with col_s1:
    p_statuses = ["PAID", "HELD", "PROCESSING", "SCHEDULED", "FAILED"]
    selected_p_statuses = st.multiselect("Payout Status", p_statuses, default=["PAID", "HELD"])
with col_s2:
    r_statuses = ["MATCHED", "DISCREPANCY"]
    selected_r_statuses = st.multiselect("Reconciliation Status", r_statuses, default=r_statuses)
with col_s3:
    search_query = st.text_input("🔍 Search Payout ID, Seller ID, or Seller Name", placeholder="e.g. PAYOUT-2026- or Hall Inc")

# Query payouts
query_where = []
if selected_p_statuses:
    p_in = ", ".join(f"'{p}'" for p in selected_p_statuses)
    query_where.append(f"p.payout_status IN ({p_in})")
if selected_r_statuses:
    r_in = ", ".join(f"'{r}'" for r in selected_r_statuses)
    query_where.append(f"p.reconciliation_status IN ({r_in})")

where_clause = " WHERE " + " AND ".join(query_where) if query_where else ""

payouts_df = db.query_df(f"""
    SELECT
        p.payout_id,
        p.seller_id,
        s.name as seller_name,
        p.batch_date,
        p.total_lines_count,
        ROUND(p.gross_sales_cents / 100.0, 2) as gross_dollars,
        ROUND(p.total_commission_cents / 100.0, 2) as commission_dollars,
        ROUND(p.total_reserve_held_cents / 100.0, 2) as reserve_dollars,
        ROUND(p.total_disputes_deducted_cents / 100.0, 2) as disputes_dollars,
        ROUND(p.net_payout_amount_cents / 100.0, 2) as net_payout_dollars,
        p.payout_status,
        p.reconciliation_status
    FROM payouts p
    JOIN sellers s ON p.seller_id = s.seller_id
    {where_clause}
    ORDER BY p.batch_date DESC
    LIMIT 1000;
""")

if search_query.strip():
    q = search_query.strip().lower()
    payouts_df = payouts_df[
        payouts_df["payout_id"].str.lower().str.contains(q)
        | payouts_df["seller_id"].str.lower().str.contains(q)
        | payouts_df["seller_name"].str.lower().str.contains(q)
    ]

# 3. Macro Visuals
col_monthly, col_status_pie = st.columns(2)

with col_monthly:
    st.subheader("Monthly Net Disbursement Volume (₹)")
    monthly_df = db.query_df("""
        SELECT
            SUBSTR(batch_date, 1, 7) as month,
            ROUND(SUM(net_payout_amount_cents) / 100.0, 2) as net_disbursed,
            COUNT(*) as batch_count
        FROM payouts
        GROUP BY month
        ORDER BY month ASC;
    """)
    if not monthly_df.empty:
        fig_monthly = px.bar(
            monthly_df,
            x="month",
            y="net_disbursed",
            color_discrete_sequence=[COLORS["primary"]],
            labels={"month": "Disbursement Month", "net_disbursed": "Net Disbursed (₹)"},
        )
        apply_plotly_white_layout(fig_monthly)
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        render_empty_state()

with col_status_pie:
    st.subheader("Payout Batch Status Breakdown")
    status_df = db.query_df("""
        SELECT payout_status, COUNT(*) as count
        FROM payouts
        GROUP BY payout_status;
    """)
    if not status_df.empty:
        fig_status = px.pie(
            status_df,
            names="payout_status",
            values="count",
            color_discrete_sequence=[COLORS["success"], COLORS["warning"], COLORS["primary"], COLORS["danger"]],
            hole=0.45,
        )
        apply_plotly_white_layout(fig_status)
        st.plotly_chart(fig_status, use_container_width=True)
    else:
        render_empty_state("No Payout Status Match", "Select at least one payout status.")

st.markdown("---")

# 4. Master Payout Directory Table
st.subheader("Payout Batches Directory")
if not payouts_df.empty:
    display_cols = [
        "payout_id",
        "seller_name",
        "batch_date",
        "total_lines_count",
        "gross_dollars",
        "commission_dollars",
        "reserve_dollars",
        "disputes_dollars",
        "net_payout_dollars",
        "payout_status",
        "reconciliation_status",
    ]
    st.dataframe(
        payouts_df[display_cols].head(100),
        use_container_width=True,
    )
    csv_payouts = payouts_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Payouts Directory (CSV)",
        data=csv_payouts,
        file_name="payout_batches_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Payout Batches Found", "Adjust your filters or clear search query above.")

st.markdown("---")

# 5. Anomaly 1 Audit Table
st.subheader("⚠️ Premature Payout Disbursements (Anomaly 1: Paid Prior to Delivery or Hold Release)")
if ano1_detected:
    ano1_rows = []
    for a in ano1_detected:
        d = a.get("details", {})
        ano1_rows.append({
            "line_id": a["entity_id"],
            "payout_id": d.get("payout_id", ""),
            "order_line_id": d.get("order_line_id", ""),
            "line_status": d.get("line_status", ""),
            "release_scheduled_date": d.get("release_scheduled_date", ""),
            "batch_date": d.get("batch_date", ""),
            "net_amount_dollars": round(d.get("net_amount_cents", 0) / 100.0, 2),
            "severity": a["severity"],
            "expected_action": a["expected_corrective_action"],
        })
    df_ano1 = pd.DataFrame(ano1_rows)
    st.dataframe(df_ano1, use_container_width=True)

    csv_prem = df_ano1.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Premature Payouts (CSV)",
        data=csv_prem,
        file_name="premature_payout_disbursements.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Disbursements: 100% of payout lines satisfied delivery and hold maturity criteria.")

st.markdown("---")

# 6. Deep-Dive Drill-Down: Detailed Payout Batch Audit
st.subheader("🔍 Payout Batch Deep-Dive & Settlement Reconciliation")

if not payouts_df.empty:
    payout_options = [
        f"{r['payout_id']} — {format_inr_rupees(r['net_payout_dollars'])} ({r['seller_name']}, Status: {r['payout_status']}, Date: {r['batch_date'][:10]})"
        for r in payouts_df.head(50).to_dict(orient="records")
    ]
    selected_payout_str = st.selectbox("Select Payout Batch for Detailed Line-Item Audit", payout_options)
    selected_payout_id = selected_payout_str.split(" — ")[0]

    p_header = db.query_df(f"""
        SELECT 
            p.payout_id,
            p.seller_id,
            s.name as seller_name,
            p.batch_date,
            p.total_lines_count,
            ROUND(p.gross_sales_cents / 100.0, 2) as gross_dollars,
            ROUND(p.total_commission_cents / 100.0, 2) as commission_dollars,
            ROUND(p.total_reserve_held_cents / 100.0, 2) as reserve_dollars,
            ROUND(p.total_disputes_deducted_cents / 100.0, 2) as disputes_dollars,
            ROUND(p.net_payout_amount_cents / 100.0, 2) as net_dollars,
            p.payout_status,
            p.reconciliation_status
        FROM payouts p
        JOIN sellers s ON p.seller_id = s.seller_id
        WHERE p.payout_id = '{selected_payout_id}';
    """).iloc[0]

    c_p1, c_p2, c_p3, c_p4 = st.columns(4)
    with c_p1:
        render_metric_card("Payout ID", p_header["payout_id"], f"Seller: {p_header['seller_name']}")
    with c_p2:
        render_metric_card("Net Amount", format_inr_rupees(p_header['net_dollars']), f"Gross: {format_inr_rupees(p_header['gross_dollars'])}")
    with c_p3:
        render_metric_card(
            "Payout Status", 
            p_header["payout_status"], 
            f"Batch Date: {p_header['batch_date'][:10]}",
            delta_color="success" if p_header["payout_status"] == "PAID" else "warning"
        )
    with c_p4:
        render_metric_card(
            "Reconciliation", 
            p_header["reconciliation_status"], 
            "Header vs Child Lines",
            delta_color="success" if p_header["reconciliation_status"] == "MATCHED" else "danger"
        )

    tab_lines, tab_events = st.tabs([
        "🛒 Child Payout Lines",
        "📜 Payout Gateway Event History"
    ])

    with tab_lines:
        st.markdown(f"#### Settlement Lines for `{selected_payout_id}`")
        lines_df = db.query_df(f"""
            SELECT 
                pl.line_id,
                pl.order_line_id,
                ROUND(pl.gross_amount_cents / 100.0, 2) as gross_dollars,
                ROUND(pl.commission_deducted_cents / 100.0, 2) as commission_dollars,
                ROUND(pl.reserve_deducted_cents / 100.0, 2) as reserve_dollars,
                ROUND(pl.dispute_deducted_cents / 100.0, 2) as dispute_dollars,
                ROUND(pl.net_line_amount_cents / 100.0, 2) as net_line_dollars
            FROM payout_lines pl
            WHERE pl.payout_id = '{selected_payout_id}';
        """)
        if not lines_df.empty:
            st.dataframe(lines_df, use_container_width=True)
            # Arithmetic verification
            lines_sum = lines_df["net_line_dollars"].sum()
            variance = round(p_header["net_dollars"] - lines_sum, 2)
            if abs(variance) < 0.01:
                st.success(f"✅ Exact Balance: Sum of child lines ({format_inr_rupees(lines_sum)}) matches payout header net ({format_inr_rupees(p_header['net_dollars'])}).")
            else:
                st.error(f"🚨 Anomaly 5 Discrepancy: Payout header ({format_inr_rupees(p_header['net_dollars'])}) does NOT match sum of lines ({format_inr_rupees(lines_sum)})! Variance: {format_inr_rupees(variance)}")
        else:
            render_empty_state("No Lines Found", "No child settlement lines found for this payout batch.")

    with tab_events:
        st.markdown(f"#### Banking Gateway Events for `{selected_payout_id}`")
        events_df = db.query_df(f"""
            SELECT 
                event_id,
                previous_status,
                new_status,
                gateway_reference,
                notes,
                created_at
            FROM payout_events
            WHERE payout_id = '{selected_payout_id}'
            ORDER BY created_at ASC;
        """)
        if not events_df.empty:
            st.dataframe(events_df, use_container_width=True)
        else:
            render_empty_state("No Gateway Events", "No disbursement gateway transitions recorded.")
else:
    render_empty_state("No Payout Selected", "Select or loosen filter criteria above.")
