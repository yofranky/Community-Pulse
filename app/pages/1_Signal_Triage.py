"""
Community Pulse — Signal Triage page.

The focused, actionable view: every current threat and opportunity,
sorted by severity, with the "why" behind each classification. This is
the page a community manager should be living in day-to-day.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from app.components import signal_table
from app.utils.data_loader import get_filtered_signals, load_data, signals_to_dataframe
from app.utils.filters import apply_date_range, render_date_range_picker
from app.utils.theme import inject_css, render_page_title, render_sidebar_wordmark

st.set_page_config(
    page_title="Signal Triage — Community Pulse",
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
        key="triage_sidebar_filter",
    )

render_page_title("Signal Triage", "Every active threat and opportunity, sorted by severity")

filter_map = {"All Signals": "all", "Only Competitor News": "competitor", "Only Community Signals": "community"}
filtered_df = get_filtered_signals(df, filter_map[filter_mode])
filtered_df = apply_date_range(filtered_df, start, end)

signal_table.render(filtered_df)

st.divider()
st.subheader("All Signals")
with st.expander("View all signals (including neutral)", expanded=False):
    if not filtered_df.empty:
        display_df = filtered_df[
            [
                "date", "source", "topic", "sentiment_score", "confidence",
                "author", "likes", "replies", "alert_level", "classification", "explanation",
            ]
        ].sort_values("date", ascending=False)
        display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d %H:%M")
        display_df["sentiment_score"] = display_df["sentiment_score"].round(2)
        display_df["confidence"] = display_df["confidence"].round(2)
        st.dataframe(
            display_df.rename(columns={
                "date": "Date", "source": "Source", "topic": "Topic",
                "sentiment_score": "Sentiment", "confidence": "Confidence",
                "author": "Author", "likes": "Likes", "replies": "Replies",
                "alert_level": "Alert Level", "classification": "Classification",
                "explanation": "Why?",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No signals in the selected range.")
