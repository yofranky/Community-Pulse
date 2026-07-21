"""
Signal Triage Table component for Community Pulse.

Renders a scrollable table of Threats and Opportunities with:
- Color-coded rows (red tint for Level 3 Threats, green tint for Level 2 Opportunities)
- Clickable source URLs
- Alert level badges
- Classification tags
- Explanation tooltip for audit trail
"""

import streamlit as st


def render(df):
    """Render the signal triage table filtered to threats and opportunities only."""
    st.subheader("Signal Triage — Threats & Opportunities")

    if df.empty:
        st.info("No signals to display.")
        return

    # Filter to only threats and opportunities
    triage_df = df[df["alert_level"] > 1].copy()

    if triage_df.empty:
        st.info("No active threats or opportunities to triage.")
        return

    # Sort by alert_level descending (threats first), then by date descending
    triage_df = triage_df.sort_values(
        ["alert_level", "date"], ascending=[False, False]
    )

    # Build HTML table rows
    rows_html = ""
    for _, row in triage_df.iterrows():
        alert_level = int(row.get("alert_level", 1))
        classification = row.get("classification", "neutral")
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

        # Determine row background color
        if alert_level == 3:
            row_bg = "rgba(220, 38, 38, 0.06)"
            level_badge = (
                '<span style="'
                "background:#FEE2E2; color:#DC2626; "
                "padding:2px 8px; border-radius:12px; "
                "font-size:12px; font-weight:600;"
                '">Level 3</span>'
            )
            class_badge = (
                '<span style="'
                "background:#FEE2E2; color:#DC2626; "
                "padding:2px 8px; border-radius:12px; "
                "font-size:11px; font-weight:500;"
                '">Threat</span>'
            )
        elif alert_level == 2:
            row_bg = "rgba(22, 163, 74, 0.06)"
            level_badge = (
                '<span style="'
                "background:#DCFCE7; color:#16A34A; "
                "padding:2px 8px; border-radius:12px; "
                "font-size:12px; font-weight:600;"
                '">Level 2</span>'
            )
            class_badge = (
                '<span style="'
                "background:#DCFCE7; color:#16A34A; "
                "padding:2px 8px; border-radius:12px; "
                "font-size:11px; font-weight:500;"
                '">Opportunity</span>'
            )
        else:
            row_bg = "transparent"
            level_badge = ""
            class_badge = ""

        # Build link
        if source_url:
            link_html = (
                f'<a href="{source_url}" target="_blank" '
                f'style="color:#1B2A4A; text-decoration:none; font-size:13px;">'
                f'🔗 View</a>'
            )
        else:
            link_html = '<span style="color:#9CA3AF; font-size:13px;">—</span>'

        # Entities tag
        if entities:
            entities_html = (
                f'<span style="'
                f"background:#F3F4F6; color:#374151; "
                f"padding:2px 6px; border-radius:4px; "
                f"font-size:11px; font-weight:500;"
                f'">{entities}</span>'
            )
        else:
            entities_html = ""

        # Explanation tooltip
        if explanation:
            explanation_html = (
                f'<span title="{explanation}" style="'
                f"border-bottom:1px dotted #9CA3AF; cursor:help;"
                f'">{explanation[:60]}{"..." if len(explanation) > 60 else ""}</span>'
            )
        else:
            explanation_html = "—"

        rows_html += f"""
        <tr style="background:{row_bg}; border-bottom:1px solid #F3F4F6;">
            <td style="padding:10px 12px; font-size:13px; color:#6B7280; white-space:nowrap;">
                {date_str}
            </td>
            <td style="padding:10px 12px; font-size:13px; color:#374151; font-weight:500;">
                {source}
            </td>
            <td style="padding:10px 12px; font-size:13px; color:#374151;">
                {topic.replace('_', ' ').title()}
            </td>
            <td style="padding:10px 12px; text-align:center;">
                {level_badge}
            </td>
            <td style="padding:10px 12px; text-align:center;">
                {class_badge}
            </td>
            <td style="padding:10px 12px; font-size:12px; color:#6B7280; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                {entities_html}
            </td>
            <td style="padding:10px 12px; font-size:12px; color:#6B7280; max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                {content_preview}
            </td>
            <td style="padding:10px 12px; font-size:11px; color:#6B7280; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-style:italic;">
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
        border:1px solid #E5E7EB;
        border-radius:8px;
        background:#FFFFFF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    ">
        <table style="width:100%; border-collapse:collapse; font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
            <thead style="position:sticky; top:0; z-index:1;">
                <tr style="background:#F9FAFB; border-bottom:2px solid #E5E7EB;">
                    <th style="padding:12px; text-align:left; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Date</th>
                    <th style="padding:12px; text-align:left; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Source</th>
                    <th style="padding:12px; text-align:left; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Topic</th>
                    <th style="padding:12px; text-align:center; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Level</th>
                    <th style="padding:12px; text-align:center; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Class</th>
                    <th style="padding:12px; text-align:left; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Entities</th>
                    <th style="padding:12px; text-align:left; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Preview</th>
                    <th style="padding:12px; text-align:left; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Why?</th>
                    <th style="padding:12px; text-align:center; font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:0.5px;">Link</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """

    st.markdown(table_html, unsafe_allow_html=True)

    # Summary caption
    threat_count = len(triage_df[triage_df["alert_level"] == 3])
    opp_count = len(triage_df[triage_df["alert_level"] == 2])
    st.caption(
        f"Showing {len(triage_df)} signals requiring attention "
        f"({threat_count} threats, {opp_count} opportunities). "
        "Red tint = Level 3 Threat, Green tint = Level 2 Opportunity."
    )