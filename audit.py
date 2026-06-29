from __future__ import annotations
import io
import re
import html as _html_mod
import time
import json
import socket
import random
import requests
import pandas as pd
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pypdf import PdfWriter

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

def _get_secret(key: str, default=None):
    """Safely read a Streamlit secret, returning default if secrets aren't configured."""
    try:
        val = st.secrets.get(key, default)
        return val
    except Exception:
        return default

def locationiq_autocomplete(query: str, api_key: str) -> tuple[list[dict], str]:
    """Query LocationIQ Autocomplete API for city/country/region suggestions.

    Uses the LocationIQ /v1/autocomplete endpoint which returns place
    predictions for cities, countries, and administrative areas.

    Returns (suggestions, error_message). suggestions is a list of
    {"description": str, "place_id": str} dicts. error_message is "" on
    success, or a human-readable reason so the UI can tell the rep why
    nothing showed up instead of silently doing nothing.
    """
    if not api_key:
        return [], "no_key"
    if not query or len(query.strip()) < 2:
        return [], ""
    try:
        resp = requests.get(
            "https://api.locationiq.com/v1/autocomplete",
            params={
                "key": api_key,
                "q": query.strip(),
                "limit": 5,
                "dedupe": 1,
                "tag": "place:city,place:country,place:state,place:region",
            },
            timeout=6,
        )
        if resp.status_code != 200:
            try:
                err = resp.json().get("error", resp.text[:200])
            except Exception:
                err = resp.text[:200]
            return [], f"HTTP {resp.status_code}: {err}"
        data = resp.json()
        suggestions = []
        for item in data:
            display = item.get("display_name", "")
            place_id = str(item.get("place_id", ""))
            if display:
                suggestions.append({"description": display, "place_id": place_id})
        return suggestions, ""
    except Exception as exc:
        return [], f"request_failed: {exc}"

def send_email_smtp(to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    try:
        smtp_host   = _get_secret("SMTP_HOST", "smtp.gmail.com")
        smtp_port   = int(_get_secret("SMTP_PORT", 587))
        smtp_user   = _get_secret("SMTP_USER")
        smtp_pass   = _get_secret("SMTP_PASSWORD")
        if not smtp_user or not smtp_pass:
            return False, "SMTP credentials not configured. Add SMTP_USER and SMTP_PASSWORD to your secrets.toml."

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = smtp_user
        msg["To"]      = to_addr
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_addr, msg.as_string())
        return True, "Sent successfully"
    except KeyError:
        return False, "SMTP credentials not configured."
    except Exception as e:
        return False, str(e)

