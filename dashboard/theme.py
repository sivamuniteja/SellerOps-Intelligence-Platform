"""Enterprise White Theme and Reusable UI Components for SellerOps Dashboard."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from typing import Optional, Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.database.connection import get_db

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
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover {
        border-color: #CBD5E1;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07);
    }
    .metric-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #111827 !important;
        line-height: 1.15;
    }
    .metric-subtitle {
        font-size: 0.82rem;
        color: #64748B !important;
        margin-top: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
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
    """Render a styled enterprise metric card."""
    badge_type = "neutral"
    if delta_color == "danger":
        badge_type = "danger"
    elif delta_color == "warning":
        badge_type = "warning"
    elif delta_color == "success":
        badge_type = "success"

    subtitle_html = f'<div class="metric-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
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
