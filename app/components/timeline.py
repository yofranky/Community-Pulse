"""
Timeline component for Community Pulse.

Renders a "Source vs. Sentiment" chart using Altair, filtered to the last 30 days.
Uses the enterprise color palette:
- Deep navy (#1B2A4A) for neutral signals
- Red (#DC2626) for threats
- Green (#16A34A) for opportunities
"""

import altair as alt
import pandas as pd
import streamlit as st


def render(df: pd.DataFrame):
    """Render a Source vs. Sentiment scatter chart for the last 30 days."""
    st.subheader("Source vs. Sentiment (Last 30 Days)")

    if df.empty:
        st.info("No signal data available to plot.")
        return

    # Filter to last 30 days
    now = pd.Timestamp.now(tz="UTC")
    thirty_days_ago = now - pd.Timedelta(days=30)
    plot_df = df[df["date"] >= thirty_days_ago].copy()

    if plot_df.empty:
        st.info("No signals in the last 30 days.")
        return

    # Assign color based on classification
    classification_color_map = {
        "threat": "#DC2626",
        "opportunity": "#16A34A",
        "neutral": "#6B7280",
    }
    # If no classification column, default to neutral
    if "classification" not in plot_df.columns:
        plot_df["classification"] = "neutral"

    # Build the chart
    chart = (
        alt.Chart(plot_df)
        .mark_circle(size=100, opacity=0.8, stroke="white", strokeWidth=1)
        .encode(
            x=alt.X(
                "source:N",
                title="Source",
                sort="-y",
                axis=alt.Axis(labelAngle=-25, labelFontSize=11),
            ),
            y=alt.Y(
                "sentiment_score:Q",
                title="Sentiment Score",
                scale=alt.Scale(domain=[-1.0, 1.0]),
                axis=alt.Axis(gridColor="#E5E7EB", titleFontSize=13),
            ),
            color=alt.Color(
                "classification:N",
                title="Classification",
                scale=alt.Scale(
                    domain=list(classification_color_map.keys()),
                    range=list(classification_color_map.values()),
                ),
                legend=alt.Legend(
                    orient="top-right",
                    labelFontSize=12,
                    titleFontSize=13,
                ),
            ),
            tooltip=[
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("topic:N", title="Topic"),
                alt.Tooltip("sentiment_score:Q", title="Sentiment", format=".2f"),
                alt.Tooltip("classification:N", title="Classification"),
                alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("content_preview:N", title="Preview"),
            ],
        )
        .properties(height=400)
        .interactive()
    )

    # Horizontal reference line at y=0
    hline = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#9CA3AF", strokeDash=[4, 4], strokeWidth=1)
        .encode(y="y:Q")
    )

    # Add a subtle jitter on x-axis to avoid overlapping points from same source
    jittered = chart.encode(
        x=alt.X(
            "source:N",
            title="Source",
            sort="-y",
            axis=alt.Axis(labelAngle=-25, labelFontSize=11),
        ),
    )

    st.altair_chart(jittered + hline, use_container_width=True)

    # Legend caption
    st.caption(
        "🟢 Green = Opportunity  |  🔴 Red = Threat  |  ⚫ Gray = Neutral. "
        "Dashed line = neutral sentiment (0.0)."
    )