st.set_page_config(
    page_title="fast.site — Lead Finder",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# PROFESSIONAL LIGHT THEME CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ════════════════════════════════════════════════════════
   LIGHT THEME — fast.site Lead Finder
   Palette:
     Page bg        #F0F4FF  (cool lavender-white)
     Surface        #FFFFFF
     Surface-2      #F8FAFF
     Border         #E2E8F4
     Brand blue     #2563EB
     Brand purple   #7C3AED
     Text primary   #0F172A
     Text secondary #475569
     Text muted     #94A3B8
     Green          #059669
     Amber          #D97706
     Red            #DC2626
════════════════════════════════════════════════════════ */

/* ── Reset & Base ─────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stApp {
    background: linear-gradient(160deg, #F8FAFF 0%, #F0F6FF 60%, #F5F8FF 100%) !important;
    min-height: 100vh !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
    box-shadow: none !important;
    height: 2.75rem !important;
}
header[data-testid="stHeader"] * { visibility: visible !important; }
#root > div:first-child { margin-top: 0 !important; }
.block-container {
    padding: 0 2.5rem 3rem 2.5rem !important;
    padding-top: 0.75rem !important;
    margin-top: 0 !important;
    max-width: 1180px !important;
}

/* ── Typography ───────────────────────────────────────── */
h1 {
    font-size: 1.75rem !important; font-weight: 800 !important;
    color: #0F172A !important; letter-spacing: -0.6px !important;
    margin-bottom: 0.2rem !important;
}
h2 { font-size: 1.2rem !important; font-weight: 700 !important; color: #1E293B !important; letter-spacing: -0.3px !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #1E293B !important; }
h4 { font-size: 0.92rem !important; font-weight: 700 !important; color: #334155 !important;
     letter-spacing: 0.04em !important; text-transform: uppercase !important; margin-bottom: 0.6rem !important; }
p, li, label, .stMarkdown { color: #334155 !important; font-size: 0.93rem !important; line-height: 1.65 !important; }
small, .stCaption, [data-testid="stCaptionContainer"] { color: #64748B !important; font-size: 0.8rem !important; }

/* ── Inputs ───────────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 10px !important;
    color: #0F172A !important;
    font-size: 0.93rem !important;
    padding: 0.6rem 0.9rem !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06) !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
    outline: none !important;
}
.stTextInput > div > div > input:hover,
.stNumberInput > div > div > input:hover {
    border-color: #93C5FD !important;
}
.stTextInput input::placeholder,
.stNumberInput input::placeholder,
.stTextArea textarea::placeholder,
input::placeholder,
textarea::placeholder {
    color: #94A3B8 !important;
    opacity: 1 !important;
    font-weight: 400 !important;
}
.stTextInput label, .stNumberInput label, .stRadio > label {
    font-weight: 600 !important; font-size: 0.82rem !important;
    color: #475569 !important; letter-spacing: 0.02em !important;
    text-transform: uppercase !important; margin-bottom: 5px !important;
}
/* textarea */
.stTextArea textarea {
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 10px !important;
    color: #0F172A !important;
    font-size: 0.9rem !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06) !important;
}
.stTextArea textarea:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}

/* ── Buttons ──────────────────────────────────────────── */
.stButton, [data-testid="stDownloadButton"] {
    display: flex !important; align-items: stretch !important;
}
.stButton > button, [data-testid="stDownloadButton"] > button {
    width: 100% !important; min-height: 2.75rem !important;
    display: flex !important; align-items: center !important;
    justify-content: center !important; cursor: pointer !important;
    border-radius: 10px !important; font-weight: 700 !important;
    font-size: 0.92rem !important; letter-spacing: 0.01em !important;
    transition: all 0.18s cubic-bezier(0.4,0,0.2,1) !important;
}
.stButton > button p, .stButton > button span,
[data-testid="stDownloadButton"] > button p,
[data-testid="stDownloadButton"] > button span { color: inherit !important; }

/* PRIMARY — vivid blue gradient, always white text */
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important;
    color: #FFFFFF !important; border: none !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.35), 0 1px 4px rgba(37,99,235,0.2) !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.12) !important;
}
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span,
button[data-testid="baseButton-primary"] p,
button[data-testid="baseButton-primary"] span { color: #FFFFFF !important; }
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 50%, #1E40AF 100%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 8px 24px rgba(37,99,235,0.45), 0 2px 6px rgba(37,99,235,0.25) !important;
    transform: translateY(-2px) !important;
}
.stButton > button[kind="primary"]:hover p,
.stButton > button[kind="primary"]:hover span,
button[data-testid="baseButton-primary"]:hover p,
button[data-testid="baseButton-primary"]:hover span { color: #FFFFFF !important; }
.stButton > button[kind="primary"]:active,
button[data-testid="baseButton-primary"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:disabled,
button[data-testid="baseButton-primary"]:disabled {
    background: #BFDBFE !important; color: #93C5FD !important;
    box-shadow: none !important; cursor: not-allowed !important;
}
.stButton > button[kind="primary"]:disabled p,
.stButton > button[kind="primary"]:disabled span { color: #93C5FD !important; }

/* SECONDARY — clean white card with blue border */
.stButton > button:not([kind="primary"]) {
    background: #FFFFFF !important;
    color: #2563EB !important;
    border: 1.5px solid #BFDBFE !important;
    box-shadow: 0 1px 4px rgba(37,99,235,0.08) !important;
}
.stButton > button:not([kind="primary"]) p,
.stButton > button:not([kind="primary"]) span { color: #2563EB !important; }
.stButton > button:not([kind="primary"]):hover {
    background: #EFF6FF !important;
    color: #1D4ED8 !important;
    border-color: #2563EB !important;
    box-shadow: 0 4px 16px rgba(37,99,235,0.18) !important;
    transform: translateY(-2px) !important;
}
.stButton > button:not([kind="primary"]):hover p,
.stButton > button:not([kind="primary"]):hover span { color: #1D4ED8 !important; }
.stButton > button:not([kind="primary"]):active {
    transform: translateY(0) !important;
    color: #1E40AF !important;
}
.stButton > button:not([kind="primary"]):active p,
.stButton > button:not([kind="primary"]):active span { color: #1E40AF !important; }
.stButton > button:not([kind="primary"]):disabled {
    background: #F8FAFC !important; color: #94A3B8 !important;
    border-color: #E2E8F0 !important; box-shadow: none !important;
}
.stButton > button:not([kind="primary"]):disabled p,
.stButton > button:not([kind="primary"]):disabled span { color: #94A3B8 !important; }

/* DOWNLOAD — same gradient as primary */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important;
    color: #FFFFFF !important; border: none !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.12) !important;
}
[data-testid="stDownloadButton"] > button p,
[data-testid="stDownloadButton"] > button span { color: #FFFFFF !important; }
[data-testid="stDownloadButton"] > button:hover {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 8px 24px rgba(37,99,235,0.45) !important;
    transform: translateY(-2px) !important;
}
[data-testid="stDownloadButton"] > button:hover p,
[data-testid="stDownloadButton"] > button:hover span { color: #FFFFFF !important; }

/* ── Tooltip ──────────────────────────────────────────── */
[data-testid="stTooltipIcon"] { color: #2563EB !important; opacity: 1 !important; }
div[role="tooltip"],
[data-testid="stTooltipContent"],
[data-testid="stTooltipPopover"],
.stTooltipContent,
[data-radix-popper-content-wrapper] > div,
[data-radix-tooltip-content] {
    background: #1E293B !important;
    color: #F1F5F9 !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    box-shadow: 0 8px 24px rgba(15,23,42,0.25) !important;
    max-width: 300px !important;
    line-height: 1.6 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}
div[role="tooltip"] *, [data-testid="stTooltipContent"] *,
[data-testid="stTooltipPopover"] *,
[data-radix-popper-content-wrapper] > div *,
[data-radix-tooltip-content] * {
    color: #F1F5F9 !important; background: transparent !important;
}

/* ── Layout helpers ───────────────────────────────────── */
[data-testid="column"] { display: flex !important; flex-direction: column !important; justify-content: flex-start !important; }
[data-testid="stHorizontalBlock"] { align-items: stretch !important; gap: 0.75rem !important; }

/* ── Radio Pills ──────────────────────────────────────── */
.stRadio > div { gap: 0.5rem !important; flex-direction: row !important; flex-wrap: wrap !important; }
.stRadio > div > label {
    background: #FFFFFF !important; border: 1.5px solid #CBD5E1 !important;
    border-radius: 9px !important; padding: 0.5rem 1.2rem !important;
    cursor: pointer !important;
    transition: all 0.17s !important;
    font-weight: 600 !important; font-size: 0.88rem !important; color: #475569 !important;
}
.stRadio > div > label:hover { border-color: #2563EB !important; color: #2563EB !important; background: #EFF6FF !important; }
.stRadio > div > label:has(input:checked) {
    border-color: #2563EB !important; background: #EFF6FF !important;
    color: #1D4ED8 !important; font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.15) !important;
}

/* ── Alerts ───────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important; border-left-width: 4px !important;
    font-size: 0.9rem !important; box-shadow: 0 1px 6px rgba(15,23,42,0.06) !important;
}

/* ── Metrics ──────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F4 !important;
    border-radius: 14px !important;
    padding: 1.1rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.06) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important; font-weight: 700 !important;
    color: #64748B !important; text-transform: uppercase !important; letter-spacing: 0.07em !important;
}
[data-testid="stMetricValue"] { font-size: 2.1rem !important; font-weight: 800 !important; color: #0F172A !important; }
[data-testid="stMetricDelta"] { font-size: 0.82rem !important; }

/* ── Expanders ────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F4 !important;
    border-radius: 12px !important;
    margin-bottom: 0.75rem !important;
    overflow: hidden !important;
    box-shadow: 0 2px 8px rgba(15,23,42,0.05) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important; font-size: 0.93rem !important;
    color: #1E293B !important; padding: 0.9rem 1.2rem !important;
    background: #FAFBFF !important;
}
[data-testid="stExpander"] summary:hover { background: #EFF6FF !important; }

/* ── Dividers ─────────────────────────────────────────── */
hr { border: none !important; border-top: 1px solid #E2E8F4 !important; margin: 1.25rem 0 !important; }

/* ── Checkbox ─────────────────────────────────────────── */
.stCheckbox label { color: #334155 !important; font-weight: 500 !important; font-size: 0.92rem !important; }

/* ── Progress bar ─────────────────────────────────────── */
.stProgress > div > div {
    background: linear-gradient(90deg, #2563EB, #7C3AED) !important;
    border-radius: 99px !important;
}
.stProgress > div { border-radius: 99px !important; background: #E2E8F4 !important; }

/* ── Spinner ──────────────────────────────────────────── */
[data-testid="stSpinner"] p { color: #475569 !important; font-size: 0.88rem !important; }

/* ── Tech badges ──────────────────────────────────────── */
.tech-badge {
    display: inline-block; padding: 3px 10px; border-radius: 6px;
    font-size: 11px; font-weight: 700; margin: 2px 2px; letter-spacing: 0.03em;
}
.score-chip {
    display: inline-block; padding: 4px 14px; border-radius: 6px;
    font-size: 13px; font-weight: 700; margin: 0 4px;
}

/* ── Custom components ────────────────────────────────── */
.fs-tag {
    display: inline-flex; align-items: center; padding: 3px 10px;
    border-radius: 6px; font-size: 11px; font-weight: 600;
    background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;
    margin: 2px 3px 2px 0;
}
.fs-tag.cms { background: #EFF6FF; color: #1D4ED8; border-color: #BFDBFE; }

.fs-score-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
    gap: 10px; margin-bottom: 0.5rem;
}
.fs-score-tile {
    background: #FAFBFF; border: 1.5px solid #E2E8F4; border-radius: 10px;
    padding: 0.85rem 0.6rem; text-align: center;
    box-shadow: 0 1px 4px rgba(15,23,42,0.04);
}
.fs-score-tile.highlight { border: 2px solid #2563EB; background: #EFF6FF; }
.fs-score-tile .fs-val { font-size: 1.6rem; font-weight: 800; line-height: 1; }
.fs-score-tile .fs-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; margin-top: 4px; color: #64748B;
}

.fs-alert-bar {
    display: flex; align-items: flex-start; gap: 12px;
    background: #FFFBEB; border: 1px solid #FDE68A;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 1rem;
    font-size: 0.88rem; line-height: 1.6; color: #92400E;
}
.fs-alert-bar .fs-alert-icon { font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }

.fs-contact-card {
    background: #FAFBFF; border: 1px solid #E2E8F4; border-radius: 12px;
    padding: 1rem 1.25rem; margin-bottom: 0.75rem;
    box-shadow: 0 1px 4px rgba(15,23,42,0.04);
}
.fs-contact-card h4 {
    font-size: 0.78rem !important; font-weight: 700 !important; color: #64748B !important;
    text-transform: uppercase !important; letter-spacing: 0.07em !important; margin-bottom: 0.6rem !important;
}
.fs-contact-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.fs-contact-item .fs-c-label { font-size: 11px; color: #94A3B8; margin-bottom: 2px; }
.fs-contact-item .fs-c-val { font-size: 0.88rem; color: #0F172A; font-weight: 600; }
.fs-contact-item .fs-c-val a { color: #2563EB; text-decoration: none; }
.fs-contact-item .fs-c-val a:hover { text-decoration: underline; color: #1D4ED8; }

/* ── App Header ───────────────────────────────────────── */
.app-header {
    display: flex; align-items: center; gap: 16px;
    margin-bottom: 1.75rem; padding: 1.4rem 2rem;
    background: linear-gradient(135deg, #1E40AF 0%, #2563EB 50%, #7C3AED 100%);
    border-radius: 0 0 16px 16px;
    position: relative; overflow: hidden;
    box-shadow: 0 4px 20px rgba(37,99,235,0.25);
}
.app-header::before {
    content: ''; position: absolute; top: -60px; right: -40px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
    pointer-events: none;
}
.app-header-title {
    font-size: 1.35rem !important; font-weight: 800 !important;
    color: #FFFFFF !important; line-height: 1.2 !important; margin: 0 !important;
}
.app-header-sub { font-size: 0.8rem; color: rgba(255,255,255,0.75); margin: 3px 0 0 0; }
.app-header-pill {
    margin-left: auto; background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.35); border-radius: 99px;
    padding: 4px 14px; font-size: 0.75rem; font-weight: 600;
    color: #FFFFFF; letter-spacing: 0.03em; white-space: nowrap;
}

/* ── Section dividers ─────────────────────────────────── */
.section-label {
    display: inline-flex; align-items: center; gap: 7px;
    color: #64748B; font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.35rem;
}
.section-divider {
    display: flex; align-items: center; gap: 10px;
    margin: 1.5rem 0 1rem 0;
}
.section-divider-line { flex: 1; height: 1px; background: #E2E8F4; }
.section-divider-label {
    font-size: 0.72rem; font-weight: 700; color: #475569;
    letter-spacing: 0.08em; text-transform: uppercase;
    background: #EFF6FF; padding: 3px 12px; border-radius: 99px;
    border: 1px solid #BFDBFE; color: #1D4ED8;
}

/* ── Cards ────────────────────────────────────────────── */
.result-card {
    background: #FFFFFF; border: 1px solid #E2E8F4; border-radius: 12px;
    padding: 1.1rem 1.4rem; margin-bottom: 0.6rem;
    box-shadow: 0 2px 8px rgba(15,23,42,0.05);
    transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
}
.result-card:hover {
    box-shadow: 0 8px 24px rgba(37,99,235,0.12); border-color: #BFDBFE;
    transform: translateY(-2px);
}
.search-card {
    background: #FFFFFF; border: 1px solid #E2E8F4; border-radius: 14px;
    padding: 1.6rem 1.75rem; margin-bottom: 1.25rem;
    box-shadow: 0 2px 8px rgba(15,23,42,0.05);
}

/* ── Footer ───────────────────────────────────────────── */
.app-footer {
    margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid #E2E8F4;
    font-size: 0.78rem; color: #94A3B8; text-align: center; letter-spacing: 0.01em;
}

/* ── Tabs ─────────────────────────────────────────────── */
[data-testid="stTabs"] > div:first-child {
    background: #FFFFFF !important;
    border-radius: 14px 14px 0 0 !important;
    border: 1px solid #E2E8F4 !important;
    border-bottom: none !important;
    padding: 0 8px !important;
    box-shadow: 0 -1px 0 #E2E8F4 !important;
}
[data-testid="stTabs"] [role="tab"] {
    font-weight: 700 !important; font-size: 0.9rem !important;
    color: #64748B !important; padding: 0.85rem 1.5rem !important;
    border-radius: 10px 10px 0 0 !important;
    transition: all 0.18s ease !important; letter-spacing: 0.01em !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
    color: #2563EB !important; background: #EFF6FF !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #1D4ED8 !important; background: #EFF6FF !important;
    border-bottom: 3px solid #2563EB !important;
}
[data-testid="stTabsContent"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F4 !important;
    border-top: none !important;
    border-radius: 0 0 14px 14px !important;
    padding: 1.5rem 1.75rem !important;
    margin-bottom: 1.5rem !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.06) !important;
}

/* ── Sidebar ──────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E3A8A 0%, #1E40AF 40%, #312E81 100%) !important;
    border-right: none !important;
    min-width: 260px !important; max-width: 260px !important;
    box-shadow: 4px 0 20px rgba(37,99,235,0.15) !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebarCollapseButton"] button {
    background: rgba(255,255,255,0.15) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    border-radius: 6px !important;
}
[data-testid="stSidebarCollapsedControl"] button {
    background: #1E3A8A !important; color: white !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
}
[data-testid="stSidebar"] * { color: rgba(255,255,255,0.9) !important; }
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.1) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    box-shadow: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 0.9rem !important;
    text-align: left !important; justify-content: flex-start !important;
    padding: 0.6rem 0.9rem !important; width: 100% !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button p,
[data-testid="stSidebar"] .stButton > button span { color: #FFFFFF !important; }
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.22) !important;
    color: #FFFFFF !important;
    border-color: rgba(255,255,255,0.4) !important;
    transform: none !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
}
[data-testid="stSidebar"] .stButton > button:hover p,
[data-testid="stSidebar"] .stButton > button:hover span { color: #FFFFFF !important; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: rgba(255,255,255,0.2) !important;
    color: #FFFFFF !important; border: 2px solid rgba(255,255,255,0.5) !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: rgba(255,255,255,0.32) !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover p,
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover span { color: #FFFFFF !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }
.sidebar-logo {
    padding: 1.25rem 0.9rem 0.5rem 0.9rem;
    border-bottom: 1px solid rgba(255,255,255,0.12);
    margin-bottom: 0.5rem;
}
.sidebar-section-label {
    font-size: 0.68rem !important; font-weight: 700 !important;
    color: rgba(255,255,255,0.45) !important; letter-spacing: 0.12em !important;
    text-transform: uppercase !important; padding: 0.8rem 0.9rem 0.3rem 0.9rem !important;
}
.sidebar-user-info {
    padding: 0.75rem 0.9rem;
    background: rgba(255,255,255,0.1);
    border-radius: 10px; margin: 0.5rem 0.5rem;
    font-size: 0.82rem; border: 1px solid rgba(255,255,255,0.15);
}
</style>
<script>
(function() {
  function tryOpenSidebar() {
    var btn = document.querySelector('[data-testid="stSidebarCollapsedControl"] button');
    if (btn) { btn.click(); return true; }
    return false;
  }
  // Try immediately and after short delays for initial load
  setTimeout(tryOpenSidebar, 300);
  setTimeout(tryOpenSidebar, 800);
  setTimeout(tryOpenSidebar, 1500);
  // Watch for sidebar being collapsed and reopen it
  var obs = new MutationObserver(function() {
    tryOpenSidebar();
  });
  document.addEventListener('DOMContentLoaded', function() {
    obs.observe(document.body, { childList: true, subtree: false });
    tryOpenSidebar();
  });
})();
</script>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE SELECTION — shown once at startup, stored in session_state
# ─────────────────────────────────────────────────────────────────────────────
if "lang" not in st.session_state:
    st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;min-height:58vh;flex-direction:column;gap:1.75rem;">
  <div style="text-align:center;">
    <div style="
      width:72px;height:72px;
      background:linear-gradient(135deg,#0D1526 0%,#1E3A7A 100%);
      border-radius:20px;margin:0 auto 1.25rem auto;
      display:flex;align-items:center;justify-content:center;
      font-size:32px;box-shadow:0 8px 24px rgba(37,99,235,0.35);">⚡</div>
    <div style="font-size:2.2rem;font-weight:800;color:#0F172A;margin-bottom:0.3rem;letter-spacing:-0.5px;">
      fast.site <span style="color:#3B82F6;font-weight:400;font-size:1.4rem;letter-spacing:0;">Lead Finder</span>
    </div>
    <div style="font-size:0.95rem;color:#94A3B8;margin-bottom:0.2rem;">
      Find slow websites · Extract contacts · Generate cold emails
    </div>
    <div style="display:inline-block;background:rgba(37,99,235,0.18);color:#93C5FD;border:1px solid rgba(59,130,246,0.35);
      border-radius:99px;padding:4px 16px;font-size:0.78rem;font-weight:700;letter-spacing:0.05em;
      text-transform:uppercase;margin-top:0.75rem;">Choose your language · Sprache wählen</div>
  </div>
</div>
""", unsafe_allow_html=True)

    col_l, col_mid, col_r = st.columns([2, 2, 2])
    with col_mid:
        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        if st.button("🇬🇧  English", use_container_width=True, type="primary"):
            st.session_state["lang"] = "en"
            st.rerun()
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        if st.button("🇩🇪  Deutsch", use_container_width=True):
            st.session_state["lang"] = "de"
            st.rerun()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION HELPER
# ─────────────────────────────────────────────────────────────────────────────
_LANG: str = st.session_state.get("lang", "en")

def _t(en: str, de: str) -> str:
    return de if _LANG == "de" else en

# ─────────────────────────────────────────────────────────────────────────────
# URL VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
_URL_RE = re.compile(
    r"^(?:https?://)?"           # optional scheme
    r"(?:[A-Za-z0-9-]+\.)+"     # one or more subdomain/domain labels
    r"[A-Za-z]{2,}"             # TLD (at least 2 letters)
    r"(?:[/?#][^\s]*)?"         # optional path/query/fragment
    r"$",
    re.IGNORECASE,
)

def _is_valid_url(raw: str) -> bool:
    """Return True only if raw looks like a real hostname/URL."""
    if not raw:
        return False
    # After stripping a leading scheme, there must be a dot-separated hostname
    stripped = re.sub(r"^https?://", "", raw.strip(), flags=re.I)
    if not _URL_RE.match(raw.strip()):
        return False
    # Must contain at least one dot in the host part
    host = stripped.split("/")[0].split("?")[0].split("#")[0]
    return "." in host

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH — delegate entirely to search.py (no duplication)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from search import search as _search_engine
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False

def multi_engine_search(industry: str, area: str, max_results: int = 20) -> tuple[list[dict], list[str]]:
    """Delegate to search.py's search() function."""
    if not SEARCH_AVAILABLE:
        return [], [_t("search.py not found", "search.py nicht gefunden")]
    results, engine = _search_engine(industry, area, max_results)
    return results, [engine] if isinstance(engine, str) else engine

# ─────────────────────────────────────────────────────────────────────────────
# TECH DETECTION  — CMS signatures & plugin detection
# ─────────────────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/123.0.0.0",
]

def _headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

CMS_SIGNATURES: dict[str, list[tuple[str, float]]] = {
    "WordPress": [
        (r"/wp-content/themes/", 2.0), (r"/wp-content/plugins/", 2.0),
        (r"/wp-includes/js/", 2.0), (r"/wp-json/", 1.5),
        (r"wp-embed\.min\.js", 1.5), (r'content="WordPress', 1.5),
        (r"xmlrpc\.php", 1.0), (r"/wp-content/uploads/", 1.0),
        (r"wp-block-", 0.8), (r"class=\"wp-", 0.7), (r"WordPress", 0.5),
    ],
    "Shopify": [
        (r"cdn\.shopify\.com", 2.0), (r"myshopify\.com", 2.0),
        (r"Shopify\.theme", 2.0), (r"shopify-section", 1.5),
        (r"shopify\.com/s/files/", 1.5), (r'"shopify"', 1.0),
        (r"Shopify\.shop", 1.0), (r"/collections/", 0.5),
    ],
    "Wix": [
        (r"wixstatic\.com", 2.0), (r"wix\.com/_api/", 2.0),
        (r"X-Wix-Published-Version", 2.0), (r"wix-code", 1.5),
        (r"\"wix\"", 1.0), (r"parastorage\.com", 1.0), (r"wixsite\.com", 1.5),
    ],
    "Squarespace": [
        (r"squarespace\.com", 2.0), (r"sqsp\.net", 2.0),
        (r"static1\.squarespace\.com", 2.0), (r'"squarespace"', 1.5),
        (r"Squarespace-Headers", 1.5), (r"sqs-layout", 1.0), (r"data-sqs-type", 1.0),
    ],
    "Webflow": [
        (r"webflow\.com", 2.0), (r"webflow\.io", 2.0),
        (r"data-wf-page", 2.0), (r"data-wf-site", 2.0),
        (r"webflow\.js", 1.5), (r'"webflow"', 1.0),
    ],
    "Joomla": [
        (r"/components/com_content", 2.0), (r"/components/com_", 1.5),
        (r'content="Joomla', 2.0), (r"joomla", 1.0),
        (r"/media/system/js/", 0.8), (r"Joomla!", 0.8), (r"/administrator/", 0.5),
    ],
    "Drupal": [
        (r"/sites/default/files/", 2.0), (r"Drupal\.settings", 2.0),
        (r'content="Drupal', 2.0), (r"drupal\.js", 1.5),
        (r"drupal", 0.8), (r"/misc/drupal\.js", 1.5), (r"X-Generator.*Drupal", 2.0),
    ],
    "Magento": [
        (r"Mage\.Cookies", 2.0), (r"/skin/frontend/", 2.0),
        (r"magento", 1.0), (r"var BLANK_URL", 1.0),
        (r"Magento_", 1.5), (r"/pub/static/frontend/", 1.5),
    ],
    "Ghost": [
        (r"content\.ghost\.io", 2.0), (r"ghost\.io", 1.5),
        (r'content="Ghost', 2.0), (r"ghost-theme", 1.5), (r"/ghost/api/", 2.0),
    ],
    "Next.js": [(r"_next/static/chunks/", 2.0), (r"__NEXT_DATA__", 2.0), (r"_next/image", 1.5)],
    "Nuxt.js": [(r"__nuxt", 2.0), (r"_nuxt/", 2.0), (r"nuxt-link", 1.5), (r"window\.__nuxt", 2.0)],
    "Gatsby":  [(r"gatsby-", 1.5), (r"/static/gatsby-", 2.0), (r"window\.___gatsby", 2.0)],
    "HubSpot CMS": [(r"hs-scripts\.com", 2.0), (r"hubspot\.com", 1.5), (r"hs-analytics", 1.5)],
    "Framer": [(r"framer\.com", 2.0), (r"framerusercontent\.com", 2.0)],
    "BigCommerce": [(r"bigcommerce\.com", 2.0), (r"cdn\.bigcommerce\.com", 2.0)],
}

HEADER_CMS_MAP: dict[str, str] = {
    "x-shopify-stage": "Shopify", "x-shopid": "Shopify",
    "x-wix-request-id": "Wix", "x-ghost-cache-status": "Ghost",
    "x-drupal-cache": "Drupal", "x-generator": None,
    "x-powered-by-squarespace": "Squarespace",
}

GENERATOR_MAP: dict[str, str] = {
    "wordpress": "WordPress", "joomla": "Joomla", "drupal": "Drupal",
    "ghost": "Ghost", "craft cms": "Craft CMS", "typo3": "TYPO3",
    "squarespace": "Squarespace", "webflow": "Webflow", "framer": "Framer",
    "wix": "Wix", "blogger": "Blogger", "hubspot": "HubSpot CMS",
    "bigcommerce": "BigCommerce", "prestashop": "PrestaShop",
    "opencart": "OpenCart", "magento": "Magento",
}

_INFRASTRUCTURE_LABELS: dict[str, str] = {
    "cloudflare": "Cloudflare CDN", "fastly": "Fastly CDN",
    "akamai": "Akamai CDN", "cloudfront": "AWS CloudFront",
    "bunnycdn": "BunnyCDN", "b-cdn": "BunnyCDN",
}

PLUGIN_SIGNATURES: dict[str, str] = {
    "WooCommerce": r"woocommerce", "Elementor": r"elementor",
    "Yoast SEO": r"yoast|yoast-schema", "Rank Math SEO": r"rank-math|rankmath",
    "Contact Form 7": r"wpcf7|contact-form-7", "Gravity Forms": r"gform_|gravityforms",
    "WPML": r"\bwpml\b", "Akismet": r"akismet", "Jetpack": r"jetpack",
    "WP Rocket": r"wp-rocket|wprocket", "All-in-One SEO": r"aioseo|all-in-one-seo",
    "Divi Builder": r"divi|et_pb_", "WPBakery": r"wpb_|vc_",
    "Beaver Builder": r"fl-builder|beaver-builder",
    "Google Analytics 4": r"G-[A-Z0-9]{6,}|gtag\(.*G-",
    "Google Analytics UA": r"UA-\d{5,}-\d+",
    "Google Tag Manager": r"googletagmanager\.com|GTM-[A-Z0-9]+",
    "Facebook Pixel": r"fbq\(|facebook\.net/en_US/fbevents",
    "Hotjar": r"hotjar\.com|hjid", "Clarity (Microsoft)": r"clarity\.ms|microsoft.*clarity",
    "Mixpanel": r"mixpanel\.com", "Segment": r"segment\.com|analytics\.js",
    "Intercom": r"intercom\.io|intercomcdn", "Tawk.to": r"tawk\.to",
    "Zendesk Chat": r"zendesk\.com|zopim\.com", "Crisp Chat": r"crisp\.chat",
    "Drift": r"drift\.com", "Tidio": r"tidio", "LiveChat": r"livechatinc\.com",
    "Cloudflare": r"cloudflare", "Fastly": r"fastly",
    "AWS CloudFront": r"cloudfront\.net", "Akamai": r"akamai",
    "reCAPTCHA": r"recaptcha", "hCaptcha": r"hcaptcha",
    "Bootstrap": r"bootstrap\.min\.css|bootstrap\.css|bootstrap\.min\.js",
    "Tailwind CSS": r"tailwind|tailwindcss", "jQuery": r"jquery\.min\.js|jquery-\d",
    "React": r"react\.production\.min|react-dom|__react",
    "Vue.js": r"vue\.global|vue\.esm|vue@\d|createApp\(",
    "Angular": r"angular\.min\.js|ng-version|zone\.js",
    "Alpine.js": r"alpine\.min\.js|x-data=",
    "Next.js": r"__NEXT_DATA__|_next/static",
    "Nuxt.js": r"__nuxt|_nuxt/", "Svelte": r"svelte-",
    "Stripe": r"stripe\.com/v3|js\.stripe\.com", "PayPal": r"paypal\.com/sdk",
    "HubSpot Forms": r"hsforms\.net|hbspt\.forms", "Mailchimp": r"mailchimp\.com|mc\.js",
    "Klaviyo": r"klaviyo\.com|kl-private", "ActiveCampaign": r"activecampaign\.com",
    "Cookiebot": r"cookiebot\.com", "OneTrust": r"onetrust\.com|onetrust-banner",
    "CookieYes": r"cookieyes\.com",
}

def _extract_generator_meta(soup) -> str | None:
    tag = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None

def _resolve_unknown_cms(t: dict) -> tuple[str, str | None]:
    plugins_lc = " ".join(t.get("plugins", [])).lower()
    svr_raw    = t.get("server") or ""
    svr_lc     = svr_raw.lower()
    if "next.js" in plugins_lc:   return "Next.js", "medium"
    if "nuxt.js" in plugins_lc:   return "Nuxt.js", "medium"
    if "react"   in plugins_lc:   return "Custom (React)", "low"
    if "angular" in plugins_lc:   return "Custom (Angular)", "low"
    if "vue.js"  in plugins_lc:   return "Custom (Vue)", "low"
    if "wordpress" in plugins_lc or "woocommerce" in plugins_lc: return "WordPress", "medium"
    if "shopify"    in plugins_lc: return "Shopify", "medium"
    if "wix"        in plugins_lc: return "Wix", "medium"
    if "squarespace"in plugins_lc: return "Squarespace", "medium"
    if "webflow"    in plugins_lc: return "Webflow", "medium"
    if "drupal"     in plugins_lc: return "Drupal", "medium"
    if "joomla"     in plugins_lc: return "Joomla", "medium"
    if "svelte"     in plugins_lc: return "Custom (Svelte)", "low"
    if "gatsby"     in plugins_lc: return "Gatsby", "low"
    if svr_lc:
        for infra_key, infra_label in _INFRASTRUCTURE_LABELS.items():
            if infra_key in svr_lc:
                return f"Hidden behind {infra_label}", "low"
        if "php" in svr_lc:
            return "Custom PHP site", "low"
        svr_label = svr_raw.split("/")[0].strip()[:20] or "Unknown server"
        return f"Custom site ({svr_label})", "low"
    return "Unknown", None

def detect_tech(url: str, timeout: int = 12) -> dict:
    result: dict = {
        "cms": "Unknown", "cms_confidence": None,
        "plugins": [], "frameworks": [],
        "server": None, "https": url.startswith("https"), "ip": None, "error": None,
    }
    try:
        resp     = requests.get(url, headers=_headers(), timeout=timeout, allow_redirects=True, stream=False)
        raw_html = resp.text
        html_lc  = raw_html.lower()
        hdrs     = resp.headers
        hdrs_lc  = {k.lower(): v.lower() for k, v in hdrs.items()}
        soup     = BeautifulSoup(raw_html, "lxml")

        result["server"] = (hdrs.get("Server") or hdrs.get("X-Powered-By") or hdrs.get("x-powered-by") or None)
        try:
            result["ip"] = socket.gethostbyname(urlparse(url).netloc)
        except Exception:
            pass

        cms_detected = "Unknown"
        confidence   = None

        gen = _extract_generator_meta(soup)
        if gen:
            gen_lc = gen.lower()
            for keyword, cms_name in GENERATOR_MAP.items():
                if keyword in gen_lc:
                    cms_detected = cms_name; confidence = "high"; break

        if cms_detected == "Unknown":
            for hdr_key, cms_name in HEADER_CMS_MAP.items():
                if hdr_key in hdrs_lc:
                    if cms_name:
                        cms_detected = cms_name; confidence = "high"; break
                    elif hdr_key == "x-generator":
                        val = hdrs_lc[hdr_key]
                        for keyword, cname in GENERATOR_MAP.items():
                            if keyword in val:
                                cms_detected = cname; confidence = "high"; break
                    if cms_detected != "Unknown":
                        break
            if cms_detected == "Unknown":
                xpb = hdrs_lc.get("x-powered-by", "")
                for keyword, cname in GENERATOR_MAP.items():
                    if keyword in xpb:
                        cms_detected = cname; confidence = "high"; break

        if cms_detected == "Unknown":
            best_cms = "Unknown"; best_score = 0.0
            combined = html_lc + " " + str(hdrs_lc)
            for cms_name, patterns in CMS_SIGNATURES.items():
                total = sum(w for pat, w in patterns if re.search(pat, combined, re.I))
                if total > best_score:
                    best_score = total; best_cms = cms_name
            if best_score >= 2.0:
                cms_detected = best_cms
                confidence   = "high" if best_score >= 3.0 else "medium"
            elif best_score >= 1.0:
                cms_detected = best_cms; confidence = "low"

        result["cms"]            = cms_detected
        result["cms_confidence"] = confidence
        found = [name for name, pat in PLUGIN_SIGNATURES.items() if re.search(pat, html_lc, re.I)]
        result["plugins"] = found
    except Exception as e:
        result["error"] = str(e)
    return result

# ─────────────────────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────────────────────
try:
    from audit import audit_website
    from audit_pdf import generate_audit_pdf
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False
    def audit_website(url, progress_callback=None):
        try:
            start = time.time()
            r     = requests.get(url, headers=_headers(), timeout=15)
            ttfb  = round((time.time() - start) * 1000)
            soup  = BeautifulSoup(r.text, "lxml")
        except Exception:
            return {"url": url, "overall_score": 0, "breakdown": {}, "lighthouse_details": {}, "fastsite_projection": {}}
        score = 0; issues = []; strengths = []
        if url.startswith("https"):
            score += 15; strengths.append("HTTPS enabled")
        else:
            issues.append("No HTTPS")
        title = soup.find("title")
        if title and title.get_text(strip=True):
            score += 10; strengths.append("Title tag present")
        else:
            issues.append("Missing title tag")
        h1s = soup.find_all("h1")
        if len(h1s) == 1:   score += 10; strengths.append("Single H1 tag")
        elif not h1s:        issues.append("No H1 tag")
        meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        if meta and meta.get("content", "").strip():
            score += 10; strengths.append("Meta description present")
        else:
            issues.append("No meta description")
        ttfb_score = 30 if ttfb < 500 else (20 if ttfb < 1000 else 5)
        score += ttfb_score
        if ttfb < 500: strengths.append(f"Fast TTFB: {ttfb}ms")
        else:          issues.append(f"Slow TTFB: {ttfb}ms")
        return {
            "url": url, "overall_score": min(score + 25, 100),
            "breakdown": {"seo": {"score": score, "issues": issues, "strengths": strengths, "details": {}}},
            "lighthouse_details": {}, "fastsite_projection": {},
        }

    def generate_audit_pdf(audit, lang="en"):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            buf    = io.BytesIO()
            doc    = SimpleDocTemplate(buf, pagesize=A4)
            styles = getSampleStyleSheet()
            story  = [Paragraph(f"Audit: {audit.get('url')}", styles["Title"]),
                      Paragraph(f"Score: {audit.get('overall_score')}/100", styles["Normal"])]
            for cat, data in audit.get("breakdown", {}).items():
                story.append(Paragraph(f"{cat}: {data.get('score')}/100", styles["Heading2"]))
                for iss in data.get("issues", []):
                    story.append(Paragraph(f"[!] {iss}", styles["Normal"]))
            doc.build(story)
            return buf.getvalue()
        except Exception:
            return b"%PDF-placeholder"

# ─── Lead generation tools ────────────────────────────────────────────────────
try:
    from lead_tools import (
        varnish_opportunity_score,
        opportunity_label,
        generate_cold_email,
        build_leads_csv,
    )
    LEAD_TOOLS_AVAILABLE = True
except ImportError:
    LEAD_TOOLS_AVAILABLE = False
    def varnish_opportunity_score(audit): return 0
    def opportunity_label(score): return ("—", "#888")
    def generate_cold_email(**kw): return "lead_tools.py not found"
    def build_leads_csv(*a, **kw): return b""

def _add_contacted_column(csv_bytes: bytes, contacted_map: dict) -> bytes:
    """Append 'Contacted' / 'Contacted At' columns to an exported leads CSV,
    matched against whichever column holds the site URL."""
    if not csv_bytes or not contacted_map:
        return csv_bytes
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        url_col = next((c for c in df.columns if "url" in c.lower()), None)
        if not url_col:
            return csv_bytes
        df["Contacted"]    = df[url_col].apply(lambda u: "Yes" if u in contacted_map else "No")
        df["Contacted At"] = df[url_col].apply(lambda u: contacted_map.get(u, {}).get("at", ""))
        return df.to_csv(index=False).encode("utf-8")
    except Exception:
        return csv_bytes

try:
    from contact_extractor import extract_contact_info, detect_cdn
    CONTACT_AVAILABLE = True
except ImportError:
    CONTACT_AVAILABLE = False
    def extract_contact_info(url): return {"emails": [], "phones": [], "contact_page": None, "primary_email": None}
    def detect_cdn(url): return {"has_cdn": False, "cdn_name": None, "is_hot_lead": True}

# ─── Preview Measurement API ──────────────────────────────────────────────────
try:
    from preview_api import run_preview_measurement, render_preview_results, get_preview_api_key
    PREVIEW_API_AVAILABLE = True
except ImportError:
    PREVIEW_API_AVAILABLE = False
    def get_preview_api_key(): return None

# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
_CMS_COLORS: dict[str, tuple[str, str]] = {
    "WordPress": ("#21759B", "#21759B18"), "Shopify": ("#5E8E3E", "#96BF4818"),
    "Wix": ("#B07D00", "#FAAD1418"), "Squarespace": ("#333333", "#33333318"),
    "Webflow": ("#2D3AC0", "#4353FF18"), "Joomla": ("#C03D1E", "#F44E2718"),
    "Drupal": ("#0678BE", "#0678BE18"), "Magento": ("#C24E12", "#EE672218"),
    "Ghost": ("#738A94", "#738A9418"), "PrestaShop": ("#DF0067", "#DF006718"),
    "Next.js": ("#000000", "#00000015"), "Nuxt.js": ("#00C58E", "#00C58E18"),
    "Gatsby": ("#663399", "#66339918"), "HubSpot CMS": ("#FF7A59", "#FF7A5918"),
    "Framer": ("#0099FF", "#0099FF18"), "BigCommerce": ("#34313F", "#34313F18"),
    "Unknown": ("#888888", "#88888815"),
}

def _cms_badge(cms: str, confidence: str | None = None) -> str:
    fg, bg = _CMS_COLORS.get(cms, ("#888888", "#88888815"))
    conf_icon = {"high": " ✓", "medium": " ~", "low": " "}.get(confidence or "", "")
    return (
        f'<span class="fs-tag cms" style="background:{bg};color:{fg};'
        f'border:1px solid {fg}55;font-weight:700;">{cms}{conf_icon}</span>'
    )

def _score_color(s):
    return "#2E7D32" if s >= 75 else ("#F57F17" if s >= 50 else "#C62828")

def _render_tech_badges(t: dict) -> str:
    cms  = t.get("cms", "Unknown")
    conf = t.get("cms_confidence")
    if cms == "Unknown":
        cms, conf = _resolve_unknown_cms(t)
    if cms == "Unknown":
        cms_html = '<span class="fs-tag">CMS not detected</span>'
    else:
        cms_html = _cms_badge(cms, conf)
    plug_html = " ".join(
        f'<span class="fs-tag cms">{p}</span>'
        for p in t.get("plugins", [])[:8]
    )
    svr_txt = t.get("server", "")
    svr = (
        f'<span class="fs-tag">🖥 {svr_txt[:30]}</span>'
        if svr_txt else ""
    )
    err_txt = t.get("error", "")
    err = (
        f'<span class="tech-badge" style="background:#ff000015;color:#c00;border:1px solid #ff000044;">⚠ {err_txt[:40]}</span>'
        if err_txt else ""
    )
    return cms_html + " " + plug_html + " " + svr + " " + err

# ─────────────────────────────────────────────────────────────────────────────
# REP LOGIN / IDENTITY GATE
# ─────────────────────────────────────────────────────────────────────────────
# Minimal access control: an optional shared team password (set TEAM_PASSWORD
# in secrets.toml to require it) plus a mandatory rep name, so anyone using
# the tool is identified and every email/PDF/CSV is branded with their name.
_TEAM_PASSWORD = _get_secret("TEAM_PASSWORD")

if "_authenticated" not in st.session_state:
    st.session_state["_authenticated"] = not bool(_TEAM_PASSWORD)
if "rep_name" not in st.session_state:
    st.session_state["rep_name"] = ""

if not st.session_state["_authenticated"] or not st.session_state["rep_name"]:
    st.markdown(f"""
<div style="max-width:420px;margin:6rem auto 1rem auto;text-align:center;">
  <div style="font-size:2.2rem;">⚡</div>
  <h1 style="margin-bottom:0;">fast.site — Lead Finder</h1>
  <p style="color:#94A3B8;font-size:0.9rem;">{_t('Sign in to continue', 'Anmelden, um fortzufahren')}</p>
</div>
""", unsafe_allow_html=True)
    _form_col1, _form_col2, _form_col3 = st.columns([1, 1.4, 1])
    with _form_col2:
        with st.form("rep_login_form"):
            _rep_name_input = st.text_input(
                _t("Your name", "Ihr Name"),
                value=st.session_state.get("rep_name", ""),
                placeholder=_t("e.g. Alex Carter", "z. B. Alex Carter"),
            )
            _pwd_input = ""
            if _TEAM_PASSWORD:
                _pwd_input = st.text_input(_t("Team password", "Team-Passwort"), type="password")
            _submitted = st.form_submit_button(_t("Continue", "Weiter"), use_container_width=True, type="primary")
        if _submitted:
            if not _rep_name_input.strip():
                st.error(_t("Please enter your name.", "Bitte geben Sie Ihren Namen ein."))
            elif _TEAM_PASSWORD and _pwd_input != _TEAM_PASSWORD:
                st.error(_t("Incorrect team password.", "Falsches Team-Passwort."))
            else:
                st.session_state["rep_name"]       = _rep_name_input.strip()
                st.session_state["_authenticated"] = True
                st.rerun()

    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────
if "nav_mode" not in st.session_state:
    st.session_state["nav_mode"] = "search"   # "search" | "direct"

with st.sidebar:
    # Logo / Brand
    st.markdown("""
<div class="sidebar-logo">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:36px;height:36px;background:linear-gradient(135deg,#2563EB,#1D4ED8);
      border-radius:9px;display:flex;align-items:center;justify-content:center;
      font-size:18px;flex-shrink:0;box-shadow:0 3px 10px rgba(37,99,235,0.4);">⚡</div>
    <div>
      <div style="font-size:1.05rem;font-weight:800;color:#fff;line-height:1.1;">fast.site</div>
      <div style="font-size:0.72rem;color:rgba(255,255,255,0.45);font-weight:500;">Lead Finder</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Navigation
    st.markdown('<div class="sidebar-section-label">Find Leads</div>', unsafe_allow_html=True)

    _nm = st.session_state.get("nav_mode", "search")
    if st.button("🔍  Search Businesses", key="nav_search", use_container_width=True,
                 type="primary" if _nm == "search" else "secondary"):
        if _nm != "search":
            for k in ["audits","results","engines","tech","direct_tech","direct_tech_skipped","direct_url_ready","selected_for_audit","_select_action"]:
                st.session_state.pop(k, None)
        st.session_state["nav_mode"] = "search"
        st.rerun()

    if st.button("🌐  Audit a Website", key="nav_direct", use_container_width=True,
                 type="primary" if _nm == "direct" else "secondary"):
        if _nm != "direct":
            for k in ["audits","results","engines","tech","direct_tech","direct_tech_skipped","direct_url_ready","selected_for_audit","_select_action"]:
                st.session_state.pop(k, None)
        st.session_state["nav_mode"] = "direct"
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="sidebar-section-label">Export</div>', unsafe_allow_html=True)
    if st.button("📤  Export & Reports", key="nav_exports_sb", use_container_width=True):
        st.session_state["goto_tab"] = 2
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="sidebar-section-label">Account</div>', unsafe_allow_html=True)

    # Signed-in user
    rep = st.session_state.get("rep_name", "")
    st.markdown(f"""
<div class="sidebar-user-info">
  <div style="font-size:0.7rem;color:rgba(255,255,255,0.4);font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;">Signed in as</div>
  <div style="font-size:0.88rem;font-weight:700;color:#fff;">👤 {rep}</div>
</div>
""", unsafe_allow_html=True)

    # Language switch
    _other_lang = "🇩🇪  Deutsch" if _LANG == "en" else "🇬🇧  English"
    if st.button(_other_lang, key="lang_switch_sb", use_container_width=True):
        st.session_state["lang"] = "de" if _LANG == "en" else "en"
        for k in ["audits","results","engines","tech","direct_tech","direct_tech_skipped","direct_url_ready","selected_for_audit","_select_action"]:
            st.session_state.pop(k, None)
        st.rerun()

    if st.button(f"🚪  {_t('Log out','Abmelden')}", key="logout_sb", use_container_width=True):
        for k in list(st.session_state.keys()):
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("---")
    st.markdown(f"""
<div style="padding:0.5rem 0.9rem;font-size:0.72rem;color:rgba(255,255,255,0.28);line-height:1.7;">
  ⚡ fast.site &nbsp;·&nbsp; Lead Finder<br>
  {_t("Find, audit & contact slow websites","Langsame Websites finden & kontaktieren")}
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TABS NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────

# Tab CSS styling
st.markdown("""
<style>
/* ── Tab bar styling (light theme) ───────────────────────────────────── */
[data-testid="stTabs"] > div:first-child {
    background: #FFFFFF !important;
    border-radius: 14px 14px 0 0 !important;
    border: 1px solid #E2E8F4 !important;
    border-bottom: none !important;
    padding: 0 8px !important;
    margin-bottom: 0 !important;
}
[data-testid="stTabs"] [role="tab"] {
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    color: #64748B !important;
    padding: 0.85rem 1.5rem !important;
    border-radius: 10px 10px 0 0 !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
    color: #2563EB !important;
    background: #EFF6FF !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #1D4ED8 !important;
    background: #EFF6FF !important;
    border-bottom: 3px solid #2563EB !important;
}
[data-testid="stTabsContent"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F4 !important;
    border-top: none !important;
    border-radius: 0 0 14px 14px !important;
    padding: 1.5rem 1.75rem !important;
    margin-bottom: 1.5rem !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.06) !important;
}
</style>
""", unsafe_allow_html=True)

# App header
st.markdown(f"""
<div style="background:linear-gradient(135deg,#2563EB 0%,#1E40AF 100%);
  color:white;padding:18px 24px;border-radius:14px;margin-bottom:1rem;
  box-shadow:0 6px 24px rgba(37,99,235,0.22);display:flex;align-items:center;gap:14px;">
  <div style="font-size:2rem;">⚡</div>
  <div>
    <div style="font-size:1.35rem;font-weight:800;color:#fff;margin-bottom:2px;">fast.site — Lead Finder</div>
    <div style="font-size:0.82rem;color:rgba(255,255,255,0.75);">{_t('Find slow websites · Extract contacts · Generate cold emails · Export leads','Langsame Websites finden · Kontakte · Kalt-E-Mails · Leads exportieren')}</div>
  </div>
  <div style="margin-left:auto;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);
    border-radius:99px;padding:4px 14px;font-size:0.75rem;font-weight:600;color:rgba(255,255,255,0.9);">
    👤 {st.session_state.get('rep_name','—')}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tab switching via JS injection ───────────────────────────────────────────
# session_state["goto_tab"] = 0/1/2 triggers a JS click on that tab button
if "goto_tab" not in st.session_state:
    st.session_state["goto_tab"] = 0

_goto = st.session_state.get("goto_tab", 0)
import streamlit.components.v1 as _tab_js_comp
_tab_js_comp.html(f"""
<script>
(function() {{
  var idx = {_goto};
  function clickTab() {{
    var tabs = window.parent.document.querySelectorAll('[data-testid="stTabs"] [role="tab"]');
    if (tabs.length > idx) {{
      tabs[idx].click();
      return true;
    }}
    return false;
  }}
  // Try immediately and with retries for Streamlit's deferred render
  if (!clickTab()) {{
    setTimeout(clickTab, 150);
    setTimeout(clickTab, 400);
  }}
}})();
</script>
""", height=0, scrolling=False)
# Reset so subsequent reruns don't keep re-clicking
st.session_state["goto_tab"] = 0

# ── 3-tab layout ─────────────────────────────────────────────────────────────
_tab_labels = [
    f"🔍 {_t('Search Businesses', 'Unternehmen suchen')}",
    f"📊 {_t('Check Results', 'Prüfergebnisse')}",
    f"⬇ {_t('Exports & PDFs', 'Export & PDFs')}",
]
tab1, tab2, tab3 = st.tabs(_tab_labels)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: SEARCH BUSINESSES
# ─────────────────────────────────────────────────────────────────────────────
with tab1:

    # ── Direct URL mode toggle ────────────────────────────────────────────────
    _nm = st.session_state.get("nav_mode", "search")
    mode_col1, mode_col2 = st.columns(2)
    with mode_col1:
        if st.button(f"🔍 {_t('Search Businesses', 'Unternehmen suchen')}",
                     use_container_width=True,
                     type="primary" if _nm == "search" else "secondary",
                     key="tab_nav_search"):
            if _nm != "search":
                for k in ["audits","results","engines","tech","direct_tech",
                          "direct_tech_skipped","direct_url_ready","selected_for_audit","_select_action"]:
                    st.session_state.pop(k, None)
            st.session_state["nav_mode"] = "search"
            st.rerun()
    with mode_col2:
        if st.button(f"🌐 {_t('Audit a Website Directly', 'Website direkt prüfen')}",
                     use_container_width=True,
                     type="primary" if _nm == "direct" else "secondary",
                     key="tab_nav_direct"):
            if _nm != "direct":
                for k in ["audits","results","engines","tech","direct_tech",
                          "direct_tech_skipped","direct_url_ready","selected_for_audit","_select_action"]:
                    st.session_state.pop(k, None)
            st.session_state["nav_mode"] = "direct"
            st.rerun()

    is_direct_mode = st.session_state.get("nav_mode", "search") == "direct"

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # ── MODE A: Direct URL Audit ──────────────────────────────────────────────
    if is_direct_mode:

        # ── Progress tracker — always visible above the URL input ─────────────
        _pre_ready   = st.session_state.get("direct_url_ready", "")
        _pre_tech    = st.session_state.get("direct_tech", {})
        _pre_s1 = bool(_pre_ready)
        _pre_s2 = _pre_s1 and _pre_ready in _pre_tech
        _pre_s3 = _pre_s1 and _pre_ready in st.session_state.get("audits", {})
        _pre_s4 = _pre_s1 and _pre_ready in st.session_state.get("contacts", {})
        _pre_steps = [
            (_t("URL Submitted",      "URL eingereicht"),        _pre_s1),
            (_t("Tech Stack Scanned", "Tech-Stack gescannt"),    _pre_s2),
            (_t("Speed Checked",      "Geschwindigkeit geprüft"),_pre_s3),
            (_t("Contacts Found",     "Kontakte gefunden"),      _pre_s4),
        ]
        _pre_html = ""
        for i, (label, done) in enumerate(_pre_steps, start=1):
            _next_active = next((j for j, (_, d) in enumerate(_pre_steps, 1) if not d), 0)
            if done:
                bg, border, color, num_bg, icon = "rgba(5,150,105,0.10)", "rgba(16,185,129,0.35)", "#059669", "#10B981", "✓"
            elif i == _next_active:
                bg, border, color, num_bg, icon = "rgba(37,99,235,0.10)", "rgba(37,99,235,0.35)", "#2563EB", "#2563EB", str(i)
            else:
                bg, border, color, num_bg, icon = "#F8FAFF", "#E2E8F4", "#94A3B8", "#CBD5E1", str(i)
            _pre_html += (
                f'<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;'
                f'background:{bg};border:1.5px solid {border};border-radius:9px;'
                f'font-size:0.82rem;font-weight:600;color:{color};flex:1;">'
                f'<div style="width:22px;height:22px;border-radius:50%;background:{num_bg};color:#fff;'
                f'font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
                f'{icon}</div>{label}</div>'
            )
            if i < len(_pre_steps):
                _pre_html += '<div style="color:#CBD5E1;font-size:1.1rem;padding:0 4px;flex-shrink:0;">→</div>'
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:0;margin-bottom:1rem;">{_pre_html}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(f"""
<div class="search-card">
  <div style="font-size:1.05rem;font-weight:700;color:#0F172A;margin-bottom:0.6rem;">
    🌐 {_t('Audit a Website Directly', 'Website direkt prüfen')}
  </div>
  <p style="margin-bottom:0.75rem;color:#64748B;font-size:0.92rem;">
    {_t('Enter any website address to check its speed, technology and contact details.',
        'Webadresse eingeben, um Geschwindigkeit, Technologie und Kontaktdaten zu prüfen.')}
  </p>
""", unsafe_allow_html=True)
        url_col, btn_col = st.columns([4, 1])
        with url_col:
            direct_url = st.text_input(
                _t("Website address", "Webadresse"),
                placeholder="https://example.com",
                label_visibility="collapsed",
                key="direct_url_input",
            )
        with btn_col:
            direct_go_btn = st.button(
                f"🚀 {_t('Check Website', 'Website prüfen')}",
                type="primary",
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        if direct_go_btn:
            raw = direct_url.strip()
            if not raw:
                st.warning(_t("Please paste a website address first.", "Bitte geben Sie zuerst eine Webadresse ein."))
            elif not _is_valid_url(raw):
                st.error(_t(
                    "That doesn't look like a valid website address. "
                    "Please enter a real URL, e.g. **example.com** or **https://example.com**.",
                    "Das sieht nicht wie eine gültige Webadresse aus. "
                    "Bitte geben Sie eine echte URL ein, z.B. **beispiel.de** oder **https://beispiel.de**.",
                ))
            else:
                if not raw.startswith(("http://", "https://")):
                    raw = "https://" + raw
                st.session_state["direct_url_ready"] = raw
                st.session_state.pop("direct_tech", None)
                st.session_state.pop("direct_tech_skipped", None)
                st.session_state.pop("audits", None)
                st.session_state.pop("results", None)
                st.session_state.get("contacts", {}).pop(raw, None)

                def _live_tracker(s1=False, s2=False, s3=False, s4=False, active_step=0):
                    _lt_steps = [
                        (_t("URL Submitted",      "URL eingereicht"),        s1),
                        (_t("Tech Stack Scanned", "Tech-Stack gescannt"),    s2),
                        (_t("Speed Checked",      "Geschwindigkeit geprüft"),s3),
                        (_t("Contacts Found",     "Kontakte gefunden"),      s4),
                    ]
                    _lt_html = ""
                    for i, (label, done) in enumerate(_lt_steps, start=1):
                        is_active = (active_step == i)
                        if done:
                            bg, border, color, num_bg, icon = "rgba(5,150,105,0.08)", "rgba(16,185,129,0.35)", "#059669", "#10B981", "✓"
                        elif is_active:
                            bg, border, color, num_bg, icon = "rgba(37,99,235,0.08)", "rgba(37,99,235,0.35)", "#2563EB", "#2563EB", "⋯"
                        else:
                            bg, border, color, num_bg, icon = "#F8FAFF", "#E2E8F4", "#94A3B8", "#CBD5E1", str(i)
                        _lt_html += (
                            f'<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;'
                            f'background:{bg};border:1px solid {border};border-radius:8px;'
                            f'font-size:0.82rem;font-weight:600;color:{color};flex:1;">'
                            f'<div style="width:22px;height:22px;border-radius:50%;background:{num_bg};color:#fff;'
                            f'font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
                            f'{icon}</div>{label}</div>'
                        )
                        if i < len(_lt_steps):
                            _lt_html += '<div style="color:#CBD5E1;font-size:1.1rem;padding:0 4px;flex-shrink:0;">→</div>'
                    return f'<div style="display:flex;align-items:center;gap:0;margin:1rem 0;">{_lt_html}</div>'

                _live_ph  = st.empty()
                _live_msg = st.empty()
                _live_ph.markdown(_live_tracker(s1=True, active_step=2), unsafe_allow_html=True)
                _live_msg.info(f"🧪 {_t('Detecting tech stack...', 'Tech-Stack wird ermittelt...')}")
                st.session_state["direct_tech"] = {raw: detect_tech(raw)}
                _live_ph.markdown(_live_tracker(s1=True, s2=True, active_step=2), unsafe_allow_html=True)
                _live_msg.success(f"✅ {_t('Tech stack detected!', 'Tech-Stack erkannt!')}")
                time.sleep(0.7)
                _live_ph.markdown(_live_tracker(s1=True, s2=True, active_step=3), unsafe_allow_html=True)
                _live_msg.info(f"🚀 {_t('Auditing site speed & performance...', 'Geschwindigkeit & Performance werden geprüft...')}")
                result = audit_website(raw)
                cdn_map = st.session_state.get("cdn_map", {})
                cdn_map[raw] = detect_cdn(raw)
                st.session_state["cdn_map"] = cdn_map
                st.session_state["audits"] = {raw: result}
                if CONTACT_AVAILABLE:
                    _live_ph.markdown(_live_tracker(s1=True, s2=True, s3=True, active_step=4), unsafe_allow_html=True)
                    _live_msg.info(f"📧 {_t('Extracting contact info...', 'Kontaktdaten werden extrahiert...')}")
                    st.session_state.setdefault("contacts", {})[raw] = extract_contact_info(raw)
                    st.session_state["_contact_auto_extracted"] = raw
                _live_ph.markdown(_live_tracker(s1=True, s2=True, s3=True, s4=True), unsafe_allow_html=True)
                _live_msg.success(f"✅ {_t('All done! Go to Check Results tab.', 'Fertig! Prüfergebnisse-Tab öffnen.')}")
                time.sleep(0.8)
                _live_ph.empty()
                _live_msg.empty()
                st.rerun()

        ready_url = st.session_state.get("direct_url_ready", "")
        if ready_url:
            direct_tech      = st.session_state.get("direct_tech", {})
            already_detected = ready_url in direct_tech
            _step3_done = ready_url in st.session_state.get("audits", {})
            _step4_done = ready_url in st.session_state.get("contacts", {})

            if already_detected:
                t = direct_tech[ready_url]
                st.markdown(
                    f"**{_t('Website platform', 'Website-Plattform')}:** " + _render_tech_badges(t),
                    unsafe_allow_html=True,
                )
            if _step3_done:
                st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
                _rc1, _rc2 = st.columns(2)
                with _rc1:
                    if st.button(f"📊 {_t('View Results', 'Ergebnisse ansehen')}", use_container_width=True, type="primary"):
                        st.session_state["goto_tab"] = 1
                        st.rerun()
                with _rc2:
                    if st.button(f"🔄 {_t('Check again', 'Erneut prüfen')}", use_container_width=True):
                        st.session_state.setdefault("audits", {}).pop(ready_url, None)
                        st.session_state.get("contacts", {}).pop(ready_url, None)
                        st.rerun()

    # ── MODE B: Search Businesses ─────────────────────────────────────────────
    else:
        _has_results  = bool(st.session_state.get("results"))
        _has_selected = bool(st.session_state.get("selected_for_audit"))
        _has_audits   = bool(st.session_state.get("audits"))
        _steps = [
            (_t("Find Businesses", "Unternehmen finden"), "done" if _has_results else "active"),
            (_t("Select Sites", "Seiten auswählen"), "done" if _has_selected else ("active" if _has_results else "")),
            (_t("Run Speed Checks", "Geschwindigkeit prüfen"), "done" if _has_audits else ("active" if _has_selected else "")),
            (_t("View Results", "Ergebnisse ansehen"), "active" if _has_audits else ""),
        ]
        _steps_html = ""
        for i, (label, state) in enumerate(_steps, start=1):
            if state == "done":
                bg, border, color, num_bg = "#DCFCE7", "#86EFAC", "#166534", "#16A34A"
                icon = "✓"
            elif state == "active":
                bg, border, color, num_bg = "#EFF6FF", "#93C5FD", "#1D4ED8", "#2563EB"
                icon = str(i)
            else:
                bg, border, color, num_bg = "#F8FAFF", "#E2E8F4", "#94A3B8", "#CBD5E1"
                icon = str(i)
            _steps_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:10px 14px;'
                f'background:{bg};border:1.5px solid {border};border-radius:8px;'
                f'font-size:0.82rem;font-weight:600;color:{color};flex:1;">'
                f'<div style="width:22px;height:22px;border-radius:50%;background:{num_bg};color:#fff;'
                f'font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
                f'{icon}</div>{label}</div>'
            )
            if i < len(_steps):
                _steps_html += '<div style="color:#CBD5E1;font-size:1rem;padding:0 2px;flex-shrink:0;">→</div>'
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:4px;margin-bottom:1rem;">{_steps_html}</div>',
            unsafe_allow_html=True,
        )

        # ── Step 1 card: Search Parameters ───────────────────────────────────
        st.markdown(f"""
<div class="result-card" style="padding:1.25rem 1.5rem;margin-bottom:0.75rem;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.9rem;">
    <span style="font-size:1rem;">🔍</span>
    <span style="font-size:0.95rem;font-weight:700;color:#0F172A;">{_t('Step 1 — Search Parameters','Schritt 1 — Suchparameter')}</span>
  </div>
""", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2.5, 2.5, 1])
        with col1:
            industry = st.text_input(
                _t("Type of business", "Art des Unternehmens"),
                placeholder=_t("e.g. restaurants, dentists, gyms", "z.B. Restaurants, Zahnärzte, Fitnessstudios"),
            )
        with col2:
            area_query = st.text_input(
                _t("City or country", "Stadt oder Land"),
                value=st.session_state.get("area_picked", ""),
                placeholder=_t("e.g. Berlin, Germany, Dubai", "z.B. Berlin, Deutschland, Dubai"),
                key="area_query_input",
            )
            area = area_query
        with col3:
            max_results = st.number_input(_t("How many?", "Wie viele?"), 1, 50, 15)

        search_btn = st.button(
            f"🔍 {_t('Find Businesses', 'Unternehmen finden')}",
            type="primary",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if search_btn:
            if not industry or not area:
                st.warning(_t("Please fill in both fields — type of business and city/country.",
                              "Bitte füllen Sie beide Felder aus — Unternehmensart und Stadt/Land."))
            else:
                status = st.empty()
                with st.spinner(_t("Searching the web for matching businesses…",
                                   "Suche im Web nach passenden Unternehmen…")):
                    results, engines = multi_engine_search(industry, area, int(max_results))
                st.session_state["results"]            = results
                st.session_state["engines"]            = engines
                st.session_state["tech"]               = {}
                st.session_state["audits"]             = {}
                st.session_state["selected_for_audit"] = []
                st.session_state.pop("direct_url_ready", None)
                status.empty()

        # ── Show search results if available ──────────────────────────────────
        if "results" in st.session_state and not st.session_state["results"]:
            engines = st.session_state.get("engines", [])
            engine_note = f" ({', '.join(engines)})" if engines and engines != ["None"] else ""
            st.markdown(f"""
<div class="result-card" style="padding:2.5rem;text-align:center;">
  <div style="font-size:2.5rem;margin-bottom:0.75rem;">🔍</div>
  <div style="font-size:1rem;font-weight:700;color:#0F172A;margin-bottom:0.4rem;">
    {_t("No businesses found","Keine Unternehmen gefunden")}
  </div>
  <div style="font-size:0.86rem;color:#64748B;max-width:380px;margin:0 auto;line-height:1.65;">
    {_t(f"We searched{engine_note} but couldn't find any matching business websites. Try a broader category, a larger city, or a different spelling.",
        f"Wir haben{engine_note} gesucht, aber keine passenden Websites gefunden.")}
  </div>
</div>
""", unsafe_allow_html=True)

        if "results" in st.session_state and st.session_state["results"]:
            results = st.session_state["results"]
            engines = st.session_state["engines"]

            # ── Auto-detect tech stack ────────────────────────────────────────
            all_result_urls = [item.get("source_url", "") for item in results if item.get("source_url")]
            _tech_cache_key = "_tech_cache_urls"
            if st.session_state.get(_tech_cache_key) != all_result_urls:
                # ── Step 2 banner: visible "Detecting Technology Stack" indicator ──
                _step2_ph = st.empty()
                _step2_ph.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:14px 18px;'
                    f'background:rgba(37,99,235,0.07);border:1.5px solid rgba(37,99,235,0.35);'
                    f'border-radius:10px;margin-bottom:0.75rem;">'
                    f'<div style="width:28px;height:28px;border-radius:50%;background:#2563EB;color:#fff;'
                    f'font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;">2</div>'
                    f'<div>'
                    f'<div style="font-size:0.85rem;font-weight:700;color:#2563EB;">'
                    f'🧪 {_t("Step 2 — Detecting Technology Stack…", "Schritt 2 — Tech-Stack wird ermittelt…")}</div>'
                    f'<div style="font-size:0.75rem;color:#64748B;margin-top:2px;">'
                    f'{_t("Scanning each site for CMS, plugins and CDN…", "Jede Website wird auf CMS und CDN geprüft…")}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                prog   = st.progress(0)
                status = st.empty()
                tech   = {}
                cdn_map = {}
                total = len(all_result_urls) or 1
                for i, url in enumerate(all_result_urls):
                    status.caption(f"🔍 {url}")
                    tech[url]    = detect_tech(url)
                    cdn_map[url] = detect_cdn(url)
                    prog.progress((i + 1) / total)
                st.session_state["tech"]    = tech
                st.session_state["cdn_map"] = cdn_map
                st.session_state[_tech_cache_key] = all_result_urls
                prog.empty()
                status.empty()
                _step2_ph.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:14px 18px;'
                    f'background:rgba(5,150,105,0.07);border:1.5px solid rgba(16,185,129,0.35);'
                    f'border-radius:10px;margin-bottom:0.75rem;">'
                    f'<div style="width:28px;height:28px;border-radius:50%;background:#10B981;color:#fff;'
                    f'font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;">✓</div>'
                    f'<div style="font-size:0.85rem;font-weight:700;color:#059669;">'
                    f'✅ {_t("Technology Stack Detected — select sites below to audit", "Tech-Stack erkannt — Seiten auswählen und prüfen")}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )


            tech    = st.session_state.get("tech", {})
            cdn_map = st.session_state.get("cdn_map", {})

            if "selected_for_audit" not in st.session_state:
                st.session_state["selected_for_audit"] = []

            all_urls = [item.get("source_url", "") for item in results if item.get("source_url")]
            if "_select_action" not in st.session_state:
                st.session_state["_select_action"] = None

            # ── Results header: count + Select All / Clear ────────────────────
            _res_left, _res_right = st.columns([1, 1])
            with _res_left:
                _n_sel = len(st.session_state["selected_for_audit"])
                st.markdown(
                    f'<div style="font-size:0.9rem;font-weight:600;color:#64748B;padding:0.6rem 0;">'
                    f'<span style="font-weight:800;color:#2563EB;">{len(results)}</span> '
                    f'{_t("businesses found","Unternehmen gefunden")}'
                    f'{f" · <span style=\'color:#2563EB;\'>{_n_sel} selected</span>" if _n_sel else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _res_right:
                _sa_col, _cl_col = st.columns(2)
                with _sa_col:
                    if st.button(f"☑ {_t('Select All','Alle auswählen')}", use_container_width=True):
                        st.session_state["selected_for_audit"] = list(all_urls)
                        st.session_state["_select_action"] = "all"
                        st.rerun()
                with _cl_col:
                    if st.button(f"☐ {_t('Clear','Aufheben')}", use_container_width=True):
                        st.session_state["selected_for_audit"] = []
                        st.session_state["_select_action"] = "none"
                        st.rerun()

            selected = st.session_state["selected_for_audit"]

            # ── Individual result cards ───────────────────────────────────────
            for idx, item in enumerate(results):
                url  = item.get("source_url", "")
                name = item.get("business_name", url)
                t    = tech.get(url, {})
                cdn  = cdn_map.get(url, {})
                already_audited = url in st.session_state.get("audits", {})
                action_suffix = st.session_state.get("_select_action", "")
                _card_key = f"leadcard_{idx}_{action_suffix}"

                _cdn_has  = cdn.get("has_cdn", False) if cdn else None
                _cdn_name = cdn.get("cdn_name", "CDN") if cdn else ""
                _cms      = t.get("cms", "Unknown") if t else "Unknown"
                _plugins  = t.get("plugins", []) if t else []
                if _cms == "Unknown" and t:
                    _cms, _ = _resolve_unknown_cms(t)

                # Tech pill badges
                _tech_pills = ""
                if _cms and _cms not in ("Unknown", ""):
                    _fg, _bg = _CMS_COLORS.get(_cms, ("#475569", "#F1F5F9"))
                    _tech_pills += (
                        f'<span style="background:{_bg};color:{_fg};border:1px solid {_fg}33;'
                        f'padding:2px 8px;border-radius:5px;font-size:11px;font-weight:700;margin-right:4px;">'
                        f'{_cms}</span>'
                    )
                for _p in _plugins[:4]:
                    _tech_pills += (
                        f'<span style="background:#EDE9FE;color:#6D28D9;border:1px solid #C4B5FD;'
                        f'padding:2px 8px;border-radius:5px;font-size:11px;font-weight:600;margin-right:4px;">'
                        f'{_p}</span>'
                    )

                # Right-side: opportunity + speed score if already audited
                _right_html = ""
                if already_audited:
                    _a = st.session_state.get("audits", {}).get(url, {})
                    _cdn_i = st.session_state.get("cdn_map", {}).get(url, {})
                    _opp = varnish_opportunity_score(_a, cdn_info=_cdn_i)
                    _lbl, _ocol = opportunity_label(_opp)
                    _spd = (_a.get("breakdown") or {}).get("speed", {}).get("score", "—")
                    _right_html = (
                        f'<div style="text-align:right;">'
                        f'<span style="background:{_ocol}18;color:{_ocol};border:1px solid {_ocol}33;'
                        f'padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;">⚡ {_lbl} · {_opp}/100</span>'
                        f'<div style="font-size:0.72rem;color:#64748B;margin-top:6px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">'
                        f'Speed Score</div>'
                        f'<div style="font-size:1.4rem;font-weight:800;color:{_score_color(_spd) if isinstance(_spd,int) else "#0F172A"};">'
                        f'{_spd}<span style="font-size:0.75rem;color:#94A3B8;font-weight:500;">/100</span></div>'
                        f'</div>'
                    )
                elif _cdn_has is False:
                    _right_html = (
                        f'<div style="text-align:right;">'
                        f'<span style="background:#FEF3C7;color:#92400E;border:1px solid #FDE68A;'
                        f'padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;">🔥 Hot Lead — No CDN</span>'
                        f'</div>'
                    )

                _domain_display = url.replace("https://","").replace("http://","").rstrip("/")
                _contacted_info = st.session_state.get("contacted", {}).get(url)

                st.markdown(f"""
<style>
div[class*="st-key-{_card_key}"] {{
    background:#FFFFFF !important;
    border:1px solid #E2E8F4 !important;
    border-radius:10px !important;
    box-shadow:0 1px 4px rgba(15,23,42,0.05) !important;
    padding:12px 16px !important;
    margin-bottom:8px !important;
}}
</style>
""", unsafe_allow_html=True)

                with st.container(key=_card_key):
                    chk_col, info_col, right_col, btn_col = st.columns([0.4, 5.5, 2.5, 1.5])
                    with chk_col:
                        checked = st.checkbox(
                            f"Select {name}", value=(url in selected),
                            key=f"chk_{idx}_{action_suffix}", label_visibility="collapsed",
                        )
                        if checked and url not in selected:
                            selected.append(url)
                            st.session_state["selected_for_audit"] = selected
                            st.session_state["_select_action"] = None
                        elif not checked and url in selected:
                            selected.remove(url)
                            st.session_state["selected_for_audit"] = selected
                            st.session_state["_select_action"] = None
                    with info_col:
                        _badges = ""
                        if already_audited:
                            _badges += '<span style="background:#DCFCE7;color:#166534;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;margin-left:6px;">✓ Audited</span>'
                        if _contacted_info:
                            _badges += '<span style="background:#DBEAFE;color:#1E40AF;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;margin-left:4px;">✅ Contacted</span>'
                        st.markdown(
                            f'<div style="font-size:0.93rem;font-weight:700;color:#0F172A;line-height:1.4;">'
                            f'{name}{_badges}</div>'
                            f'<div style="font-size:0.78rem;color:#2563EB;margin-top:2px;">{_domain_display}</div>'
                            f'<div style="margin-top:6px;line-height:2.2;">{_tech_pills}</div>',
                            unsafe_allow_html=True,
                        )
                    with right_col:
                        if _right_html:
                            st.markdown(_right_html, unsafe_allow_html=True)
                    with btn_col:
                        if already_audited:
                            if st.button(f"📊 {_t('View','Ansehen')}", key=f"view_{idx}", use_container_width=True, type="primary"):
                                st.session_state["goto_tab"] = 1
                                st.rerun()
                            if st.button(f"🔄 {_t('Re-check','Neu prüfen')}", key=f"recheck_{idx}", use_container_width=True):
                                st.session_state.setdefault("audits", {}).pop(url, None)
                                st.rerun()
                        else:
                            if st.button(f"🔍 {_t('Check','Prüfen')}", key=f"audit1_{idx}", use_container_width=True, type="primary"):
                                with st.spinner(f"{_t('Checking','Prüfe')} {url}…"):
                                    result = audit_website(url)
                                    cdn_m = st.session_state.get("cdn_map", {})
                                    cdn_m[url] = detect_cdn(url)
                                    st.session_state["cdn_map"] = cdn_m
                                    st.session_state.setdefault("audits", {})[url] = result
                                    if CONTACT_AVAILABLE and url not in st.session_state.get("contacts", {}):
                                        st.session_state.setdefault("contacts", {})[url] = extract_contact_info(url)
                                st.rerun()

            # ── Step 3: Bulk check card ───────────────────────────────────────
            st.markdown("<div style='height:0.25rem;'></div>", unsafe_allow_html=True)
            selected = st.session_state["selected_for_audit"]
            not_yet  = [u for u in selected if u not in st.session_state.get("audits", {})]

            st.markdown(f"""
<div class="result-card" style="padding:1.25rem 1.5rem;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.5rem;">
    <span style="font-size:1rem;">🚀</span>
    <span style="font-size:0.95rem;font-weight:700;color:#0F172A;">{_t('Step 3 — Run Speed Checks','Schritt 3 — Geschwindigkeitsprüfung')}</span>
  </div>
  <div style="font-size:0.85rem;color:#64748B;margin-bottom:0.85rem;">
    {_t('Tick the boxes next to businesses above, then run all speed audits at once.','Häkchen setzen, dann alle Speed-Audits auf einmal starten.')}
  </div>
""", unsafe_allow_html=True)
            _btn_label = (
                f"🚀 {_t('Check','Prüfe')} {len(not_yet)} {_t('website','Website') if len(not_yet)==1 else _t('websites','Websites')}"
                if not_yet else
                f"✅ {_t('All selected sites already checked!','Alle ausgewählten Seiten bereits geprüft!')}"
            )
            check_btn = st.button(
                _btn_label,
                type="primary",
                disabled=(not not_yet or not selected),
            )
            st.markdown("</div>", unsafe_allow_html=True)

            if check_btn and not_yet:
                batch = not_yet
                prog   = st.progress(0)
                status = st.empty()
                _auto_contact_count = 0
                for i, url in enumerate(batch):
                    status.info(f"🔍 {_t('Checking','Prüfe')} {url}…")
                    result = audit_website(url)
                    cdn_map_b = st.session_state.get("cdn_map", {})
                    cdn_map_b[url] = detect_cdn(url)
                    st.session_state["cdn_map"] = cdn_map_b
                    st.session_state["audits"][url] = result
                    if CONTACT_AVAILABLE and url not in st.session_state.get("contacts", {}):
                        status.info(f"📧 {_t('Extracting contacts for','Kontakte werden abgerufen für')} {url}…")
                        st.session_state.setdefault("contacts", {})[url] = extract_contact_info(url)
                        _auto_contact_count += 1
                    prog.progress((i + 1) / len(batch), text=f"{_t('Done','Fertig')}: {i+1} / {len(batch)}")
                status.empty(); prog.empty()
                sites_done = len(batch)
                site_word  = _t("website","Website") if sites_done == 1 else _t("websites","Websites")
                st.success(f"✅ {_t('All done!','Alles fertig!')} {sites_done} {site_word} {_t('checked.','geprüft.')}")
                if _auto_contact_count:
                    st.info(f"📧 {_t('Auto-extracted contact info for','Kontakte automatisch extrahiert für')} {_auto_contact_count} {_t('sites.','Seiten.')}")
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: CHECK RESULTS
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    audits = st.session_state.get("audits", {})
    _direct_mode_results = audits and "results" not in st.session_state

    if not audits:
        st.markdown(f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F4;border-radius:14px;box-shadow:0 2px 12px rgba(15,23,42,0.06);
    padding:3rem 2.5rem;text-align:center;margin:1.5rem 0;">
  <div style="font-size:3rem;margin-bottom:1rem;">📊</div>
  <div style="font-size:1.15rem;font-weight:700;color:#0F172A;margin-bottom:0.5rem;">
    {_t("No audit results yet", "Noch keine Prüfergebnisse")}
  </div>
  <div style="font-size:0.9rem;color:#64748B;max-width:400px;margin:0 auto;">
    {_t("Go to the Search Businesses tab, find sites and click Check Websites to run audits.",
        "Gehen Sie zum Tab Unternehmen suchen, finden Sie Websites und klicken Sie auf Prüfen.")}
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div class="section-divider" style="margin-top:0.5rem;">
  <div class="section-divider-line"></div>
  <div class="section-divider-label">📊 {_t('Audit Results', 'Prüfergebnisse')}</div>
  <div class="section-divider-line"></div>
</div>
""", unsafe_allow_html=True)
        audit_list = list(audits.values())

        _auto_extracted_url = st.session_state.pop("_contact_auto_extracted", None)
        if _auto_extracted_url:
            _ae_contact = st.session_state.get("contacts", {}).get(_auto_extracted_url, {})
            _ae_email   = _ae_contact.get("primary_email")
            if _ae_email:
                st.success(f"📧 {_t('Contact info auto-extracted', 'Kontaktdaten automatisch extrahiert')} — **{_ae_email}**")
            else:
                st.info(f"📧 {_t('Contact extraction ran automatically — no email found.', 'Kontaktextraktion automatisch ausgeführt — keine E-Mail gefunden.')}")

        if not _direct_mode_results:
            successful = [a for a in audit_list if not a.get("error")]
            scores     = [a.get("overall_score", 0) for a in successful]
            _cdn_map_bulk = st.session_state.get("cdn_map", {})
            opps       = [varnish_opportunity_score(a, cdn_info=_cdn_map_bulk.get(a.get("url",""), {})) for a in successful]

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1: st.metric(_t("Sites Checked", "Geprüfte Seiten"), len(successful))
            with mc2: st.metric(_t("Avg Speed Score", "Ø Speed Score"), f"{int(sum(scores)/len(scores)) if scores else 0}/100")
            with mc3: st.metric(_t("Hot Leads", "Heiße Leads"), sum(1 for o in opps if o >= 65))
            with mc4: st.metric(_t("Avg Opportunity", "Ø Chance"), f"{int(sum(opps)/len(opps)) if opps else 0}/100")

            # Filters
            col_filter1, col_filter2, col_filter3 = st.columns([2, 1, 1])
            with col_filter1:
                hot_lead_only = st.checkbox(_t("Show only high-opportunity sites", "Nur hochopportune Seiten anzeigen"))
            with col_filter2:
                opp_threshold = st.slider(
                    _t("Min opportunity score", "Min. Opportunity Score"),
                    min_value=10, max_value=90, value=40, step=5,
                    disabled=not hot_lead_only,
                )
            with col_filter3:
                cdn_map_for_filter = st.session_state.get("cdn_map", {})
                cdn_filter_available = bool(cdn_map_for_filter)
                no_cdn_only = st.checkbox(
                    _t("🔥 No CDN only", "🔥 Nur ohne CDN"),
                    disabled=not cdn_filter_available,
                )

            filtered = audit_list
            if hot_lead_only:
                filtered = [
                    a for a in filtered
                    if (not a.get("error") and varnish_opportunity_score(a, cdn_info=cdn_map_for_filter.get(a.get("url",""), {})) >= opp_threshold)
                ]
            if no_cdn_only:
                filtered = [
                    a for a in filtered
                    if not a.get("error") and not cdn_map_for_filter.get(a.get("url", ""), {}).get("has_cdn")
                ]
        else:
            filtered = audit_list

        # ── Contact extraction state ──────────────────────────────────────────
        if "contacts" not in st.session_state:
            st.session_state["contacts"] = {}
        contacts = st.session_state["contacts"]

        if CONTACT_AVAILABLE:
            pending_contact = [
                a.get("url", "") for a in audit_list
                if not a.get("error") and a.get("url", "") not in contacts
            ]
            if pending_contact:
                with st.spinner(_t("Auto-extracting contact info…", "Kontaktdaten werden automatisch extrahiert…")):
                    for url_c in pending_contact:
                        contacts[url_c] = extract_contact_info(url_c)
                    st.session_state["contacts"] = contacts

        # ── Individual audit cards ────────────────────────────────────────────
        for a in filtered:
            url       = a.get("url", "")
            score     = a.get("overall_score", 0)
            bd        = a.get("breakdown", {})
            fetch_err = a.get("error", "")
            opp       = varnish_opportunity_score(a, cdn_info=st.session_state.get("cdn_map", {}).get(url, {})) if not fetch_err else 0
            opp_lbl, opp_col = opportunity_label(opp)
            proj      = a.get("fastsite_projection") or {}
            cur       = proj.get("current", {})
            prj_d     = proj.get("projected", {})
            spd_score = (bd.get("speed") or {}).get("score", 50)
            prf_score = (bd.get("performance") or {}).get("score", 50)
            _cdn_info = st.session_state.get("cdn_map", {}).get(url, {})
            _cdn_detected = _cdn_info.get("has_cdn")
            ttfb_now  = cur.get("ttfb_ms")
            ttfb_proj = prj_d.get("ttfb_ms")
            ps_min    = prj_d.get("perf_score_min")
            ps_max    = prj_d.get("perf_score_max")
            contact   = contacts.get(url, {})
            _is_contacted = url in st.session_state.get("contacted", {})

            # ── Outer card wrapper ────────────────────────────────────────────
            st.markdown(f"""
<div class="result-card" style="padding:0;margin-bottom:1.5rem;overflow:hidden;">

  <!-- Header row: badge + URL -->
  <div style="padding:1rem 1.5rem 0.75rem 1.5rem;border-bottom:1px solid #E2E8F4;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
      <span style="background:{'#DCFCE7' if not fetch_err else '#FEE2E2'};color:{'#166534' if not fetch_err else '#991B1B'};
        font-size:0.72rem;font-weight:700;padding:3px 10px;border-radius:99px;letter-spacing:0.05em;text-transform:uppercase;">
        {'✓ Audited' if not fetch_err else '⚠ Error'}
      </span>
      {'<span style="background:#FEF3C7;color:#92400E;font-size:0.72rem;font-weight:700;padding:3px 10px;border-radius:99px;letter-spacing:0.05em;text-transform:uppercase;">🔥 No CDN</span>' if not _cdn_detected and not fetch_err else ''}
      {'<span style="background:#DCFCE7;color:#166534;font-size:0.72rem;font-weight:700;padding:3px 10px;border-radius:99px;letter-spacing:0.05em;text-transform:uppercase;">✓ Contacted</span>' if _is_contacted else ''}
    </div>
    <div style="font-size:0.95rem;font-weight:600;color:#2563EB;">{_html_mod.escape(url)}</div>
  </div>
""", unsafe_allow_html=True)

            if fetch_err:
                st.markdown(f"""
  <div style="padding:1.25rem 1.5rem;">
    <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:1rem 1.25rem;color:#991B1B;font-size:0.9rem;">
      ❌ <strong>{_t('Could not audit this site.', 'Diese Website konnte nicht geprüft werden.')}</strong><br>
      <span style="color:#7F1D1D;">{fetch_err}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
                continue

            # ── 6-metric chip row ─────────────────────────────────────────────
            _safe_score = lambda v: v if not isinstance(v, dict) else "—"
            _spd_val  = _safe_score((bd.get("speed") or {}).get("score", "—"))
            _perf_val = _safe_score((bd.get("performance") or {}).get("score", "—"))
            _rank_val = _safe_score((bd.get("page_ranking") or {}).get("score", "—"))
            _server_ms = ttfb_now if ttfb_now else "—"
            _ps_val   = _safe_score((bd.get("pagespeed") or {}).get("score", _perf_val))
            _cache_type = _cdn_info.get("cdn_name") or "None"

            def _chip(val, label, color="#0F172A"):
                return (
                    f'<div style="flex:1;min-width:100px;background:#FFFFFF;border:1px solid #E2E8F4;'
                    f'border-radius:10px;padding:0.85rem 1rem;text-align:center;">'
                    f'<div style="font-size:1.6rem;font-weight:800;color:{color};line-height:1;">{val}</div>'
                    f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#94A3B8;margin-top:4px;">{label}</div>'
                    f'</div>'
                )

            _ttfb_color = "#DC2626" if (isinstance(ttfb_now, (int,float)) and ttfb_now > 800) else "#D97706" if (isinstance(ttfb_now, (int,float)) and ttfb_now > 300) else "#059669"
            _ttfb_disp  = f"{ttfb_now}<small style='font-size:0.8rem'>ms</small>" if isinstance(ttfb_now, (int,float)) else "—"
            _after_disp = f"~{ttfb_proj}<small style='font-size:0.8rem'>ms</small>" if ttfb_proj else "—"

            st.markdown(f"""
  <div style="display:flex;gap:8px;flex-wrap:wrap;padding:1rem 1.5rem;background:#F8FAFF;border-bottom:1px solid #E2E8F4;">
    {_chip(opp,        _t('Opportunity','Chance'),   opp_col)}
    {_chip(_spd_val,   _t('Speed Score','Speed Score'), _score_color(spd_score) if isinstance(_spd_val, int) else '#0F172A')}
    {_chip(_perf_val,  _t('Performance','Performance'), _score_color(prf_score) if isinstance(_perf_val, int) else '#0F172A')}
    {_chip(_ttfb_disp, _t('Server Response','Server Response'), _ttfb_color)}
    {_chip(_rank_val,  _t('PageSpeed','PageSpeed'),  _score_color(_rank_val) if isinstance(_rank_val, int) else '#0F172A')}
    {_chip(_cache_type,_t('Cache Type','Cache-Typ'),  '#059669' if _cdn_detected else '#DC2626')}
  </div>
""", unsafe_allow_html=True)

            # ── Speed alert bar ───────────────────────────────────────────────
            if spd_score < 60 or prf_score < 60:
                ttfb_line = (
                    f"{_t('Server response time is','Serverantwortzeit beträgt')} <b>{ttfb_now}ms</b> — "
                    f"{_t('ideal is under 200ms.','Ideal sind unter 200ms.')} "
                    f"{_t('Varnish Edge Cache would bring this to','Varnish Edge Cache würde dies auf')} <b>~{ttfb_proj}ms</b>. "
                    if ttfb_now and ttfb_proj else ""
                )
                ps_line = (
                    f"{_t('PageSpeed score could jump from','PageSpeed-Score könnte steigen von')} "
                    f"<b>{prf_score}</b> {_t('to','auf')} <b>{ps_min}–{ps_max}/100</b>. "
                    if ps_min else ""
                )
                st.markdown(f"""
  <div style="padding:0.75rem 1.5rem;border-bottom:1px solid #E2E8F4;">
    <div class="fs-alert-bar">
      <span class="fs-alert-icon">⚡</span>
      <div><strong>{_t('This site has a speed problem.','Diese Website hat ein Geschwindigkeitsproblem.')}</strong>
      {_t('Slow-loading websites lose visitors and rank lower on Google.','Langsam ladende Websites verlieren Besucher.')}
      {ttfb_line}{ps_line}
      {_t('Speed improvements could reduce load times by 3–10× with no code changes required.','Verbesserungen können Ladezeiten 3–10× reduzieren.')}</div>
    </div>
  </div>
""", unsafe_allow_html=True)

            # ── Performance breakdown with labeled bars ───────────────────────
            st.markdown(f"""
  <div style="padding:1.25rem 1.5rem;border-bottom:1px solid #E2E8F4;">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#64748B;margin-bottom:1rem;">
      📈 {_t('Performance Breakdown','Performance-Aufschlüsselung')}
    </div>
""", unsafe_allow_html=True)

            _bar_items = [
                (_t("Server Response Time", "Serverantwortzeit"),
                 max(0, min(100, int(100 - (ttfb_now / 50)) if isinstance(ttfb_now, (int,float)) else 50)),
                 f"{ttfb_now}ms {_t('(critical)','(kritisch)')}" if isinstance(ttfb_now,(int,float)) and ttfb_now > 800 else f"{ttfb_now}ms" if isinstance(ttfb_now,(int,float)) else "—",
                 "#DC2626" if isinstance(ttfb_now,(int,float)) and ttfb_now > 800 else "#D97706"),
                (_t("PageSpeed Score",  "PageSpeed-Score"),  prf_score,  f"{prf_score}/100", _score_color(prf_score)),
                (_t("Opportunity Score","Opportunity Score"), opp,        f"{opp}/100",        opp_col),
                (_t("Estimated After Edge Cache","Geschätzt nach Edge Cache"),
                 max(0, min(100, int(100 - (ttfb_proj / 50)) if isinstance(ttfb_proj,(int,float)) else 85)),
                 f"~{ttfb_proj}ms" if ttfb_proj else (f"~{ps_max}/100" if ps_max else "—"),
                 "#059669"),
            ]
            _bars_html = ""
            for _label, _pct, _disp, _col in _bar_items:
                _bars_html += (
                    f'<div style="margin-bottom:0.85rem;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
                    f'<span style="font-size:0.82rem;color:#475569;font-weight:500;">{_label}</span>'
                    f'<span style="font-size:0.82rem;font-weight:700;color:{_col};">{_disp}</span>'
                    f'</div>'
                    f'<div style="height:8px;background:#E2E8F4;border-radius:99px;overflow:hidden;">'
                    f'<div style="height:8px;width:{_pct}%;background:{_col};border-radius:99px;"></div>'
                    f'</div></div>'
                )
            st.markdown(f'<div style="padding:0 0 0.25rem 0;">{_bars_html}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # ── Contact info row ──────────────────────────────────────────────
            if contact:
                em    = contact.get("primary_email")
                ph    = contact.get("phones", [])
                extra = contact.get("extra_info", "")
                _email_html = f'<a href="mailto:{em}" style="color:#2563EB;text-decoration:none;">{em}</a>' if em else "—"
                _phone_html = ph[0] if ph else "—"
                st.markdown(f"""
  <div style="padding:1.25rem 1.5rem;border-bottom:1px solid #E2E8F4;">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#64748B;margin-bottom:0.75rem;">
      📧 {_t('Contact Info','Kontaktdaten')}
    </div>
    <div style="display:flex;gap:2rem;flex-wrap:wrap;">
      <div>
        <div style="font-size:0.72rem;color:#94A3B8;margin-bottom:2px;">{_t('Email','E-Mail')}</div>
        <div style="font-size:0.9rem;font-weight:600;color:#0F172A;">{_email_html}</div>
      </div>
      <div>
        <div style="font-size:0.72rem;color:#94A3B8;margin-bottom:2px;">{_t('Phone','Telefon')}</div>
        <div style="font-size:0.9rem;font-weight:600;color:#0F172A;">{_phone_html}</div>
      </div>
      {'<div style="flex:1;"><div style="font-size:0.72rem;color:#94A3B8;margin-bottom:2px;">Extra Info</div><div style="font-size:0.82rem;color:#475569;">'+extra+'</div></div>' if extra else ''}
    </div>
  </div>
""", unsafe_allow_html=True)
            elif CONTACT_AVAILABLE:
                with st.spinner(_t("Auto-extracting contact info…", "Kontaktdaten werden automatisch extrahiert…")):
                    contacts[url] = extract_contact_info(url)
                    st.session_state["contacts"] = contacts
                contact = contacts[url]

            # ── Live Preview section ──────────────────────────────────────────
            _preview_key = get_preview_api_key() if PREVIEW_API_AVAILABLE else None
            if PREVIEW_API_AVAILABLE and _preview_key:
                _safe_url_key       = url.replace("https://", "").replace("http://", "").replace("/", "_").strip("_")
                _preview_session_key = f"preview_result_{_safe_url_key}"
                _cached_preview     = st.session_state.get(_preview_session_key)
                st.markdown(f"""
  <div style="padding:1.25rem 1.5rem;border-bottom:1px solid #E2E8F4;">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#64748B;margin-bottom:0.4rem;">
      ⚡ {_t('Live Preview & Speed Measurement','Live Vorschau & Geschwindigkeitsmessung')}
    </div>
    <div style="font-size:0.85rem;color:#64748B;margin-bottom:0.85rem;">
      {_t('Provision a branded fast.site edge preview and compare real measured TTFB/TTLB timings and PageSpeed scores — before vs after Varnish Edge Cache.',
          'Erstellen Sie eine fast.site-Vorschau und vergleichen Sie echte TTFB/PageSpeed-Scores — vorher/nachher mit Varnish Edge Cache.')}
    </div>
""", unsafe_allow_html=True)
                _run_preview_btn = st.button(
                    f"🚀 {_t('Run live preview measurement','Live-Vorschaumessung starten')}",
                    key=f"preview_run_{_safe_url_key}",
                    type="primary",
                )
                st.markdown("</div>", unsafe_allow_html=True)
                if _run_preview_btn:
                    _status_ph = st.empty()
                    with st.spinner(_t("Provisioning edge preview and measuring performance…","Edge-Vorschau wird bereitgestellt…")):
                        _result = run_preview_measurement(url=url, api_key=_preview_key, progress_callback=lambda m: _status_ph.info(m))
                    _status_ph.empty()
                    st.session_state[_preview_session_key] = _result
                    st.rerun()
                if _cached_preview is not None:
                    render_preview_results(_cached_preview)
                    if _cached_preview.ok and not _cached_preview.inconclusive:
                        st.success(
                            f"✅ **{_t('Real measurement complete','Echte Messung abgeschlossen')}** — "
                            f"TTFB {_t('improved by','verbessert um')} **{_cached_preview.ttfb_improvement_pct}%**, "
                            f"PageSpeed **{_cached_preview.perf_score_origin} → {_cached_preview.perf_score_preview}** "
                            f"(+{_cached_preview.score_improvement} {_t('pts','Punkte')}). "
                            f"[{_t('View live preview','Live-Vorschau ansehen')}]({_cached_preview.preview_url})"
                        )

            # ── Cold email section ────────────────────────────────────────────
            contact = contacts.get(url, {})
            st.markdown(f"""
  <div style="padding:1.25rem 1.5rem;border-bottom:1px solid #E2E8F4;">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#64748B;margin-bottom:0.4rem;">
      ✉️ {_t('Generate Cold Email for This Site','Kalt-E-Mail für diese Website')}
    </div>
    <div style="font-size:0.85rem;color:#64748B;margin-bottom:0.85rem;">
      {_t('AI-generate a personalised outreach email highlighting this site&#39;s speed issues and the value of Varnish Edge Cache.','KI-generierte personalisierte E-Mail zu Speed-Problemen und Varnish Edge Cache.')}
    </div>
""", unsafe_allow_html=True)
            import re as _re
            m = _re.search(r"https?://(?:www\.)?([^/]+)", url)
            biz_name = m.group(1) if m else url
            cdn_info_email = st.session_state.get("cdn_map", {}).get(url, {})
            email_text = generate_cold_email(
                business_name=biz_name,
                url=url,
                overall_score=score,
                speed_score=spd_score,
                performance_score=prf_score,
                opportunity_score=opp,
                primary_email=contact.get("primary_email"),
                ttfb_ms=cur.get("ttfb_ms"),
                lcp_ms=cur.get("lcp_ms"),
                has_cdn=cdn_info_email.get("has_cdn", False),
            )
            _sender_name = st.session_state.get("rep_name", "").strip()
            if _sender_name:
                for _ph in ("[Your name]", "[your name]", "[YOUR NAME]", "[Your Name]"):
                    email_text = email_text.replace(_ph, _sender_name)

            _gen_email_btn = st.button(
                f"✉️ {_t('Generate Cold Email','Kalt-E-Mail generieren')}",
                key=f"gen_email_btn_{url}",
                type="primary",
            )
            st.markdown("</div>", unsafe_allow_html=True)

            if _gen_email_btn:
                st.session_state[f"show_email_{url}"] = True
                st.session_state["goto_tab"] = 1
            if _gen_email_btn or st.session_state.get(f"show_email_{url}"):
                edited_email = st.text_area(
                    _t("Edit before sending (optional)", "Vor dem Senden bearbeiten (optional)"),
                    value=email_text,
                    height=260,
                    key=f"email_{url}",
                )
                import streamlit.components.v1 as _components
                _safe_email = edited_email.replace("`", "\\`").replace("\\", "\\\\").replace("$", "\\$")
                _components.html(f"""
<button onclick="navigator.clipboard.writeText(`{_safe_email}`).then(()=>{{
    this.textContent='✅ Copied!';
    setTimeout(()=>{{this.textContent='📋 Copy email'}},2000);
}})" style="background:#2563EB;color:#fff;border:none;border-radius:8px;
    padding:8px 18px;font-size:14px;font-weight:600;cursor:pointer;font-family:Inter,sans-serif;">
  📋 Copy email
</button>""", height=50)

                _contacted_map = st.session_state.setdefault("contacted", {})
                _is_contacted2 = url in _contacted_map
                mark_col, status_col = st.columns([2, 3])
                with mark_col:
                    _new_contacted = st.checkbox(
                        f"✅ {_t('Mark as contacted','Als kontaktiert markieren')}",
                        value=_is_contacted2,
                        key=f"contacted_{url}",
                    )
                with status_col:
                    if _is_contacted2:
                        st.caption(f"{_t('Contacted on','Kontaktiert am')} {_contacted_map[url].get('at','')} {_t('by','von')} {_contacted_map[url].get('by','—')}")
                    else:
                        st.caption(_t("Tick once you've sent the email to avoid duplicate outreach.","Markieren Sie dies nach dem Senden."))
                if _new_contacted and not _is_contacted2:
                    _contacted_map[url] = {"at": time.strftime("%Y-%m-%d %H:%M"), "by": st.session_state.get("rep_name", "")}
                    st.session_state["contacted"] = _contacted_map
                    st.session_state["goto_tab"] = 1
                    st.rerun()
                elif not _new_contacted and _is_contacted2:
                    _contacted_map.pop(url, None)
                    st.session_state["contacted"] = _contacted_map
                    st.session_state["goto_tab"] = 1
                    st.rerun()

                smtp_configured = bool(_get_secret("SMTP_USER") and _get_secret("SMTP_PASSWORD"))
                if not smtp_configured:
                    st.info("📬 To enable one-click sending, add `SMTP_USER` and `SMTP_PASSWORD` to `.streamlit/secrets.toml`.")
                else:
                    recipient = contact.get("primary_email", "")
                    if recipient:
                        col_send, col_status = st.columns([2, 3])
                        with col_send:
                            if st.button(f"📨 Send to {recipient}", key=f"send_{url}", type="primary"):
                                lines = email_text.strip().splitlines()
                                subject_line = lines[0].replace("Subject: ", "").strip() if lines else "Site audit"
                                body = "\n".join(lines[2:]).strip()
                                ok, msg = send_email_smtp(recipient, subject_line, body)
                                if ok:
                                    st.success(f"✅ Email sent to {recipient}")
                                    st.session_state.setdefault("contacted", {})[url] = {
                                        "at": time.strftime("%Y-%m-%d %H:%M"),
                                        "by": st.session_state.get("rep_name", ""),
                                    }
                                    st.session_state["goto_tab"] = 1
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                    else:
                        st.caption(_t("No email address found for this site.", "Keine E-Mail-Adresse gefunden."))

            # ── PDF download footer ───────────────────────────────────────────
            st.markdown('<div style="padding:1rem 1.5rem;">', unsafe_allow_html=True)
            try:
                pdf_bytes = generate_audit_pdf(a, lang=_LANG)
                safe = url.replace("https://", "").replace("http://", "").replace("/", "_").strip("_")
                st.download_button(
                    f"⬇ {_t('Download Audit Report (PDF)','Prüfbericht herunterladen (PDF)')}",
                    data=pdf_bytes,
                    file_name=f"audit_{safe}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"dl_{url}",
                )
            except Exception as e:
                st.warning(f"{_t('PDF generation failed','PDF-Erstellung fehlgeschlagen')}: {e}")
            st.markdown("</div></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: EXPORTS & PDFs
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    audits_exp = st.session_state.get("audits", {})
    contacts_exp = st.session_state.get("contacts", {})
    audit_list_exp = list(audits_exp.values())
    filtered_exp = [a for a in audit_list_exp if not a.get("error")]
    cdn_map_exp = st.session_state.get("cdn_map", {})

    if not audits_exp:
        st.markdown(f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F4;border-radius:14px;box-shadow:0 2px 12px rgba(15,23,42,0.06);
    padding:3rem 2.5rem;text-align:center;margin:1.5rem 0;">
  <div style="font-size:3rem;margin-bottom:1rem;">⬇</div>
  <div style="font-size:1.15rem;font-weight:700;color:#0F172A;margin-bottom:0.5rem;">
    {_t("No data to export yet", "Noch keine Daten zum Exportieren")}
  </div>
  <div style="font-size:0.9rem;color:#64748B;max-width:400px;margin:0 auto;">
    {_t("Run website audits first, then come back here to export your leads.",
        "Führen Sie zuerst Website-Prüfungen durch, und exportieren Sie dann Ihre Leads hier.")}
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        # ── Summary stats ─────────────────────────────────────────────────────
        n_sites = len(filtered_exp)
        n_today = sum(1 for a in filtered_exp if True)  # all loaded in session = "today"
        n_hot   = sum(1 for a in filtered_exp if varnish_opportunity_score(a, cdn_info=cdn_map_exp.get(a.get("url",""), {})) >= 65)
        opps_e  = [varnish_opportunity_score(a, cdn_info=cdn_map_exp.get(a.get("url",""), {})) for a in filtered_exp]
        avg_opp = int(sum(opps_e) / len(opps_e)) if opps_e else 0
        speeds_e = [a.get("overall_score", 0) for a in filtered_exp]
        avg_spd  = int(sum(speeds_e) / len(speeds_e)) if speeds_e else 0

        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1: st.metric(_t("Sites Checked", "Geprüfte Seiten"), n_sites, f"+{n_today} {_t('today','heute')}")
        with ec2: st.metric(_t("Avg Speed Score", "Ø Speed Score"), f"{avg_spd}/100")
        with ec3: st.metric(_t("Hot Leads", "Heiße Leads"), n_hot, f"Score ≥ 0")
        with ec4: st.metric(_t("Avg Opportunity", "Ø Chance"), avg_opp, "/100")

        st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

        # ── Export cards row ──────────────────────────────────────────────────
        st.markdown(f"""
<div class="section-divider">
  <div class="section-divider-line"></div>
  <div class="section-divider-label">📤 {_t('Export', 'Exportieren')}</div>
  <div class="section-divider-line"></div>
</div>
""", unsafe_allow_html=True)

        exp_col1, exp_col2 = st.columns(2)

        # ── CSV card ──────────────────────────────────────────────────────────
        with exp_col1:
            st.markdown(f"""
<div class="result-card" style="padding:1.4rem 1.6rem;margin-bottom:0.75rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem;">
    <span style="font-size:1.3rem;">📄</span>
    <span style="font-size:1rem;font-weight:700;color:#0F172A;">{_t('Export Leads (CSV)', 'Leads exportieren (CSV)')}</span>
  </div>
  <p style="font-size:0.86rem;color:#64748B;margin:0 0 1rem 0;line-height:1.55;">
    {_t('Download all audited sites with scores, contact details, and CDN status as a spreadsheet.',
        'Alle geprüften Seiten mit Scores, Kontaktdaten und CDN-Status herunterladen.')}
  </p>
</div>
""", unsafe_allow_html=True)
            csv_bytes = build_leads_csv(
                audit_results=filtered_exp,
                contact_data=contacts_exp,
                cdn_data=cdn_map_exp,
            )
            csv_bytes = _add_contacted_column(csv_bytes, st.session_state.get("contacted", {}))
            st.download_button(
                f"⬇ {_t('Download leads CSV', 'Leads-CSV herunterladen')} ({n_sites} {_t('sites', 'Seiten')})",
                data=csv_bytes,
                file_name="fastsite_leads.csv",
                mime="text/csv",
                use_container_width=True,
                key="csv_export_tab3",
                type="primary",
            )

        # ── PDF card ──────────────────────────────────────────────────────────
        with exp_col2:
            st.markdown(f"""
<div class="result-card" style="padding:1.4rem 1.6rem;margin-bottom:0.75rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem;">
    <span style="font-size:1.3rem;">📋</span>
    <span style="font-size:1rem;font-weight:700;color:#0F172A;">{_t('Download All Reports (PDF)', 'Alle Berichte herunterladen (PDF)')}</span>
  </div>
  <p style="font-size:0.86rem;color:#64748B;margin:0 0 1rem 0;line-height:1.55;">
    {_t('Get a branded PDF audit report for every site in this session — ready to share with prospects.',
        'Für jede geprüfte Website einen PDF-Bericht herunterladen — bereit zum Teilen.')}
  </p>
</div>
""", unsafe_allow_html=True)
            writer = PdfWriter()
            for a in filtered_exp:
                try:
                    pdf_b = generate_audit_pdf(a, lang=_LANG)
                    writer.append(io.BytesIO(pdf_b))
                except Exception:
                    pass
            if writer.pages:
                buf = io.BytesIO()
                writer.write(buf)
                buf.seek(0)
                st.download_button(
                    f"⬇ {_t('Download All Reports (PDF)', 'Alle Berichte herunterladen (PDF)')}",
                    data=buf.read(),
                    file_name=_t("fastsite_leads_reports.pdf", "fastsite_leads_berichte.pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_bulk_tab3",
                    type="primary",
                )
            else:
                st.info(_t("Run audits first to generate PDF reports.", "Führen Sie zuerst Prüfungen durch."))

        # ── Save / Restore Session ────────────────────────────────────────────
        st.markdown(f"""
<div class="section-divider" style="margin-top:1.5rem;">
  <div class="section-divider-line"></div>
  <div class="section-divider-label">💾 {_t('Save / Restore Session', 'Sitzung speichern / wiederherstellen')}</div>
  <div class="section-divider-line"></div>
</div>
""", unsafe_allow_html=True)

        persist_col1, persist_col2 = st.columns(2)

        # ── Save card ─────────────────────────────────────────────────────────
        with persist_col1:
            st.markdown(f"""
<div class="result-card" style="padding:1.4rem 1.6rem;margin-bottom:0.75rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem;">
    <span style="font-size:1.3rem;">💾</span>
    <span style="font-size:1rem;font-weight:700;color:#0F172A;">{_t('Save Current Session', 'Aktuelle Sitzung speichern')}</span>
  </div>
  <p style="font-size:0.86rem;color:#64748B;margin:0 0 1rem 0;line-height:1.55;">
    {_t('Downloads all audit results, contacts, contacted status, and CDN data as a JSON file you can reload later.',
        'Lädt alle Prüfergebnisse, Kontakte, Kontaktstatus und CDN-Daten als JSON-Datei herunter.')}
  </p>
</div>
""", unsafe_allow_html=True)
            session_snapshot = {
                "audits":    {k: v for k, v in audits_exp.items()},
                "contacts":  contacts_exp,
                "cdn_map":   cdn_map_exp,
                "results":   st.session_state.get("results", []),
                "engines":   st.session_state.get("engines", []),
                "contacted": st.session_state.get("contacted", {}),
            }
            st.download_button(
                label=f"⬇ {_t('Download session (.json)', 'Sitzung herunterladen (.json)')}",
                data=json.dumps(session_snapshot, indent=2, default=str).encode("utf-8"),
                file_name="fastsite_session.json",
                mime="application/json",
                use_container_width=True,
                key="session_save_tab3",
                type="primary",
            )

        # ── Restore card ──────────────────────────────────────────────────────
        with persist_col2:
            st.markdown(f"""
<div class="result-card" style="padding:1.4rem 1.6rem;margin-bottom:0.75rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem;">
    <span style="font-size:1.3rem;">📂</span>
    <span style="font-size:1rem;font-weight:700;color:#0F172A;">{_t('Restore a Saved Session', 'Gespeicherte Sitzung wiederherstellen')}</span>
  </div>
  <p style="font-size:0.86rem;color:#64748B;margin:0 0 1rem 0;line-height:1.55;">
    {_t('Upload a previously saved JSON file to continue exactly where you left off.',
        'Laden Sie eine früher gespeicherte JSON-Datei hoch, um dort weiterzumachen.')}
  </p>
</div>
""", unsafe_allow_html=True)
            uploaded_session = st.file_uploader(
                _t("Upload session file", "Sitzungsdatei hochladen"),
                type=["json"],
                label_visibility="collapsed",
                key="session_upload_tab3",
            )
            if uploaded_session is not None:
                try:
                    loaded = json.loads(uploaded_session.read())
                    if st.button(
                        f"✅ {_t('Restore this session', 'Diese Sitzung wiederherstellen')}",
                        type="primary",
                        use_container_width=True,
                        key="session_restore_btn_tab3",
                    ):
                        st.session_state["audits"]    = loaded.get("audits", {})
                        st.session_state["contacts"]  = loaded.get("contacts", {})
                        st.session_state["cdn_map"]   = loaded.get("cdn_map", {})
                        st.session_state["contacted"] = loaded.get("contacted", {})
                        if loaded.get("results"):
                            st.session_state["results"] = loaded["results"]
                        if loaded.get("engines"):
                            st.session_state["engines"] = loaded["engines"]
                        st.success(_t(
                            f"✅ Session restored — {len(loaded.get('audits', {}))} audits loaded.",
                            f"✅ Sitzung wiederhergestellt — {len(loaded.get('audits', {}))} Prüfungen geladen.",
                        ))
                        st.rerun()
                except Exception as exc:
                    st.error(_t(f"Could not load session file: {exc}", f"Sitzungsdatei konnte nicht geladen werden: {exc}"))

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="app-footer">
  <span style="font-weight:700;color:#2563EB;">⚡ fast.site</span>
  &nbsp;·&nbsp; Lead Finder &nbsp;·&nbsp;
  {_t(
      "Find websites · Check performance · Extract contacts · Send cold emails · Export leads",
      "Websites finden · Performance prüfen · Kontakte extrahieren · Kalt-E-Mails · Leads exportieren"
  )}
</div>
""", unsafe_allow_html=True)
