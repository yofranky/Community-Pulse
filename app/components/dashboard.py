"""
Dashboard component for Community Pulse.

Renders KPI cards showing high-level community health metrics.
"""

import streamlit as st


def render(stats: dict):
    """Render KPI summary cards at the top of the dashboard."""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Total Signals",
            value=stats["total_signals"],
            help="Total community signals collected across all sources",
        )

    with col2:
        st.metric(
            label="Sources",
            value=stats["sources_count"],
            help="Number of community channels being monitored",
        )

    with col3:
        sentiment = stats["overall_sentiment"]
        delta = None
        if sentiment >= 0.5:
            delta = "positive"
        elif sentiment <= -0.3:
            delta = "negative"
        st.metric(
            label="Overall Sentiment",
            value=f"{sentiment:+.2f}",
            delta=delta,
            help="Average sentiment score across all signals (-1.0 to 1.0)",
        )

    with col4:
        st.metric(
            label="Top Topic",
            value=stats["top_topic"].replace("_", " ").title(),
            help="Most discussed topic in the community",
        )

    with col5:
        st.metric(
            label="Trend Span",
            value=f"{stats['trend_days']} days",
            help="Number of days in the sentiment trend window",
        )