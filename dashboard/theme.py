"""Enterprise White Theme and Reusable UI Components for SellerOps Dashboard."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.database.connection import get_db

# Canonical Color Palette
COLORS = {
    "bg": "#FFFFFF",
    "surface": "#FFFFFF",
    "text_primary": "#111827",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "primary": "#2563EB",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "card_bg": "#FFFFFF",
    "gray_light": "#F8FAFC",
}

CUSTOM_CSS = """
<style>
    /* Global white enterprise theme */
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #FFFFFF !important;
        color: #111827 !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    
    html, body, p, span, div, label {
        color: #111827 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #111827 !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }

    /* Metric Cards */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 500;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #111827 !important;
        line-height: 1.2;
    }
    .metric-subtitle {
        font-size: 0.8rem;
        color: #64748B !important;
        margin-top: 6px;
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 3px 8px;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 4px;
    }
    .badge-success { background-color: #DCFCE7; color: #166534 !important; }
    .badge-warning { background-color: #FEF3C7; color: #92400E !important; }
    .badge-danger { background-color: #FEE2E2; color: #991B1B !important; }
    .badge-info { background-color: #DBEAFE; color: #1E40AF !important; }

    /* Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 6px !important;
    }

    /* Remove Streamlit default footer */
    footer { visibility: hidden; }
</style>
"""


def apply_theme():
    """Inject pure white enterprise CSS into the active Streamlit page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_resource
def get_database():
    """Cached database manager instance."""
    return get_db("data/sellerops.db")


def render_metric_card(title: str, value: str, subtitle: str = "", delta_color: str = "text_secondary"):
    """Render a styled enterprise metric card."""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_plotly_white_layout(fig):
    """Enforce crisp white palette on Plotly figures."""
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#111827", family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto"),
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B"),
        ),
        legend=dict(
            font=dict(color="#111827"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#E2E8F0",
        ),
    )
    return fig
