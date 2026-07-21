"""
Community Pulse - Stlite Frontend

A serverless Streamlit dashboard (via Stlite) that visualizes community
sentiment data from the Pure community. Runs entirely in the browser
with no backend server required.

Features:
- 3-column intelligence dashboard (KPI cards, chart, triage table)
- Sidebar filter: All / Competitor News / Community Signals
- Professional enterprise styling (deep navy, clean white, slate gray)
- Color-coded threat/opportunity rows in the triage table

Usage:
    stlite run app/app.py
    # or open index.html in a browser (when bundled with Stlite)
"""

import sys
from pathlib import Path

# Add parent directory to path so 'app' package can be imported
# even though app/app.py exists as a module in the same namespace
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from app.components import dashboard, signal_table, timeline, topic_cloud
from app.utils.data_loader import (
    get_filtered_signals,
    get_intel_stats,
    get_summary_stats,
    load_data,
    signals_to_dataframe,
)

# ── Page Configuration ──────────────────────────────────────────────
st.set_page_config(
    page_title="Community Pulse — Enterprise Storage Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Professional Enterprise CSS ─────────────────────────────────────
st.markdown(
    """
    <style>
        /* Deep navy headers */
        h1, h2, h3 {
            color: #1B2A4A !important;
            font-weight: 600 !important;
        }
        h1 {
            font-size: 28px !important;
            letter-spacing: -0.5px;
        }
        h2 {
            font-size: 20px !important;
            letter-spacing: -0.3px;
        }
        /* Clean white card backgrounds */
        div[data-testid="metric-container"] {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background-color: #F9FAFB;
            border-right: 1px solid #E5E7EB;
        }
        section[data-testid="stSidebar"] .sidebar-content {
            padding: 20px 16px;
        }
        /* Divider styling */
        hr {
            border-color: #E5E7EB;
            margin: 20px 0;
        }
        /* Streamlit default overrides for cleaner look */
        .stApp {
            background: #F9FAFB;
        }
        .stButton button {
            border-radius: 6px;
        }
        /* Dataframe styling */
        .stDataFrame {
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        }
        /* Caption styling */
        .stCaption {
            color: #9CA3AF;
            font-size: 12px;
        }
        /* Info box styling */
        .stInfo {
            background: #F0F2F5;
            border: 1px solid #E5E7EB;
            color: #374151;
        }
        /* Radio button styling */
        div[role="radiogroup"] label {
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
        }
        div[role="radiogroup"] label:hover {
            background: #F3F4F6;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
            <span style="font-size:36px;">📊</span>
            <div>
                <p style="margin:0; font-size:20px; font-weight:700; color:#1B2A4A;">
                    Community Pulse
                </p>
                <p style="margin:0; font-size:12px; color:#6B7280;">
                    Pure Intelligence Dashboard
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        """
        <p style="font-size:13px; font-weight:600; color:#374151; margin:0 0 8px 0;">
            🔍 Signal Filter
        </p>
        """,
        unsafe_allow_html=True,
    )

    filter_mode = st.radio(
        "Filter mode",
        options=["All Signals", "Only Competitor News", "Only Community Signals"],
        index=0,
        label_visibility="collapsed",
        key="sidebar_filter",
    )

    st.divider()

    st.markdown(
        """
        <p style="font-size:13px; font-weight:600; color:#374151; margin:0 0 8px 0;">
            📖 About
        </p>
        <p style="font-size:12px; color:#6B7280; line-height:1.5;">
            This dashboard aggregates community signals from Reddit, Discord,
            GitHub Discussions, RSS feeds, and competitor channels.
        </p>
        <p style="font-size:12px; color:#6B7280; line-height:1.5;">
            <strong>Threats</strong> = Competitor praise or Pure criticism<br>
            <strong>Opportunities</strong> = Migration inquiries or competitor criticism
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Version info
    try:
        data_meta = load_data().get("meta", {})
        version = data_meta.get("version", "?")
        last_updated = data_meta.get("last_updated", "?")[:10]
    except Exception:
        version = "?"
        last_updated = "?"

    st.caption(f"Schema v{version} · Updated {last_updated}")
    st.caption("Built with Stlite + Streamlit")

# ── Main Content ────────────────────────────────────────────────────
st.title("📊 Community Pulse")
st.markdown(
    '<p style="color:#6B7280; font-size:16px; margin-top:-8px;">'
    "Enterprise storage intelligence — competitor watch, community sentiment, and migration signals"
    "</p>",
    unsafe_allow_html=True,
)

# Load data
try:
    data = load_data()
except FileNotFoundError:
    st.error("data/data.json not found. Run the ETL pipeline first.")
    st.stop()

df = signals_to_dataframe(data)

# Apply sidebar filter
filter_map = {
    "All Signals": "all",
    "Only Competitor News": "competitor",
    "Only Community Signals": "community",
}
filtered_df = get_filtered_signals(df, filter_map[filter_mode])

# Compute intelligence stats from the filtered dataframe
intel_stats = get_intel_stats(filtered_df)

# ── Row 1: KPI Cards ───────────────────────────────────────────────
dashboard.render(intel_stats)

st.divider()

# ── Row 2: Two-column layout (Chart + Triage Table) ────────────────
col_left, col_right = st.columns([1, 1.4])

with col_left:
    timeline.render(filtered_df)

with col_right:
    signal_table.render(filtered_df)

st.divider()

# ── Row 3: Topic Cloud (full width) ────────────────────────────────
topic_cloud.render(filtered_df)

st.divider()

# ── Row 4: Raw Signals Table (collapsible) ─────────────────────────
st.subheader("All Signals")
with st.expander("View all signals", expanded=False):
    if not filtered_df.empty:
        display_df = filtered_df[
            [
                "date",
                "source",
                "topic",
                "sentiment_score",
                "confidence",
                "author",
                "likes",
                "replies",
                "alert_level",
                "classification",
                "explanation",
            ]
        ].sort_values("date", ascending=False)
        display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d %H:%M")
        display_df["sentiment_score"] = display_df["sentiment_score"].round(2)
        display_df["confidence"] = display_df["confidence"].round(2)

        st.dataframe(
            display_df.rename(
                columns={
                    "date": "Date",
                    "source": "Source",
                    "topic": "Topic",
                    "sentiment_score": "Sentiment",
                    "confidence": "Confidence",
                    "author": "Author",
                    "likes": "Likes",
                    "replies": "Replies",
                    "alert_level": "Alert Level",
                    "classification": "Classification",
                    "explanation": "Why?",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No signals to display.")