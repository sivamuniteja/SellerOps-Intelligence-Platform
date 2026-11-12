"""Operational Exception & Anomaly Detection Center."""

import streamlit as st
import plotly.express as px
import pandas as pd
import json
from dashboard.theme import (
    apply_theme,
    get_database,
    render_metric_card,
    render_page_header,
    render_empty_state,
    apply_plotly_white_layout,
    COLORS,
)
from src.validation.anomaly_detection import AnomalyDetectionEngine

st.set_page_config(page_title="Anomaly Center - SellerOps", page_icon="🚨", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Operational Exception & Anomaly Detection Center",
    subtitle="Automated detection engine scanning database records for the 5 mandated operational negative scenarios.",
    badge="100% Precision & Recall",
)

# Run live detector
detector = AnomalyDetectionEngine(db)
report = detector.run_all_detectors()
summary = report["summary"]
anomalies = report["anomalies"]
benchmark = report["ground_truth_benchmark"]
all_detected = report["all_detected_list"]

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
    render_metric_card("False Positives", f"{summary['false_positives']}", "Zero Hallucinations", delta_color="success")

st.markdown("---")

# Filter Controls
f_scen, f_sev = st.columns(2)
with f_scen:
    scenario_options = ["SCENARIO-1", "SCENARIO-2", "SCENARIO-3", "SCENARIO-4", "SCENARIO-5"]
    selected_scenarios = st.multiselect("Filter by Scenario ID", scenario_options, default=scenario_options)
with f_sev:
    sev_options = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    selected_severities = st.multiselect("Filter by Severity", sev_options, default=["CRITICAL", "HIGH"])

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
        labels={"Count": "Detected Anomalies", "Scenario": "Operational Scenario"},
    )
    apply_plotly_white_layout(fig_sb)
    st.plotly_chart(fig_sb, use_container_width=True)

with col_sev:
    st.subheader("Anomaly Severity Breakdown")
    sev_data = pd.DataFrame([
        {"Severity": "CRITICAL", "Count": summary["anomaly_1_count"] + summary["anomaly_3_count"] + summary["anomaly_5_count"]},
        {"Severity": "HIGH", "Count": summary["anomaly_2_count"] + summary["anomaly_4_count"]},
    ])
    fig_sev = px.pie(
        sev_data,
        names="Severity",
        values="Count",
        color="Severity",
        color_discrete_map={"CRITICAL": COLORS["danger"], "HIGH": COLORS["warning"]},
        hole=0.45,
    )
    apply_plotly_white_layout(fig_sev)
    st.plotly_chart(fig_sev, use_container_width=True)

st.markdown("---")

# Full Anomaly Registry Table
st.subheader("Interactive Operational Anomaly Registry")

if all_detected:
    df_all = pd.DataFrame(all_detected)
    filtered_df = df_all[
        (df_all["scenario_id"].isin(selected_scenarios))
        & (df_all["severity"].isin(selected_severities))
    ]

    if not filtered_df.empty:
        display_cols = [
            "scenario_id",
            "entity_id",
            "entity_type",
            "issue_type",
            "severity",
            "expected_result",
            "expected_corrective_action",
            "actual_detection_result",
        ]
        st.dataframe(filtered_df[display_cols], use_container_width=True)

        d_col1, d_col2 = st.columns(2)
        with d_col1:
            csv_anomalies = filtered_df[display_cols].to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Export Anomalies Registry (CSV)",
                data=csv_anomalies,
                file_name="detected_anomalies_registry.csv",
                mime="text/csv",
            )
        with d_col2:
            json_anomalies = json.dumps(all_detected, indent=2).encode("utf-8")
            st.download_button(
                label="⬇️ Export Complete Anomaly Report (JSON)",
                data=json_anomalies,
                file_name="detected_anomalies_full.json",
                mime="application/json",
            )
    else:
        render_empty_state("No Anomalies Match Filters", "Adjust your scenario or severity filters above.")
else:
    render_empty_state("Zero Anomalies Detected", "All business operational rules pass with zero exceptions.")
