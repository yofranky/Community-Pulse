"""
Topic breakdown component for Community Pulse.

Renders a bar chart of top topics with average sentiment coloring.
"""

import altair as alt
import pandas as pd
import streamlit as st

from app.utils.theme import BORDER, GREEN, MUTED, ORANGE, SURFACE, TEXT

DARK_CHART_CONFIG = {
    "background": SURFACE,
    "axis": {
        "domainColor": BORDER,
        "gridColor": BORDER,
        "tickColor": BORDER,
        "labelColor": MUTED,
        "titleColor": TEXT,
        "labelFont": "IBM Plex Sans",
        "titleFont": "IBM Plex Mono",
    },
    "legend": {
        "labelColor": TEXT,
        "titleColor": MUTED,
        "labelFont": "IBM Plex Sans",
        "titleFont": "IBM Plex Mono",
    },
    "view": {"stroke": BORDER},
}


def render(df: pd.DataFrame):
    """Render a topic breakdown chart with sentiment heatmap."""
    st.subheader("Topic Breakdown")

    if df.empty:
        st.info("No signal data available.")
        return

    topic_stats = (
        df.groupby("topic")
        .agg(
            count=("sentiment_score", "count"),
            avg_sentiment=("sentiment_score", "mean"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    topic_stats["avg_sentiment"] = topic_stats["avg_sentiment"].round(4)
    topic_stats["topic_label"] = topic_stats["topic"].str.replace("_", " ").str.title()

    bar_chart = (
        alt.Chart(topic_stats)
        .mark_bar()
        .encode(
            x=alt.X("count:Q", title="Signal Count"),
            y=alt.Y("topic_label:N", title=None, sort="-x"),
            color=alt.Color(
                "avg_sentiment:Q",
                title="Avg Sentiment",
                scale=alt.Scale(
                    domain=[-1.0, 0, 1.0],
                    range=[ORANGE, MUTED, GREEN],
                ),
                legend=alt.Legend(format=".2f"),
            ),
            tooltip=[
                alt.Tooltip("topic_label:N", title="Topic"),
                alt.Tooltip("count:Q", title="Signals"),
                alt.Tooltip("avg_sentiment:Q", title="Avg Sentiment", format=".2f"),
            ],
        )
        .properties(height=300)
        .configure(**DARK_CHART_CONFIG)
        .interactive()
    )

    st.altair_chart(bar_chart, use_container_width=True)

    with st.expander("View raw topic data"):
        st.dataframe(
            topic_stats[["topic_label", "count", "avg_sentiment"]].rename(
                columns={
                    "topic_label": "Topic",
                    "count": "Signal Count",
                    "avg_sentiment": "Avg Sentiment",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.caption("Bar color = average sentiment (orange = negative, gray = neutral, green = positive).")