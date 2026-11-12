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
    subtitle="Carrier transit metrics, dispatch delays, 48-hour SLA compliance, and package event history.",
    badge="Logistics SLA",
)

# 1. Macro Fulfillment KPIs
flf_kpis = db.query_df("""
    SELECT
        COUNT(*) as total_fulfillments,
        SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) as on_time_count,
        SUM(CASE WHEN sla_status = 'LATE' THEN 1 ELSE 0 END) as late_count,
        ROUND(AVG(transit_days), 1) as avg_transit_days,
        ROUND(SUM(CASE WHEN sla_status = 'ON_TIME' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as on_time_pct
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
    render_metric_card("Total Dispatched", f"{tot_f:,}", "Fulfilled Packages")
with c2:
    render_metric_card("On-Time Deliveries", f"{ontime_f:,}", f"{ontime_pct:.1f}% Compliance", delta_color="success")
with c3:
    render_metric_card("Late Shipments", f"{late_f:,}", "Breached 48h SLA", delta_color="danger" if late_f > 0 else "success")
with c4:
    render_metric_card("Avg Transit Days", f"{avg_t} Days", "Door-to-Door")
with c5:
    render_metric_card("Carriers Integrated", "4 Carriers", "FedEx, UPS, USPS, DHL")

st.markdown("---")

# 2. Interactive Filter Controls
st.markdown("#### Filter Logistics Pipeline")
f_car, f_sla, f_days, f_search = st.columns([1, 1, 1.5, 1.5])
with f_car:
    carriers = ["FedEx", "UPS", "USPS", "DHL"]
    selected_carriers = st.multiselect("Carrier", carriers, default=carriers)
with f_sla:
    sla_options = ["ON_TIME", "LATE", "IN_TRANSIT", "CANCELLED"]
    selected_sla = st.multiselect("SLA Status", sla_options, default=["ON_TIME", "LATE"])
with f_days:
    transit_range = st.slider("Transit Days", 1, 14, (1, 14), step=1)
with f_search:
    search_query = st.text_input("🔍 Search Tracking #, Order Line, or Fulfillment ID", placeholder="e.g. FUL- or TRK-")

# Query fulfillments
query_where = []
if selected_carriers:
    car_in = ", ".join(f"'{c}'" for c in selected_carriers)
    query_where.append(f"f.carrier IN ({car_in})")
if selected_sla:
    sla_in = ", ".join(f"'{s}'" for s in selected_sla)
    query_where.append(f"f.sla_status IN ({sla_in})")

query_where.append(f"COALESCE(f.transit_days, 1) >= {transit_range[0]} AND COALESCE(f.transit_days, 1) <= {transit_range[1]}")

where_clause = " WHERE " + " AND ".join(query_where) if query_where else ""

fulfillments_df = db.query_df(f"""
    SELECT
        f.fulfillment_id,
        f.order_line_id,
        f.order_id,
        f.seller_id,
        s.name as seller_name,
        f.carrier,
        f.tracking_number,
        f.dispatched_at,
        f.expected_delivery_at,
        f.delivered_at,
        f.sla_status,
        f.transit_days
    FROM fulfillments f
    JOIN sellers s ON f.seller_id = s.seller_id
    {where_clause}
    ORDER BY f.dispatched_at DESC
    LIMIT 1000;
""")

if search_query.strip():
    q = search_query.strip().lower()
    fulfillments_df = fulfillments_df[
        fulfillments_df["fulfillment_id"].str.lower().str.contains(q)
        | fulfillments_df["order_line_id"].str.lower().str.contains(q)
        | fulfillments_df["tracking_number"].str.lower().str.contains(q)
        | fulfillments_df["seller_name"].str.lower().str.contains(q)
    ]

# 3. Macro Carrier Visuals
col_carrier, col_transit = st.columns(2)

with col_carrier:
    st.subheader("Carrier Performance Scorecard (On-Time %)")
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

# 4. Master Fulfillment Directory Table
st.subheader("Fulfillment Directory")
if not fulfillments_df.empty:
    display_cols = [
        "fulfillment_id",
        "order_line_id",
        "seller_name",
        "carrier",
        "tracking_number",
        "dispatched_at",
        "expected_delivery_at",
        "delivered_at",
        "sla_status",
        "transit_days",
    ]
    st.dataframe(
        fulfillments_df[display_cols].head(100),
        use_container_width=True,
    )
    csv_flf = fulfillments_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Fulfillments (CSV)",
        data=csv_flf,
        file_name="fulfillments_directory.csv",
        mime="text/csv",
    )
else:
    render_empty_state("No Fulfillments Found", "Zero fulfillments match the selected filters.")

st.markdown("---")

# 5. Late Shipments SLA Audit Table
st.subheader("⚠️ Late Shipment Exceptions Audit (SLA = LATE)")
late_shipments = db.query_df("""
    SELECT
        f.fulfillment_id,
        f.order_line_id,
        f.order_id,
        f.seller_id,
        s.name as seller_name,
        f.carrier,
        f.tracking_number,
        f.dispatched_at,
        f.expected_delivery_at,
        f.delivered_at,
        f.transit_days,
        f.sla_status
    FROM fulfillments f
    JOIN sellers s ON f.seller_id = s.seller_id
    WHERE f.sla_status = 'LATE'
    ORDER BY f.dispatched_at DESC
    LIMIT 100;
""")

if not late_shipments.empty:
    st.dataframe(late_shipments, use_container_width=True)
    csv_late = late_shipments.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Late Shipments Audit (CSV)",
        data=csv_late,
        file_name="late_shipment_exceptions.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Clean Logistics: Zero late shipment exceptions detected.")

st.markdown("---")

# 6. Deep-Dive Drill-Down: Fulfillment Details & Event History
st.subheader("🔍 Fulfillment Deep-Dive & Carrier Event Timeline")

if not fulfillments_df.empty:
    flf_options = [
        f"{r['fulfillment_id']} — {r['carrier']} ({r['sla_status']}, Tracking: {r['tracking_number']})"
        for r in fulfillments_df.head(50).to_dict(orient="records")
    ]
    selected_flf_str = st.selectbox("Select Fulfillment for Event History Audit", flf_options)
    selected_flf_id = selected_flf_str.split(" — ")[0]

    flf_record = db.query_df(f"""
        SELECT 
            f.fulfillment_id,
            f.order_line_id,
            f.order_id,
            f.seller_id,
            s.name as seller_name,
            f.carrier,
            f.tracking_number,
            f.dispatched_at,
            f.expected_delivery_at,
            f.delivered_at,
            f.sla_status,
            f.transit_days
        FROM fulfillments f
        JOIN sellers s ON f.seller_id = s.seller_id
        WHERE f.fulfillment_id = '{selected_flf_id}';
    """).iloc[0]

    c_f1, c_f2, c_f3, c_f4 = st.columns(4)
    with c_f1:
        render_metric_card("Carrier & Tracking", flf_record["carrier"], flf_record["tracking_number"])
    with c_f2:
        render_metric_card(
            "SLA Compliance", 
            flf_record["sla_status"], 
            f"Transit: {flf_record['transit_days']} Days",
            delta_color="success" if flf_record["sla_status"] == "ON_TIME" else "danger"
        )
    with c_f3:
        render_metric_card("Dispatched At", str(flf_record["dispatched_at"]), f"Seller: {flf_record['seller_name']}")
    with c_f4:
        render_metric_card("Delivered At", str(flf_record["delivered_at"]), f"Expected: {str(flf_record['expected_delivery_at'])[:10]}")

    st.markdown(f"#### Fulfillment Event History Timeline for `{selected_flf_id}`")
    events_df = db.query_df(f"""
        SELECT 
            event_id,
            event_type,
            event_timestamp,
            location,
            notes
        FROM fulfillment_events
        WHERE fulfillment_id = '{selected_flf_id}'
        ORDER BY event_timestamp ASC;
    """)

    if not events_df.empty:
        st.dataframe(events_df, use_container_width=True)
    else:
        render_empty_state("No Event Milestones", "No tracking milestone events recorded for this fulfillment package.")
else:
    render_empty_state("No Fulfillment Selected", "Select or loosen filter criteria above.")
