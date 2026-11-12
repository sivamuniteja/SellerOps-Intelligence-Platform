"""Fulfillment Tracking and Carrier SLA Console."""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.theme import apply_theme, get_database, render_metric_card, apply_plotly_white_layout, COLORS

st.set_page_config(page_title="Fulfillment SLA - SellerOps", page_icon="🚚", layout="wide")
apply_theme()
db = get_database()

st.title("Fulfillment Operations & Logistics SLA")
st.markdown("Carrier transit metrics, dispatch delays, and 48-hour SLA compliance tracking.")

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
tot_f = flf_kpis["total_fulfillments"].iloc[0]
ontime_f = flf_kpis["on_time_count"].iloc[0]
late_f = flf_kpis["late_count"].iloc[0]
avg_t = flf_kpis["avg_transit_days"].iloc[0]
ontime_pct = flf_kpis["on_time_pct"].iloc[0]

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

col_carrier, col_transit = st.columns(2)

with col_carrier:
    st.subheader("Carrier Performance Scorecard")
    carrier_scorecard = db.query_df("""
        SELECT
            carrier,
            COUNT(*) as total_shipments,
            SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) as on_time,
            SUM(CASE WHEN sla_status = 'LATE' THEN 1 ELSE 0 END) as late,
            ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as on_time_rate,
            ROUND(AVG(transit_days), 1) as avg_transit
        FROM fulfillments
        WHERE carrier IS NOT NULL AND sla_status IN ('ON_TIME', 'LATE')
        GROUP BY carrier
        ORDER BY total_shipments DESC;
    """)
    fig_cp = px.bar(
        carrier_scorecard,
        x="carrier",
        y="on_time_rate",
        text="on_time_rate",
        color="carrier",
        color_discrete_sequence=[COLORS["primary"], COLORS["success"], COLORS["warning"], COLORS["text_secondary"]],
        labels={"on_time_rate": "On-Time Compliance (%)", "carrier": "Carrier"},
    )
    fig_cp.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    apply_plotly_white_layout(fig_cp)
    fig_cp.update_layout(showlegend=False, yaxis_range=[85, 100])
    st.plotly_chart(fig_cp, use_container_width=True)

with col_transit:
    st.subheader("Transit Days Distribution")
    transit_dist = db.query_df("""
        SELECT transit_days, COUNT(*) as shipments
        FROM fulfillments
        WHERE transit_days IS NOT NULL
        GROUP BY transit_days
        ORDER BY transit_days ASC;
    """)
    fig_td = px.bar(
        transit_dist,
        x="transit_days",
        y="shipments",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"transit_days": "Transit Duration (Days)", "shipments": "Total Shipments"},
    )
    apply_plotly_white_layout(fig_td)
    st.plotly_chart(fig_td, use_container_width=True)

st.markdown("---")
st.subheader("Late Shipment Exception Audit")

f1, f2 = st.columns([1, 2])
with f1:
    sel_carrier = st.selectbox("Filter Carrier", ["ALL"] + list(carrier_scorecard["carrier"]))
with f2:
    search_tracking = st.text_input("Search Tracking Number or Order ID", "")

late_q = """
    SELECT
        f.fulfillment_id,
        f.order_id,
        f.carrier,
        f.tracking_number,
        o.order_date,
        f.dispatched_at,
        ROUND((JULIANDAY(f.dispatched_at) - JULIANDAY(o.order_date)) * 24.0, 1) as dispatch_delay_hours,
        f.delivered_at,
        f.transit_days,
        f.sla_status
    FROM fulfillments f
    JOIN orders o ON f.order_id = o.order_id
    WHERE f.sla_status = 'LATE'
"""
params = []
if sel_carrier != "ALL":
    late_q += " AND f.carrier = ?"
    params.append(sel_carrier)
if search_tracking:
    late_q += " AND (f.tracking_number LIKE ? OR f.order_id LIKE ?)"
    params.extend([f"%{search_tracking}%", f"%{search_tracking}%"])

late_q += " ORDER BY dispatch_delay_hours DESC LIMIT 200;"

late_table = db.query_df(late_q, tuple(params))
st.dataframe(late_table, use_container_width=True)
