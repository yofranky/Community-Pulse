"""
Shared date-range filtering for Community Pulse.

Streamlit multipage apps don't share widget state across pages
automatically — each page file re-executes independently. We persist the
selected date range in st.session_state so picking a range on one page
keeps it applied when you navigate to another.
"""

from datetime import timedelta

import pandas as pd
import streamlit as st

from app.utils.theme import render_telemetry_sweep

SESSION_KEY_START = "pulse_date_start"
SESSION_KEY_END = "pulse_date_end"


def render_date_range_picker(df: pd.DataFrame, location=st.sidebar) -> tuple:
    """
    Render a date-range picker (defaults to the full range in the data)
    and persist the selection in session_state so it applies across pages.

    Returns:
        (start_date, end_date) as pandas Timestamps, or (None, None) if
        the data is empty.
    """
    if df.empty or "date" not in df.columns:
        return None, None

    data_min = df["date"].min().date()
    data_max = df["date"].max().date()

    default_start = st.session_state.get(SESSION_KEY_START, data_min)
    default_end = st.session_state.get(SESSION_KEY_END, data_max)

    # Clamp defaults to the actual data range (handles switching data.json
    # files between sessions where a previously-picked range no longer fits)
    default_start = max(default_start, data_min)
    default_end = min(default_end, data_max)
    if default_start > default_end:
        default_start, default_end = data_min, data_max

    location.markdown(
        """
        <p style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; color:#9A9A9A; text-transform:uppercase; letter-spacing:0.8px; margin:0 0 8px 0;">
            Date Range
        </p>
        """,
        unsafe_allow_html=True,
    )

    selection = location.date_input(
        "Date range",
        value=(default_start, default_end),
        min_value=data_min,
        max_value=data_max,
        label_visibility="collapsed",
        key="pulse_date_range_widget",
    )

    # date_input returns a single date while the user has only picked one
    # side of the range — guard against that mid-selection state.
    if isinstance(selection, tuple) and len(selection) == 2:
        start_date, end_date = selection
    else:
        start_date, end_date = default_start, default_end

    st.session_state[SESSION_KEY_START] = start_date
    st.session_state[SESSION_KEY_END] = end_date

    render_telemetry_sweep()

    quick_col1, quick_col2, quick_col3 = location.columns(3)
    if quick_col1.button("7d", use_container_width=True):
        start_date, end_date = data_max - timedelta(days=7), data_max
        st.session_state[SESSION_KEY_START] = start_date
        st.session_state[SESSION_KEY_END] = end_date
        st.rerun()
    if quick_col2.button("30d", use_container_width=True):
        start_date, end_date = data_max - timedelta(days=30), data_max
        st.session_state[SESSION_KEY_START] = start_date
        st.session_state[SESSION_KEY_END] = end_date
        st.rerun()
    if quick_col3.button("All", use_container_width=True):
        start_date, end_date = data_min, data_max
        st.session_state[SESSION_KEY_START] = start_date
        st.session_state[SESSION_KEY_END] = end_date
        st.rerun()

    # `st.date_input` returns plain (timezone-naive) datetime.date objects,
    # but signals_to_dataframe() parses `date` as UTC-aware (the source
    # timestamps end in "Z"). Comparing a tz-naive Timestamp against a
    # tz-aware Series raises TypeError in pandas — localize to UTC here so
    # apply_date_range() always compares like-for-like.
    return (
        pd.Timestamp(start_date, tz="UTC"),
        pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1),
    )


def apply_date_range(df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Filter a signals DataFrame to the given [start, end) date range."""
    if df.empty or start is None or end is None or "date" not in df.columns:
        return df

    # Defensive tz alignment: match start/end's tz-awareness to whatever
    # df["date"] actually is, rather than assuming UTC. Prevents the
    # "Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp"
    # error if the data's tz-awareness ever changes upstream.
    df_tz = getattr(df["date"].dtype, "tz", None)
    if df_tz is not None:
        if start.tzinfo is None:
            start = start.tz_localize(df_tz)
        else:
            start = start.tz_convert(df_tz)
        if end.tzinfo is None:
            end = end.tz_localize(df_tz)
        else:
            end = end.tz_convert(df_tz)
    else:
        if start.tzinfo is not None:
            start = start.tz_localize(None)
        if end.tzinfo is not None:
            end = end.tz_localize(None)

    return df[(df["date"] >= start) & (df["date"] < end)]
