"""Enterprise White Theme and Reusable UI Components for SellerOps Dashboard."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from typing import Optional, Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.database.connection import get_db
from src.currency import format_inr, format_inr_paise, from_paise, to_paise


def format_inr_rupees(amount: float, compact: bool = False) -> str:
    """Format an amount given in whole rupees (or float) to Indian Rupee notation (₹)."""
    return format_inr(amount, compact=compact)


# Mandatory Enterprise Color Palette
COLORS = {
    "bg": "#FFFFFF",
    "surface": "#FFFFFF",
    "sidebar_bg": "#FFFFFF",
    "text_primary": "#111827",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "subtle": "#F8FAFC",
    "primary": "#2563EB",
    "primary_light": "#DBEAFE",
    "success": "#16A34A",
    "success_light": "#DCFCE7",
    "warning": "#D97706",
    "warning_light": "#FEF3C7",
    "danger": "#DC2626",
    "danger_light": "#FEE2E2",
}

CUSTOM_CSS = """
<style>
    /* Global Pure White Enterprise Theme */
    [data-testid="stAppViewContainer"], 
    [data-testid="stHeader"],
    .main,
    .stApp {
        background-color: #FFFFFF !important;
        color: #111827 !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }

    [data-testid="stSidebar"] * {
        color: #111827 !important;
    }
    
    html, body, p, span, div, label, li {
        color: #111827 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", Helvetica, Arial, sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #111827 !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }

    /* Enterprise Metric Card */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px 18px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        height: 100%;
        min-height: 125px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
    }
    .metric-card:hover {
        border-color: #CBD5E1;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07);
    }
    .metric-header {
        margin-bottom: 6px;
    }
    .metric-title {
        font-size: 0.78rem;
        font-weight: 600;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        line-height: 1.35;
        white-space: normal;
        word-break: break-word;
    }
    .metric-value-container {
        flex-grow: 1;
        display: flex;
        align-items: center;
        margin: 4px 0;
    }
    .metric-value {
        font-size: clamp(1.15rem, 1.85vw, 1.65rem);
        font-weight: 700;
        color: #111827 !important;
        line-height: 1.2;
        word-break: break-word;
        overflow-wrap: anywhere;
        white-space: normal;
    }
    .metric-subtitle {
        font-size: 0.80rem;
        color: #64748B !important;
        margin-top: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
        line-height: 1.35;
        word-break: break-word;
    }

    /* Column card alignment */
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
    }
    [data-testid="column"] > div {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    [data-testid="column"] .metric-card {
        flex: 1 1 auto;
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 3px 9px;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 4px;
        line-height: 1.3;
    }
    .badge-success { background-color: #DCFCE7; color: #166534 !important; border: 1px solid #BBF7D0; }
    .badge-warning { background-color: #FEF3C7; color: #92400E !important; border: 1px solid #FDE68A; }
    .badge-danger { background-color: #FEE2E2; color: #991B1B !important; border: 1px solid #FECACA; }
    .badge-info { background-color: #DBEAFE; color: #1E40AF !important; border: 1px solid #BFDBFE; }
    .badge-neutral { background-color: #F1F5F9; color: #475569 !important; border: 1px solid #E2E8F0; }

    /* Tables & DataFrames */
    [data-testid="stDataFrame"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        background-color: #FFFFFF !important;
        overflow-x: auto !important;
        width: 100% !important;
    }

    /* Multi-select and Filter Enhancements */
    .stMultiSelect [data-baseweb="select"] {
        min-height: 42px !important;
        border-color: #E2E8F0 !important;
        border-radius: 6px !important;
    }
    .stMultiSelect [data-baseweb="tag"] {
        max-width: 100% !important;
        white-space: normal !important;
        height: auto !important;
        padding: 3px 8px !important;
        margin: 2px 3px 2px 0 !important;
        background-color: #EFF6FF !important;
        border: 1px solid #BFDBFE !important;
        border-radius: 4px !important;
    }
    .stMultiSelect [data-baseweb="tag"] span {
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        color: #1E40AF !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }
    .stSelectbox [data-baseweb="select"], .stTextInput > div > div {
        border-color: #E2E8F0 !important;
        border-radius: 6px !important;
    }
    .stSelectbox label, .stMultiSelect label, .stSlider label, .stTextInput label {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #374151 !important;
        margin-bottom: 4px !important;
    }

    /* Filter Panels */
    .filter-panel {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
    }

    /* Empty and Error States */
    .empty-state {
        background-color: #F8FAFC;
        border: 1px dashed #CBD5E1;
        border-radius: 8px;
        padding: 32px 20px;
        text-align: center;
        margin: 20px 0;
    }
    .empty-state-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 6px;
    }
    .empty-state-desc {
        font-size: 0.88rem;
        color: #64748B;
    }

    /* Buttons */
    .stButton>button {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 6px 16px !important;
    }
    .stButton>button:hover {
        background-color: #1D4ED8 !important;
    }

    /* Section divider */
    hr {
        border: none;
        height: 1px;
        background-color: #E2E8F0;
        margin: 24px 0;
    }

    /* Clean Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
"""


def apply_theme():
    """Inject pure white enterprise CSS into the active Streamlit page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    render_sidebar_branding()


@st.cache_resource
def get_database():
    """Cached database manager instance for fast dashboard rendering."""
    return get_db("data/sellerops.db")


def render_sidebar_branding():
    """Render standardized platform branding in the sidebar."""
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 12px 0 20px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="background-color: #2563EB; width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 16px;">⚡</div>
                    <div>
                        <div style="font-weight: 700; font-size: 1.15rem; color: #111827; line-height: 1.2;">SellerOps</div>
                        <div style="font-size: 0.72rem; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;">Intelligence Platform</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_page_header(title: str, subtitle: str, badge: Optional[str] = None):
    """Render unified enterprise page header."""
    badge_html = f'<span class="badge badge-info" style="margin-left: 10px; vertical-align: middle;">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div style="margin-bottom: 22px;">
            <h1 style="font-size: 1.9rem; font-weight: 700; margin-bottom: 6px; display: flex; align-items: center;">
                {title} {badge_html}
            </h1>
            <p style="color: #64748B; font-size: 0.98rem; margin: 0; line-height: 1.4;">
                {subtitle}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, subtitle: str = "", delta_color: str = "text_secondary"):
    """Render a styled enterprise metric card with responsive sizing, uniform height, and tooltips."""
    badge_style = ""
    if delta_color == "danger":
        badge_style = 'color: #DC2626 !important; font-weight: 600;'
    elif delta_color == "warning":
        badge_style = 'color: #D97706 !important; font-weight: 600;'
    elif delta_color == "success":
        badge_style = 'color: #16A34A !important; font-weight: 600;'

    subtitle_html = f'<div class="metric-subtitle" style="{badge_style}">{subtitle}</div>' if subtitle else ""
    clean_value = str(value).replace('"', '&quot;')

    st.markdown(
        f"""
        <div class="metric-card" title="{clean_value}">
            <div class="metric-header">
                <div class="metric-title">{title}</div>
            </div>
            <div class="metric-value-container">
                <div class="metric-value" title="{clean_value}">{value}</div>
            </div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str = "No Data Found", message: str = "No records matched your selected criteria."):
    """Render a clean empty state card."""
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-desc">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_error_state(title: str = "Query Error", message: str = "An error occurred while loading data."):
    """Render a standardized error state."""
    st.markdown(
        f"""
        <div class="empty-state" style="border-color: #FECACA; background-color: #FEF2F2;">
            <div class="empty-state-title" style="color: #991B1B;">⚠️ {title}</div>
            <div class="empty-state-desc" style="color: #B91C1C;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_plotly_white_layout(fig, title: Optional[str] = None):
    """Enforce crisp white palette and enterprise styling on Plotly figures."""
    layout_args = dict(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#111827", family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto"),
        margin=dict(l=24, r=24, t=40 if title else 20, b=24),
        xaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B", size=11),
            titlefont=dict(color="#475569", size=12),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B", size=11),
            titlefont=dict(color="#475569", size=12),
        ),
        legend=dict(
            font=dict(color="#111827", size=11),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#E2E8F0",
            borderwidth=1,
        ),
    )
    if title:
        layout_args["title"] = dict(
            text=f"<b>{title}</b>",
            font=dict(color="#111827", size=14),
            x=0.01,
            xanchor="left",
        )

    fig.update_layout(**layout_args)
    return fig
