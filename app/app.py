"""
Community Pulse - Stlite Frontend

A serverless Streamlit dashboard (via Stlite) that visualizes community
sentiment data from the Everpure community. Runs entirely in the browser
with no backend server required.

Usage:
    stlite run app/app.py
    # or open index.html in a browser (when bundled with Stlite)
"""

import streamlit as st

from app.components import dashboard, timeline, topic_cloud
from app.utils.data_loader import get_summary_stats, load_data, signals_to_dataframe

# ── Page Configuration ──────────────────────────────────────────────
st.set_page_config(
    page_title="Community Pulse - Everpure",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/water--v1.png", width=64)
    st.title("Community Pulse")
    st.caption("Everpure Community Sentiment Dashboard")

    st.divider()

    st.markdown("### About")
    st.markdown(
        """
        This dashboard aggregates community signals from:
        - **Reddit** (r/everpure, r/waterfiltration)
        - **Discord** (Everpure Community Server)
        - **GitHub Discussions** (everpure/community)

        Data is collected via automated ETL pipelines and updated daily.
        """
    )

    st.divider()

    st.markdown("### Legend")
    st.markdown(
        """
        - **Sentiment Score**: -1.0 (negative) to 1.0 (positive)
        - **Confidence**: 0.0 (low) to 1.0 (high)
        - **Sources are color-coded** in charts
        """
    )

    st.divider()
    st.caption("Built with Stlite + Streamlit")
    st.caption(f"v{load_data().get('meta', {}).get('version', '?')}")

# ── Main Content ────────────────────────────────────────────────────
st.title("📊 Community Pulse")
st.markdown("Real-time community sentiment monitoring for Everpure")

# Load data
try:
    data = load_data()
except FileNotFoundError:
    st.error("data/data.json not found. Run the ETL pipeline first.")
    st.stop()

df = signals_to_dataframe(data)
stats = get_summary_stats(data)

# ── Dashboard KPIs ──────────────────────────────────────────────────
dashboard.render(stats)

st.divider()

# ── Two-column layout for charts ────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    timeline.render(df)

with col_right:
    topic_cloud.render(df)

st.divider()

# ── Raw Signals Table ───────────────────────────────────────────────
st.subheader("Recent Signals")
with st.expander("View all signals", expanded=False):
    if not df.empty:
        display_df = df[
            ["date", "source", "topic", "sentiment_score", "confidence", "author", "likes", "replies"]
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
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No signals to display.")