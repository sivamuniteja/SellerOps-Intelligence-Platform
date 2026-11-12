"""Fulfillment Tracking and Carrier SLA Console."""

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

st.set_page_config(page_title="Fulfillment SLA - SellerOps", page_icon="🚚", layout="wide")
apply_theme()
db = get_database()

render_page_header(
    title="Fulfillment Operations & Logistics SLA",
    subtitle="Carrier transit metrics, dispatch delays, and 48-hour SLA compliance tracking across carriers.",
    badge="Logistics SLA",
)

# High level KPIs
flf_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_fulfillments,
        SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) as on_time_count,
        SUM(CASE WHEN sla_status = 'LATE' THEN 1 ELSE 0 END) as late_count,
        ROUND(AVG(transit_days), 1) as avg_transit_days,
        ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as on_time_pct
    FROM fulfillments
    WHERE sla_status IN ('ON_TIME', 'LATE');
""")
tot_f = int(flf_kpis["total_fulfillments"].iloc[0] or 0)
ontime_f = int(flf_kpis["on_time_count"].iloc[0] or 0)
late_f = int(flf_kpis["late_count"].iloc[0] or 0)
avg_t = float(flf_kpis["avg_transit_days"].iloc[0] or 0.0)
ontime_pct = float(flf_kpis["on_time_pct"].iloc[0] or 0.0)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Dispatched", f"{tot_f:,}", "Fulfilled Shipments")
with c2:
    render_metric_card("On-Time Deliveries", f"{ontime_f:,}", f"{ontime_pct:.1f}% Compliance")
with c3:
    render_metric_card("Late Shipments", f"{late_f:,}", "Breached 48h SLA", delta_color="danger")
with c4:
    render_metric_card("Avg Transit Days", f"{avg_t} Days", "Door-to-Door")
with c5:
    render_metric_card("Carriers Integrated", "4 Partners", "FedEx, UPS, USPS, DHL")

st.markdown("---")

# Filter Controls
f_car, f_sla = st.columns(2)
with f_car:
    carriers = ["FedEx", "UPS", "USPS", "DHL"]
    selected_carriers = st.multiselect("Select Carrier", carriers, default=carriers)
with f_sla:
    sla_options = ["ON_TIME", "LATE", "IN_TRANSIT", "CANCELLED"]
    selected_sla = st.multiselect("SLA Status", sla_options, default=["ON_TIME", "LATE"])

col_carrier, col_transit = st.columns(2)

with col_carrier:
    st.subheader("Carrier Performance Scorecard")
    carrier_scorecard = db.query_df("""
        SELECT
            carrier,
            COUNT(*) as total_shipments,
            SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) as on_time_count,
            ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as on_time_pct
        FROM fulfillments
        WHERE carrier IS NOT NULL
        GROUP BY carrier
        ORDER BY on_time_pct DESC;
    """)
    filtered_carrier = carrier_scorecard[carrier_scorecard["carrier"].isin(selected_carriers)]
    if not filtered_carrier.empty:
        fig_carrier = px.bar(
            filtered_carrier,
            x="carrier",
            y="on_time_pct",
            color="carrier",
            color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["text_secondary"]],
            labels={"carrier": "Carrier", "on_time_pct": "On-Time Compliance (%)"},
        )
        apply_plotly_white_layout(fig_carrier)
        st.plotly_chart(fig_carrier, use_container_width=True)
    else:
        render_empty_state("No Carrier Selected", "Select at least one logistics carrier.")

with col_transit:
    st.subheader("Transit Duration Distribution (Days)")
    transit_df = db.query_df("""
        SELECT transit_days, COUNT(*) as count
        FROM fulfillments
        WHERE transit_days IS NOT NULL AND carrier IN ('FedEx', 'UPS', 'USPS', 'DHL')
        GROUP BY transit_days
        ORDER BY transit_days ASC;
    """)
    if not transit_df.empty:
        fig_transit = px.bar(
            transit_df,
            x="transit_days",
            y="count",
            color_discrete_sequence=[COLORS["primary"]],
            labels={"transit_days": "Transit Duration (Days)", "count": "Shipments Count"},
        )
        apply_plotly_white_layout(fig_transit)
        st.plotly_chart(fig_transit, use_container_width=True)
    else:
        render_empty_state()

st.markdown("---")

# Late Shipments SLA Audit Table
st.subheader("Late Shipment Violations Audit (Dispatched > 48h SLA)")
late_shipments = db.query_df("""
    SELECT
        f.fulfillment_id,
        f.order_line_id,
        f.order_id,
        f.seller_id,
        f.carrier,
        f.tracking_number,
        f.dispatched_at,
        f.delivered_at,
        f.transit_days,
        f.sla_status
    FROM fulfillments f
    WHERE f.sla_status = 'LATE'
    LIMIT 100;
""")
st.dataframe(late_shipments, use_container_width=True)

csv_late = late_shipments.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Export Late Shipments Audit (CSV)",
    data=csv_late,
    file_name="late_shipment_violations.csv",
    mime="text/csv",
)
