"""Reports & Multi-Format Data Exports Console."""

import streamlit as st
import pandas as pd
import json
from dashboard.theme import apply_theme, get_database, render_metric_card
from src.exports.csv_export import CsvExporter
from src.exports.json_export import JsonExporter

st.set_page_config(page_title="Reports & Exports - SellerOps", page_icon="📄", layout="wide")
apply_theme()
db = get_database()

st.title("Reports & Multi-Format Data Exports")
st.markdown("Download enterprise operational datasets, financial audit logs, and compliance summaries in CSV, JSON, and SQL.")

c1, c2, c3 = st.columns(3)
with c1:
    render_metric_card("Export Formats", "CSV / JSON / SQL", "Standard Formats")
with c2:
    render_metric_card("Tables Available", "11 Tables", "Full Relational Schema")
with c3:
    render_metric_card("Total Relational Rows", f"{db.row_count('orders') + db.row_count('fulfillments') + db.row_count('listings'):,}+", "Ready to Stream")

st.markdown("---")

col_export, col_summary = st.columns([1, 1])

with col_export:
    st.subheader("1. Download Table Datasets")
    table_to_export = st.selectbox(
        "Select Table to Export",
        [
            "sellers", "listings", "orders", "fulfillments",
            "reviews", "disputes", "order_settlements",
            "payout_batches", "payout_lines", "anomalies_ground_truth"
        ]
    )

    limit_rows = st.number_input("Maximum Rows (0 for all)", min_value=0, max_value=100000, value=1000, step=500)
    limit_clause = f" LIMIT {limit_rows}" if limit_rows > 0 else ""

    export_df = db.query_df(f"SELECT * FROM {table_to_export}{limit_clause};")

    csv_data = export_df.to_csv(index=False).encode("utf-8")
    json_data = export_df.to_json(orient="records", indent=2).encode("utf-8")

    st.download_button(
        label=f"⬇️ Download {table_to_export}.csv",
        data=csv_data,
        file_name=f"{table_to_export}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.download_button(
        label=f"⬇️ Download {table_to_export}.json",
        data=json_data,
        file_name=f"{table_to_export}.json",
        mime="application/json",
        use_container_width=True,
    )

with col_summary:
    st.subheader("2. Operational Executive Summary Report")
    st.markdown("Generate a consolidated operational report with high-level marketplace metrics.")

    if st.button("Generate Consolidated Executive Report", use_container_width=True):
        summary_q = """
            SELECT
                (SELECT COUNT(*) FROM sellers) as total_sellers,
                (SELECT COUNT(*) FROM listings) as total_listings,
                (SELECT COUNT(*) FROM orders) as total_orders,
                (SELECT ROUND(SUM(gross_amount), 2) FROM orders) as total_gmv,
                (SELECT ROUND(SUM(commission_amount), 2) FROM order_settlements) as total_commission,
                (SELECT COUNT(*) FROM disputes) as total_disputes,
                (SELECT COUNT(*) FROM anomalies_ground_truth) as total_anomalies;
        """
        exec_df = db.query_df(summary_q)
        st.dataframe(exec_df, use_container_width=True)

        exec_json = exec_df.to_json(orient="records", indent=2)
        st.download_button(
            label="⬇️ Download Executive Summary (JSON)",
            data=exec_json,
            file_name="sellerops_executive_summary.json",
            mime="application/json",
            use_container_width=True,
        )

st.markdown("---")
st.subheader("3. Anomaly & Audit Report Export")
st.markdown("Export the complete ground-truth registry along with detection audit trails:")

anomalies_df = db.query_df("SELECT * FROM anomalies_ground_truth;")
ano_csv = anomalies_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇️ Download All 115 Operational Anomalies (CSV)",
    data=ano_csv,
    file_name="operational_anomalies_audit.csv",
    mime="text/csv",
)
