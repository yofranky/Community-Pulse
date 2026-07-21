"""
Dashboard component for Community Pulse.

Renders intelligence-focused KPI cards at the top of the dashboard:
- Active Threats (alert_level == 3)
- Migration Opportunities (classification == "opportunity")
- New Technical Mentions (engineering/blog/cloud_native in last 7 days)
"""

import streamlit as st


def render(intel_stats: dict):
    """Render intelligence KPI summary cards.

    Args:
        intel_stats: dict from get_intel_stats() with keys:
            active_threats, migration_opportunities, new_technical_mentions,
            total_signals, overall_sentiment
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div style="
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-left: 4px solid #DC2626;
                border-radius: 8px;
                padding: 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            ">
                <p style="margin:0; font-size:14px; color:#6B7280; font-weight:500;">
                    🚨 Active Threats
                </p>
                <p style="margin:4px 0 0 0; font-size:32px; font-weight:700; color:#DC2626;">
                    {intel_stats['active_threats']}
                </p>
                <p style="margin:2px 0 0 0; font-size:12px; color:#9CA3AF;">
                    Competitor praise or Pure criticism
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div style="
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-left: 4px solid #16A34A;
                border-radius: 8px;
                padding: 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            ">
                <p style="margin:0; font-size:14px; color:#6B7280; font-weight:500;">
                    💡 Migration Opportunities
                </p>
                <p style="margin:4px 0 0 0; font-size:32px; font-weight:700; color:#16A34A;">
                    {intel_stats['migration_opportunities']}
                </p>
                <p style="margin:2px 0 0 0; font-size:12px; color:#9CA3AF;">
                    User inquiries and competitor criticism
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div style="
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-left: 4px solid #1B2A4A;
                border-radius: 8px;
                padding: 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            ">
                <p style="margin:0; font-size:14px; color:#6B7280; font-weight:500;">
                    🔬 New Technical Mentions
                </p>
                <p style="margin:4px 0 0 0; font-size:32px; font-weight:700; color:#1B2A4A;">
                    {intel_stats['new_technical_mentions']}
                </p>
                <p style="margin:2px 0 0 0; font-size:12px; color:#9CA3AF;">
                    Engineering & cloud-native signals (7 days)
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )