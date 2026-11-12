"""Operational Exception & Anomaly Detection Center."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS
from src.validation.anomaly_detection import AnomalyDetectionEngine

st.set_page_config(page_title="Anomaly Center - SellerOps", page_icon="🚨", layout="wide")
apply_theme()
db = get_database()

st.title("Operational Exception & Anomaly Detection Center")
st.markdown("Automated detection engine scanning database records for the 5 mandated operational negative scenarios.")

# Run live detector
detector = AnomalyDetectionEngine(db)
report = detector.run_all_detectors()
summary = report["summary"]
anomalies = report["anomalies"]
benchmark = report["ground_truth_benchmark"]

# Top Metrics
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Anomalies", f"{summary['total_anomalies_detected']}", "5 Injected Scenarios", delta_color="danger")
with c2:
    render_metric_card("Detection Precision", f"{summary['precision'] * 100:.1f}%", f"{benchmark['true_positives']} TP / {benchmark['false_positives']} FP")
with c3:
    render_metric_card("Detection Recall", f"{summary['recall'] * 100:.1f}%", f"{benchmark['false_negatives']} FN")
with c4:
    render_metric_card("F1-Score Benchmark", f"{summary['f1_score'] * 100:.1f}%", "Harmonic Mean")
with c5:
    render_metric_card("Ground Truth Status", "115 Verified", "Deterministic Seed 42")

st.markdown("---")

# Chart summary
col_bar, col_sev = st.columns(2)

with col_bar:
    st.subheader("Detected Anomalies by Scenario Type")
    scenario_counts = pd.DataFrame([
        {"Scenario": "1. Premature Payout", "Count": summary["anomaly_1_count"], "Severity": "CRITICAL"},
        {"Scenario": "2. Double Commission", "Count": summary["anomaly_2_count"], "Severity": "HIGH"},
        {"Scenario": "3. Suspended Seller Active", "Count": summary["anomaly_3_count"], "Severity": "CRITICAL"},
        {"Scenario": "4. Unclawbacked Dispute", "Count": summary["anomaly_4_count"], "Severity": "HIGH"},
        {"Scenario": "5. Payout Mismatch", "Count": summary["anomaly_5_count"], "Severity": "CRITICAL"},
    ])
    fig_sb = px.bar(
        scenario_counts,
        x="Count",
        y="Scenario",
        orientation="h",
        color="Severity",
        color_discrete_map={"CRITICAL": COLORS["danger"], "HIGH": COLORS["warning"]},
        text="Count",
    )
    apply_plotly_white_layout(fig_sb)
    fig_sb.update_traces(textposition="outside")
    st.plotly_chart(fig_sb, use_container_width=True)

with col_sev:
    st.subheader("Severity Distribution")
    sev_df = pd.DataFrame([
        {"Severity": "CRITICAL", "Count": summary["anomaly_1_count"] + summary["anomaly_3_count"] + summary["anomaly_5_count"]},
        {"Severity": "HIGH", "Count": summary["anomaly_2_count"] + summary["anomaly_4_count"]},
    ])
    fig_sev = px.pie(
        sev_df,
        names="Severity",
        values="Count",
        color="Severity",
        color_discrete_map={"CRITICAL": COLORS["danger"], "HIGH": COLORS["warning"]},
        hole=0.45,
    )
    apply_plotly_white_layout(fig_sev)
    st.plotly_chart(fig_sev, use_container_width=True)

st.markdown("---")
st.subheader("Detailed Anomaly Audit Explorer")

tab1, tab2, tab3, tab4, tab5, tab_gt = st.tabs([
    "1. Premature Payouts",
    "2. Double Commissions",
    "3. Suspended Seller Activity",
    "4. Unclawbacked Disputes",
    "5. Payout Mismatches",
    "Ground Truth Registry",
])

with tab1:
    st.markdown("#### Anomaly Scenario 1: Payout Before Delivery or Hold Release")
    st.markdown("Payout lines where the order is not confirmed delivered, or where the payout batch date occurred prior to reserve release date.")
    df1 = pd.DataFrame(anomalies["premature_payouts"])
    st.dataframe(df1, use_container_width=True)

with tab2:
    st.markdown("#### Anomaly Scenario 2: Commission Applied Twice")
    st.markdown("Order settlements where the recorded platform commission is double the standard contractual rate.")
    df2 = pd.DataFrame(anomalies["double_commissions"])
    st.dataframe(df2, use_container_width=True)

with tab3:
    st.markdown("#### Anomaly Scenario 3: Suspended Seller Continues Listing")
    st.markdown("Listings with status ACTIVE belonging to sellers who are officially flagged as SUSPENDED.")
    df3 = pd.DataFrame(anomalies["suspended_seller_activity"])
    st.dataframe(df3, use_container_width=True)

with tab4:
    st.markdown("#### Anomaly Scenario 4: Dispute Not Deducted (Unclawbacked Chargeback)")
    st.markdown("Disputes decided in buyer's favor or lost as chargebacks, where the refund was not deducted from seller payout balance.")
    df4 = pd.DataFrame(anomalies["unclawbacked_disputes"])
    st.dataframe(df4, use_container_width=True)

with tab5:
    st.markdown("#### Anomaly Scenario 5: Payout Total Does Not Equal Payout Lines")
    st.markdown("Payout batches where the header net payout amount deviates by $125.00 from the arithmetic sum of child line items.")
    df5 = pd.DataFrame(anomalies["payout_total_mismatches"])
    st.dataframe(df5, use_container_width=True)

with tab_gt:
    st.markdown("#### Synthetic Ground-Truth Registry")
    st.markdown("Deterministic target records tagged during generation used as benchmark ground truth for precision/recall evaluation.")
    gt_df = db.query_df("SELECT * FROM anomalies_ground_truth ORDER BY anomaly_id ASC;")
    st.dataframe(gt_df, use_container_width=True)
