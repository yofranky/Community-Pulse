"""
Community Pulse — Trends & Topics page.

Deeper analytical view: sentiment over sources, and what topics are
driving the conversation. Good for spotting patterns before they become
a Level 3 threat, not just reacting to ones that already are.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from app.components import timeline, topic_cloud
from app.utils.data_loader import get_filtered_signals, load_data, signals_to_dataframe
from app.utils.filters import apply_date_range, render_date_range_picker
from app.utils.theme import inject_css, render_page_title, render_sidebar_wordmark

st.set_page_config(
    page_title="Trends & Topics — Community Pulse",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

try:
    data = load_data()
except FileNotFoundError:
    st.error("data/data.json not found. Run the ETL pipeline first.")
    st.stop()

df = signals_to_dataframe(data)

with st.sidebar:
    render_sidebar_wordmark()
    st.divider()
    start, end = render_date_range_picker(df)
    st.divider()
    filter_mode = st.radio(
        "Filter mode",
        options=["All Signals", "Only Competitor News", "Only Community Signals"],
        index=0,
        key="trends_sidebar_filter",
    )

render_page_title("Trends & Topics", "Sentiment patterns and what's driving the conversation")

filter_map = {"All Signals": "all", "Only Competitor News": "competitor", "Only Community Signals": "community"}
filtered_df = get_filtered_signals(df, filter_map[filter_mode])
filtered_df = apply_date_range(filtered_df, start, end)

timeline.render(filtered_df, title="Source vs. Sentiment")

st.divider()

topic_cloud.render(filtered_df)
