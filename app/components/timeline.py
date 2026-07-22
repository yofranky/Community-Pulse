"""
Timeline component for Community Pulse.

Renders a "Source vs. Sentiment" chart using Altair, styled to match the
dark Ops Console theme. The caller is responsible for date-range
filtering (see app/utils/filters.py) — this component just plots
whatever DataFrame it's given.
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


def render(df: pd.DataFrame, title: str = "Source vs. Sentiment"):
    """Render a Source vs. Sentiment scatter chart for the given (already
    date-filtered) DataFrame."""
    st.subheader(title)

    if df.empty:
        st.info("No signals in the selected date range.")
        return

    plot_df = df.copy()
    classification_color_map = {
        "threat": ORANGE,
        "opportunity": GREEN,
        "neutral": MUTED,
    }
    if "classification" not in plot_df.columns:
        plot_df["classification"] = "neutral"

    chart = (
        alt.Chart(plot_df)
        .mark_circle(size=100, opacity=0.85, stroke=SURFACE, strokeWidth=1)
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
                axis=alt.Axis(titleFontSize=13),
            ),
            color=alt.Color(
                "classification:N",
                title="Classification",
                scale=alt.Scale(
                    domain=list(classification_color_map.keys()),
                    range=list(classification_color_map.values()),
                ),
                legend=alt.Legend(orient="top-right", labelFontSize=12, titleFontSize=13),
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
        .interactive()
    )

    hline = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color=MUTED, strokeDash=[4, 4], strokeWidth=1)
        .encode(y="y:Q")
    )

    combined = (chart + hline).properties(height=380).configure(**DARK_CHART_CONFIG)

    st.altair_chart(combined, use_container_width=True)

    st.caption(
        "● Green = Opportunity  |  ▲ Orange = Threat  |  ■ Gray = Neutral. "
        "Chart reflects the date range selected in the sidebar."
    )
