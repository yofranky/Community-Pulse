"""
Topic breakdown component for Community Pulse.

Renders a bar chart of top topics with average sentiment coloring.
"""

import altair as alt
import pandas as pd
import streamlit as st


def render(df: pd.DataFrame):
    """Render a topic breakdown chart with sentiment heatmap."""
    st.subheader("Topic Breakdown")

    if df.empty:
        st.info("No signal data available.")
        return

    # Aggregate by topic
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

    # Bar chart: count per topic, colored by avg sentiment
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
                    range=["#e74c3c", "#f39c12", "#2ecc71"],
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
        .interactive()
    )

    st.altair_chart(bar_chart, use_container_width=True)

    # Data table below
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

    st.caption("Bar color = average sentiment (red = negative, yellow = neutral, green = positive).")