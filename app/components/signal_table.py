"""
Signal Triage Table component for Community Pulse.

Renders a scrollable table of Threats and Opportunities with:
- A left-border status stripe per row (Threat = orange, Opportunity = green)
- Outline-chip badges (color + text, never color-only — accessibility)
- Clickable source URLs
- Explanation tooltip for audit trail
"""

import streamlit as st

from app.utils.theme import BORDER, GREEN, MUTED, ORANGE, SURFACE, SURFACE_2, TEXT


def _chip(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}1F; color:{color}; border:1px solid {color}4D; '
        f'padding:2px 9px; border-radius:3px; font-size:11px; font-weight:600; '
        f'font-family:\'IBM Plex Mono\',monospace; white-space:nowrap;">{text}</span>'
    )


def render(df):
    """Render the signal triage table filtered to threats and opportunities only."""
    st.subheader("Signal Triage — Threats & Opportunities")

    if df.empty:
        st.info("No signals to display.")
        return

    triage_df = df[df["alert_level"] > 1].copy()

    if triage_df.empty:
        st.info("No active threats or opportunities to triage.")
        return

    triage_df = triage_df.sort_values(
        ["alert_level", "date"], ascending=[False, False]
    )

    rows_html = ""
    for _, row in triage_df.iterrows():
        alert_level = int(row.get("alert_level", 1))
        source = row.get("source", "unknown")
        topic = row.get("topic", "general")
        date_str = row.get("date", "")
        if hasattr(date_str, "strftime"):
            date_str = date_str.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = str(date_str)[:16]

        content_preview = str(row.get("content_preview", ""))[:120]
        source_url = row.get("source_url", "")
        entities = row.get("entities_detected", "")
        explanation = row.get("explanation", "")

        if alert_level == 3:
            stripe_color = ORANGE
            level_badge = _chip("Level 3", ORANGE)
            class_badge = _chip("▲ Threat", ORANGE)
        elif alert_level == 2:
            stripe_color = GREEN
            level_badge = _chip("Level 2", GREEN)
            class_badge = _chip("● Opportunity", GREEN)
        else:
            stripe_color = BORDER
            level_badge = ""
            class_badge = ""

        if source_url:
            link_html = (
                f'<a href="{source_url}" target="_blank" '
                f'style="color:{ORANGE}; text-decoration:none; font-size:13px;">'
                f'View →</a>'
            )
        else:
            link_html = f'<span style="color:{MUTED}; font-size:13px;">—</span>'

        if entities:
            entities_html = (
                f'<span style="background:{SURFACE_2}; color:{TEXT}; '
                f'padding:2px 6px; border-radius:4px; '
                f'font-size:11px; font-weight:500; font-family:\'IBM Plex Mono\',monospace;">{entities}</span>'
            )
        else:
            entities_html = ""

        if explanation:
            explanation_html = (
                f'<span title="{explanation}" style="'
                f'border-bottom:1px dotted {MUTED}; cursor:help; color:{MUTED};">'
                f'{explanation[:60]}{"..." if len(explanation) > 60 else ""}</span>'
            )
        else:
            explanation_html = "—"

        rows_html += f"""
        <tr style="background:{SURFACE}; border-bottom:1px solid {BORDER}; border-left:3px solid {stripe_color};">
            <td style="padding:10px 12px; font-size:13px; color:{MUTED}; white-space:nowrap; font-family:'IBM Plex Mono',monospace;">
                {date_str}
            </td>
            <td style="padding:10px 12px; font-size:13px; color:{TEXT}; font-weight:500;">
                {source}
            </td>
            <td style="padding:10px 12px; font-size:13px; color:{TEXT};">
                {topic.replace('_', ' ').title()}
            </td>
            <td style="padding:10px 12px; text-align:center;">
                {level_badge}
            </td>
            <td style="padding:10px 12px; text-align:center;">
                {class_badge}
            </td>
            <td style="padding:10px 12px; font-size:12px; color:{MUTED}; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                {entities_html}
            </td>
            <td style="padding:10px 12px; font-size:12px; color:{MUTED}; max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                {content_preview}
            </td>
            <td style="padding:10px 12px; font-size:11px; color:{MUTED}; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-style:italic;">
                {explanation_html}
            </td>
            <td style="padding:10px 12px; text-align:center;">
                {link_html}
            </td>
        </tr>
        """

    table_html = f"""
    <div style="
        max-height:500px;
        overflow-y:auto;
        border:1px solid {BORDER};
        border-radius:6px;
        background:{SURFACE};
    ">
        <table style="width:100%; border-collapse:collapse; font-family:'IBM Plex Sans',sans-serif;">
            <thead style="position:sticky; top:0; z-index:1;">
                <tr style="background:{SURFACE_2}; border-bottom:1px solid {BORDER};">
                    <th style="padding:12px; text-align:left; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Date</th>
                    <th style="padding:12px; text-align:left; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Source</th>
                    <th style="padding:12px; text-align:left; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Topic</th>
                    <th style="padding:12px; text-align:center; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Level</th>
                    <th style="padding:12px; text-align:center; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Class</th>
                    <th style="padding:12px; text-align:left; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Entities</th>
                    <th style="padding:12px; text-align:left; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Preview</th>
                    <th style="padding:12px; text-align:left; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Why?</th>
                    <th style="padding:12px; text-align:center; font-size:11px; font-weight:600; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px; font-family:'IBM Plex Mono',monospace;">Link</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """

    st.markdown(table_html, unsafe_allow_html=True)

    threat_count = len(triage_df[triage_df["alert_level"] == 3])
    opp_count = len(triage_df[triage_df["alert_level"] == 2])
    st.caption(
        f"Showing {len(triage_df)} signals requiring attention "
        f"({threat_count} threats, {opp_count} opportunities). "
        "Orange stripe = Threat, Green stripe = Opportunity."
    )
