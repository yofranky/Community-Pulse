"""
Shared theme for Community Pulse — "Ops Console" styling.

Color palette is inspired by Pure Storage's real brand identity (black +
their signature vibrant orange) — reusing a company's public brand color
as an accent is a normal, low-risk design choice (unlike using their name
or logo, which this project deliberately avoids — see PRIVACY.md). This
is not an attempt to clone their full corporate identity system, just a
palette choice that fits the subject matter.

Every page (app.py + app/pages/*.py) should call inject_css() once near
the top and use render_sidebar_header() for a consistent wordmark/nav.
"""

import streamlit as st

# ── Design tokens ────────────────────────────────────────────────────
BG = "#0A0A0A"
SURFACE = "#161616"
SURFACE_2 = "#212121"
BORDER = "#333333"
TEXT = "#F5F5F5"
MUTED = "#9A9A9A"
ORANGE = "#FE5000"  # Pure Storage's real brand orange — accent + Threat signal
GREEN = "#3FB950"  # Opportunity signal

# Signature mark: a small inline "pulse waveform" — ties the UI directly
# to the product name rather than a generic icon.
PULSE_SVG = f"""<svg width="30" height="30" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M2 17H9L12 8L18 26L22 12L25 17H32" stroke="{ORANGE}" stroke-width="2.25"
stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def inject_css() -> None:
    """Inject the shared Ops Console CSS. Call once per page, near the top."""
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

            .stApp {{
                background-color: {BG};
                background-image:
                    linear-gradient(rgba(245,245,245,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(245,245,245,0.03) 1px, transparent 1px);
                background-size: 28px 28px;
            }}
            html, body, [class*="css"] {{
                font-family: 'IBM Plex Sans', sans-serif;
                color: {TEXT};
            }}
            h1, h2, h3, h4 {{
                font-family: 'IBM Plex Mono', monospace !important;
                color: {TEXT} !important;
                font-weight: 600 !important;
                letter-spacing: -0.3px;
            }}
            h1 {{ font-size: 26px !important; }}
            h2 {{
                font-size: 15px !important;
                text-transform: uppercase;
                letter-spacing: 1px !important;
                color: {MUTED} !important;
                font-weight: 600 !important;
            }}
            section[data-testid="stSidebar"] {{
                background-color: {SURFACE};
                border-right: 1px solid {BORDER};
            }}
            hr {{
                height: 1px;
                border: none;
                margin: 18px 0;
                background: linear-gradient(90deg, {BORDER} 0%, {ORANGE} 15%, {BORDER} 35%);
                opacity: 0.6;
            }}
            .stButton button {{
                border-radius: 4px;
                background: {SURFACE_2};
                color: {TEXT};
                border: 1px solid {BORDER};
                font-family: 'IBM Plex Mono', monospace;
            }}
            .stButton button:hover {{
                border-color: {ORANGE};
                color: {ORANGE};
            }}
            .stDataFrame, div[data-testid="stExpander"] {{
                border: 1px solid {BORDER} !important;
                border-radius: 6px;
                background: {SURFACE};
            }}
            .stCaption, [data-testid="stCaptionContainer"] {{
                color: {MUTED} !important;
                font-size: 12px !important;
            }}
            div[data-testid="stNotification"] {{
                background: {SURFACE} !important;
                border: 1px solid {BORDER} !important;
                color: {TEXT} !important;
            }}
            div[role="radiogroup"] label {{
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 13px;
                font-family: 'IBM Plex Mono', monospace;
                border: 1px solid transparent;
            }}
            div[role="radiogroup"] label:hover {{
                background: {SURFACE_2};
                border-color: {BORDER};
            }}
            /* Date input */
            .stDateInput input {{
                font-family: 'IBM Plex Mono', monospace;
                background: {SURFACE_2} !important;
                color: {TEXT} !important;
                border-color: {BORDER} !important;
            }}
            a {{ color: {ORANGE} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_wordmark() -> None:
    """Render the pulse mark + product wordmark at the top of the sidebar."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
            <span>{PULSE_SVG}</span>
            <div>
                <p style="margin:0; font-family:'IBM Plex Mono',monospace; font-size:18px; font-weight:700; color:{TEXT}; letter-spacing:-0.3px;">
                    Community Pulse
                </p>
                <p style="margin:0; font-size:11px; color:{MUTED}; text-transform:uppercase; letter-spacing:0.6px;">
                    Pure Intelligence Console
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_title(title: str, subtitle: str = "") -> None:
    """Render a page's main title with the pulse mark, consistent across pages."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:14px; margin-bottom:2px;">
            <span>{PULSE_SVG}</span>
            <h1 style="margin:0;">{title}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f'<p style="color:{MUTED}; font-size:14px; margin-top:0px; margin-bottom:20px;">{subtitle}</p>',
            unsafe_allow_html=True,
        )
