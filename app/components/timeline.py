"""
Timeline component for Community Pulse.

Renders a sentiment-over-time chart using Altair.
"""

import altair as alt
import pandas as pd
import streamlit as st


def render(df: pd.DataFrame):
    """Render a sentiment-over-time scatter/line chart."""
    st.subheader("Sentiment Over Time")

    if df.empty:
        st.info("No signal data available to plot.")
        return

    # Source filter
    sources = ["All"] + sorted(df["source"].unique().tolist())
    selected_source = st.selectbox("Filter by source", sources, key="timeline_source")

    plot_df = df.copy()
    if selected_source != "All":
        plot_df = plot_df[plot_df["source"] == selected_source]

    if plot_df.empty:
        st.info(f"No signals from source: {selected_source}")
        return

    # Base chart
    chart = (
        alt.Chart(plot_df)
        .mark_circle(size=80, opacity=0.7)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y(
                "sentiment_score:Q",
                title="Sentiment Score",
                scale=alt.Scale(domain=[-1.0, 1.0]),
            ),
            color=alt.Color(
                "source:N",
                title="Source",
                scale=alt.Scale(
                    domain=["reddit", "discord", "github_discussions"],
                    range=["#FF4500", "#5865F2", "#2DBA4E"],
                ),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("sentiment_score:Q", title="Sentiment", format=".2f"),
                alt.Tooltip("topic:N", title="Topic"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("content_preview:N", title="Preview"),
            ],
        )
        .properties(height=400)
        .interactive()
    )

    # Add a horizontal reference line at y=0
    hline = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="gray", strokeDash=[4, 4]).encode(y="y:Q")

    st.altair_chart(chart + hline, use_container_width=True)

    # Show raw trend data from summary
    st.caption("Green = positive sentiment, Red = negative sentiment. Dashed line = neutral.")