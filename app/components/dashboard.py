"""
Dashboard component for Community Pulse.

Renders intelligence-focused KPI "readout tiles":
- Active Threats (alert_level == 3)
- Migration Opportunities (classification == "opportunity")
- New Technical Mentions (engineering/blog/cloud_native in last 7 days)
"""

import streamlit as st

from app.utils.theme import BORDER, GREEN, MUTED, ORANGE, SURFACE, TEXT


def _tile(label: str, value, caption: str, color: str, icon: str) -> str:
    return f"""
        <div style="
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-left: 3px solid {color};
            border-radius: 6px;
            padding: 18px 18px 16px 16px;
        ">
            <p style="margin:0; font-size:12px; color:{MUTED}; font-weight:600; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Sans',sans-serif;">
                {icon} {label}
            </p>
            <p style="margin:6px 0 0 0; font-size:38px; font-weight:700; color:{color}; font-family:'IBM Plex Mono',monospace;">
                {value}
            </p>
            <p style="margin:4px 0 0 0; font-size:12px; color:{MUTED};">
                {caption}
            </p>
        </div>
        """


def render(intel_stats: dict):
    """Render intelligence KPI readout tiles.

    Args:
        intel_stats: dict from get_intel_stats() with keys:
            active_threats, migration_opportunities, new_technical_mentions,
            total_signals, overall_sentiment
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            _tile(
                "Active Threats",
                intel_stats["active_threats"],
                "Competitor praise or Pure criticism",
                ORANGE,
                "▲",
            ),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            _tile(
                "Migration Opportunities",
                intel_stats["migration_opportunities"],
                "User inquiries and competitor criticism",
                GREEN,
                "●",
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            _tile(
                "New Technical Mentions",
                intel_stats["new_technical_mentions"],
                "Engineering & cloud-native signals (7 days)",
                TEXT,
                "■",
            ),
            unsafe_allow_html=True,
        )
