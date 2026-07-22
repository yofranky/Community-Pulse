"""
Community Pulse - Stlite Frontend (Welcome page)

A serverless Streamlit dashboard (via Stlite) that visualizes community
sentiment data from the Pure community. Runs entirely in the browser
with no backend server required.

This is the entry point / "Welcome" page: top-line KPIs, one summary
chart, and a short "what to focus on" highlight. Deeper analysis lives
in the pages/ directory (see the sidebar nav):
    - pages/1_Signal_Triage.py — full triage table
    - pages/2_Trends_and_Topics.py — timeline + topic breakdown

Usage:
    streamlit run app/app.py
    # or open index.html in a browser (when bundled with Stlite)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from app.components import dashboard, timeline
from app.utils.data_loader import generate_briefing, get_filtered_signals, get_intel_stats, load_data, signals_to_dataframe
from app.utils.filters import apply_date_range, render_date_range_picker
from app.utils.theme import BORDER, GREEN, MUTED, ORANGE, SURFACE, TEXT, inject_css, render_page_title, render_sidebar_wordmark

st.set_page_config(
    page_title="Community Pulse — Pure Intelligence Console",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Load data (needed before rendering the sidebar's date picker) ─────
try:
    data = load_data()
except FileNotFoundError:
    st.error("data/data.json not found. Run the ETL pipeline first.")
    st.stop()

df = signals_to_dataframe(data)

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_wordmark()
    st.divider()

    start, end = render_date_range_picker(df)

    st.divider()
    st.markdown(
        """
        <p style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; color:#9A9A9A; text-transform:uppercase; letter-spacing:0.8px; margin:0 0 8px 0;">
            Signal Filter
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
        f"""
        <p style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.8px; margin:0 0 8px 0;">
            About
        </p>
        <p style="font-size:12px; color:{MUTED}; line-height:1.6;">
            This console aggregates community signals from Reddit, Discord,
            GitHub Discussions, RSS feeds, and competitor channels.
        </p>
        <p style="font-size:12px; color:{MUTED}; line-height:1.6;">
            <strong style="color:{ORANGE};">Threats</strong> = Competitor praise or Pure criticism<br>
            <strong style="color:{GREEN};">Opportunities</strong> = Migration inquiries or competitor criticism
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    data_meta = data.get("meta", {})
    version = data_meta.get("version", "?")
    last_updated = data_meta.get("last_updated", "?")[:10]
    st.markdown(
        f"""
        <p style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:{MUTED}; margin:0;">
            <span style="color:{GREEN};">●</span> Schema v{version} · Updated {last_updated}
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Built with Stlite + Streamlit")

# ── Main Content ────────────────────────────────────────────────────
render_page_title(
    "Community Pulse",
    "Pure intelligence console — competitor watch, community sentiment, and migration signals",
)

filter_map = {
    "All Signals": "all",
    "Only Competitor News": "competitor",
    "Only Community Signals": "community",
}
filtered_df = get_filtered_signals(df, filter_map[filter_mode])
filtered_df = apply_date_range(filtered_df, start, end)

# ── Today's Briefing ────────────────────────────────────────────────
# The single highest-value thing on this page: what does the community
# manager need to know before anything else loads.
intel_stats = get_intel_stats(filtered_df)

top_signal_row = None
if not filtered_df.empty:
    _top = filtered_df[filtered_df["alert_level"] > 1].sort_values(
        ["alert_level", "date"], ascending=[False, False]
    ).head(1)
    if not _top.empty:
        top_signal_row = _top.iloc[0].to_dict()

briefing_text = generate_briefing(intel_stats, top_signal_row)

st.markdown(
    f"""
    <div style="
        background: linear-gradient(100deg, {SURFACE} 0%, {SURFACE} 70%, #1A0F08 100%);
        border: 1px solid {BORDER};
        border-left: 3px solid {ORANGE};
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 20px;
    ">
        <p style="margin:0; font-size:11px; color:{MUTED}; text-transform:uppercase; letter-spacing:0.8px; font-family:'IBM Plex Mono',monospace;">
            Today's Briefing
        </p>
        <p style="margin:6px 0 0 0; font-size:16px; color:{TEXT}; line-height:1.5;">
            {briefing_text}
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Top 3 KPIs ──────────────────────────────────────────────────────
dashboard.render(intel_stats)

st.divider()

# ── Summary viz ─────────────────────────────────────────────────────
timeline.render(filtered_df, title="Sentiment Overview")

st.divider()

# ── What to focus on ────────────────────────────────────────────────
st.subheader("What to Focus On")

if filtered_df.empty:
    st.info("No signals in the selected range.")
else:
    top_signals = filtered_df[filtered_df["alert_level"] > 1].sort_values(
        ["alert_level", "date"], ascending=[False, False]
    ).head(3)

    if top_signals.empty:
        st.markdown(
            f'<p style="color:{MUTED};">No active threats or opportunities in this range — quiet week.</p>',
            unsafe_allow_html=True,
        )
    else:
        for _, row in top_signals.iterrows():
            color = ORANGE if row["alert_level"] == 3 else GREEN
            label = "▲ Threat" if row["alert_level"] == 3 else "● Opportunity"
            explanation = row.get("explanation") or row.get("content_preview", "")[:140]
            st.markdown(
                f"""
                <div style="
                    background:{SURFACE}; border-left:3px solid {color};
                    border-radius:4px; padding:12px 16px; margin-bottom:10px;
                ">
                    <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; color:{color}; text-transform:uppercase; letter-spacing:0.6px;">
                        {label} · {row.get('source', '')}
                    </span>
                    <p style="margin:6px 0 0 0; font-size:13px; color:{TEXT};">
                        {explanation}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.caption("Full triage view with all signals → see **Signal Triage** in the sidebar nav.")
