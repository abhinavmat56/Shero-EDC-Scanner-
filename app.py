
import os
import sys
import io
import json
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
 
from edc_matcher import load_database, split_ingredients, match_ingredients, summarize_risk
 
# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()
 
 
def _get_secret(name):
    """Check a regular env var / .env value first (local dev), then fall
    back to Streamlit Cloud's Secrets manager (st.secrets) — so the same
    code works unmodified both locally and when deployed."""
    val = os.getenv(name)
    if val:
        return val
    try:
        return st.secrets.get(name)
    except Exception:
        return None
 
 
API_KEY = _get_secret("GEMINI_API_KEY")
 
LOGO_PATH = "assets/logo.png"
_page_icon = Image.open(LOGO_PATH) if os.path.exists(LOGO_PATH) else "🌸"
 
# st.set_page_config must run before any other Streamlit call, so it comes
# before we even attempt the google-genai import below.
st.set_page_config(page_title="Shero — EDC Scanner", page_icon=_page_icon, layout="centered")
 
# ---------------------------------------------------------------------------
# google-genai import guard
# ---------------------------------------------------------------------------
# This import fails with "cannot import name 'genai' from 'google'" when the
# app is being run from a Python environment that doesn't have the
# `google-genai` package installed (most commonly: running from an Anaconda
# base environment instead of this project's own venv). Rather than crashing
# with a raw traceback, show the fix directly in the app.
try:
    from google import genai
except ImportError:
    st.error(
        "**Missing dependency: `google-genai`**\n\n"
        "This Python environment doesn't have the `google-genai` package "
        "installed, so Shero can't start. This almost always means "
        "Streamlit is running from the wrong Python (e.g. Anaconda's base "
        "environment instead of this project's own virtual environment)."
    )
    st.markdown(
        f"**Currently running from:**\n```\n{sys.executable}\n```\n\n"
        "**To fix it, run this in your project folder:**\n"
        "```bash\n"
        "python3 -m venv venv\n"
        "source venv/bin/activate   # Windows: venv\\Scripts\\activate\n"
        "pip install -r requirements.txt\n"
        "streamlit run app.py\n"
        "```\n"
        "Then re-run the app **from that same activated terminal**. "
        "If it still fails, run `pip show google-genai` in that terminal — "
        "if it says 'not found', the install step above didn't target the "
        "environment Streamlit is using."
    )
    st.stop()
 
RISK_COLORS = {
    "High": "#b5651d",
    "Medium-High": "#c98a3f",
    "Medium": "#c9a227",
    "Low": "#6b8f4e",
}
RISK_ORDER = {"High": 0, "Medium-High": 1, "Medium": 2, "Low": 3}
 
SYSTEM_PROMPT = """
You are Shero AI, created by Team Shero.
Your purpose is to help users understand endocrine-disrupting chemicals (EDCs)
in a friendly, scientific, and easy-to-understand way.
If someone asks your name, always answer: "My name is Shero AI."
Never introduce yourself as Google Gemini.
"""
 
# ---------------------------------------------------------------------------
# Decorative styling — sage watercolor / botanical editorial theme
# ---------------------------------------------------------------------------
_SHERO_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Jost:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
 
:root {
    --sh-cream: #f8f6ee;
    --sh-sage-bg: #eef0e0;
    --sh-sage-bg-deep: #e5e9d6;
    --sh-sage-deep: #5f7247;
    --sh-sage-mid: #869a63;
    --sh-sage-line: #c9d1af;
    --sh-ink: #34331f;
    --sh-muted: #83805f;
    --sh-paper: #fffdf6;
}
 
html, body, [class*="css"] { font-family: 'Jost', sans-serif; }
 
.stApp {
    background:
        radial-gradient(ellipse 480px 320px at 4% 2%, rgba(134,154,99,0.16), transparent 65%),
        radial-gradient(ellipse 420px 300px at 98% 3%, rgba(95,114,71,0.14), transparent 62%),
        radial-gradient(ellipse 520px 360px at 100% 100%, rgba(134,154,99,0.13), transparent 60%),
        radial-gradient(ellipse 360px 260px at 0% 96%, rgba(95,114,71,0.10), transparent 60%),
        linear-gradient(165deg, var(--sh-cream) 0%, var(--sh-sage-bg) 55%, var(--sh-sage-bg-deep) 100%);
    background-attachment: fixed;
}
 
/* faint scattered-dot texture, echoing the watercolor corners */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        radial-gradient(rgba(52,51,31,0.05) 1px, transparent 1px),
        radial-gradient(rgba(52,51,31,0.04) 1px, transparent 1px);
    background-size: 90px 90px, 130px 130px;
    background-position: 0 0, 45px 65px;
    z-index: 0;
}
 
/* ---- Header block ---- */
.shero-crest-wrap {
    position: relative;
    text-align: center;
    padding: 1.6rem 1rem 0.4rem 1rem;
}
.shero-crest {
    width: 74px;
    height: 74px;
    margin: 0 auto 0.9rem auto;
    display: flex;
    align-items: center;
    justify-content: center;
}
.shero-eyebrow {
    text-align: center;
    color: var(--sh-sage-mid);
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.shero-header {
    font-family: 'Cormorant Garamond', serif;
    font-size: 3.4rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-align: center;
    color: var(--sh-sage-deep);
    line-height: 1;
    margin-bottom: 0.3rem;
}
.shero-tagline {
    text-align: center;
    color: var(--sh-muted);
    font-family: 'Cormorant Garamond', serif;
    font-style: italic;
    font-size: 1.05rem;
    letter-spacing: 0.1em;
    margin-top: -0.1rem;
    margin-bottom: 0.7rem;
}
.shero-tagline::before, .shero-tagline::after {
    content: "·";
    margin: 0 0.6em;
    color: var(--sh-sage-line);
}
.shero-sub {
    text-align: center;
    color: var(--sh-muted);
    font-size: 1rem;
    letter-spacing: 0.02em;
    margin-bottom: 0.4rem;
}
.shero-rule {
    width: 64px;
    height: 1px;
    margin: 0.9rem auto 1.7rem auto;
    background: linear-gradient(90deg, transparent, var(--sh-sage-line), transparent);
}
 
/* ---- Ingredient result cards ---- */
.edc-card {
    background: var(--sh-paper);
    border: 1px solid rgba(95,114,71,0.14);
    border-radius: 4px 14px 14px 4px;
    padding: 1rem 1.2rem;
    margin: 0.7rem 0 0.2rem 0;
    box-shadow: 0 3px 14px rgba(95,114,71,0.10);
}
.edc-card-title {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 600;
    font-size: 1.25rem;
    color: var(--sh-ink);
    letter-spacing: 0.01em;
}
.edc-card-sub {
    font-size: 0.82rem;
    color: var(--sh-muted);
    margin-top: 0.2rem;
    font-style: italic;
}
.risk-badge {
    color: var(--sh-paper);
    font-family: 'Jost', sans-serif;
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    margin-left: 0.6rem;
    vertical-align: middle;
}
 
/* ---- Section headers ---- */
h3, .stMarkdown h3 {
    font-family: 'Cormorant Garamond', serif !important;
    color: var(--sh-sage-deep) !important;
    letter-spacing: 0.04em;
}
 
div[data-testid="stChatMessage"] {
    border-radius: 4px 16px 16px 16px;
    border: 1px solid rgba(95,114,71,0.12);
    background: var(--sh-paper) !important;
}
 
/* ---- Buttons ---- */
.stButton > button, button[kind="primary"] {
    background-color: var(--sh-sage-deep) !important;
    color: var(--sh-paper) !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Jost', sans-serif !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1rem !important;
    transition: background-color 0.15s ease, transform 0.1s ease;
}
.stButton > button:hover, button[kind="primary"]:hover {
    background-color: #4c5c39 !important;
}
.stButton > button:active, button[kind="primary"]:active {
    transform: scale(0.98);
}
 
/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    border-bottom: 1px solid var(--sh-sage-line);
}
.stTabs [data-baseweb="tab"],
.stTabs [data-baseweb="tab"] p {
    font-family: 'Jost', sans-serif;
    letter-spacing: 0.05em;
    color: var(--sh-muted) !important;
}
.stTabs [aria-selected="true"],
.stTabs [aria-selected="true"] p {
    color: var(--sh-sage-deep) !important;
    font-weight: 600;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--sh-sage-mid) !important;
}
 
/* ---- Metrics ---- */
div[data-testid="stMetric"] {
    background: var(--sh-paper);
    border: 1px solid rgba(95,114,71,0.14);
    border-radius: 10px;
    padding: 0.6rem 0.4rem;
}
div[data-testid="stMetricLabel"] {
    font-family: 'Jost', sans-serif;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-size: 0.7rem !important;
    color: var(--sh-muted) !important;
}
 
/* ---- File uploader / camera frames ---- */
[data-testid="stFileUploaderDropzone"], video {
    border-radius: 12px !important;
}
[data-testid="stFileUploaderDropzone"] {
    border: 1.5px dashed var(--sh-sage-line) !important;
    background: rgba(255,253,246,0.5) !important;
}
 
/* ---- Chat input ---- */
[data-testid="stChatInput"] textarea {
    font-family: 'Jost', sans-serif;
}
 
/* ---- Expanders ---- */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    font-family: 'Jost', sans-serif;
    color: var(--sh-sage-deep);
}
 
/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: var(--sh-sage-bg);
    border-right: 1px solid rgba(95,114,71,0.14);
}
.shero-side-title {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 600;
    font-size: 1.15rem;
    color: var(--sh-sage-deep);
    margin: 0.8rem 0 0.6rem 0;
    letter-spacing: 0.02em;
}
.shero-step {
    font-size: 0.85rem;
    color: var(--sh-ink);
    line-height: 1.4;
    margin-bottom: 0.65rem;
    padding-left: 0.1rem;
}
.shero-step span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.3rem;
    height: 1.3rem;
    background: var(--sh-sage-deep);
    color: var(--sh-paper);
    border-radius: 50%;
    font-size: 0.7rem;
    font-weight: 600;
    margin-right: 0.45rem;
}
.shero-legend-row {
    display: flex;
    align-items: center;
    font-size: 0.85rem;
    color: var(--sh-ink);
    margin-bottom: 0.4rem;
}
.shero-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 0.55rem;
}
.shero-side-note {
    font-size: 0.75rem;
    color: var(--sh-muted);
    font-style: italic;
    margin-top: 0.8rem;
}
 
/* ---- Helper captions & empty states ---- */
.shero-caption {
    font-size: 0.9rem;
    color: var(--sh-muted);
    margin-bottom: 0.7rem;
}
.shero-empty-state {
    text-align: center;
    padding: 2.4rem 1rem;
    border: 1.5px dashed var(--sh-sage-line);
    border-radius: 14px;
    background: rgba(255,253,246,0.5);
    margin: 1rem 0;
}
.shero-empty-icon {
    font-size: 2.2rem;
    margin-bottom: 0.5rem;
}
.shero-empty-title {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 600;
    font-size: 1.3rem;
    color: var(--sh-sage-deep);
}
.shero-empty-sub {
    font-size: 0.88rem;
    color: var(--sh-muted);
    margin-top: 0.3rem;
}
 
/* ---- Force light-mode text ----
   Some Streamlit widgets (radio labels, camera/file-uploader captions,
   st.caption text) inherit the OS/browser's dark-mode text color even when
   our own background stays light, making them invisible (white-on-cream).
   Pin these specific elements to our own palette regardless of system
   color scheme. */
:root {
    color-scheme: light only;
}
.stApp,
section[data-testid="stSidebar"] {
    color-scheme: light only;
}
.stRadio label p,
.stRadio div[role="radiogroup"] label,
.stCheckbox label p,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
.stFileUploader label,
.stFileUploader small,
.stFileUploader span,
.stFileUploader div,
[data-testid="stCameraInput"] label,
[data-testid="stCameraInput"] p,
[data-testid="stWidgetLabel"] p,
[data-testid="stMarkdownContainer"] p,
.stMultiSelect label p,
.stTextArea label p {
    color: var(--sh-ink) !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: var(--sh-muted) !important;
}
 
/* ---- Safety score card ---- */
.shero-score-card {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    background: var(--sh-paper);
    border: 2px solid;
    border-radius: 16px;
    padding: 1rem 1.4rem;
    margin: 0.8rem 0 1.2rem 0;
}
.shero-score-number {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 600;
    font-size: 3rem;
    line-height: 1;
}
.shero-score-label {
    font-weight: 600;
    font-size: 1.05rem;
    letter-spacing: 0.03em;
}
.shero-score-sub {
    font-size: 0.78rem;
    color: var(--sh-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
</style>
"""
 
# st.html() (Streamlit >= 1.41) renders raw HTML/CSS with no sanitization and
# is the most reliable way to inject a <style> block. Older Streamlit
# versions don't have st.html, so fall back to st.markdown with
# unsafe_allow_html=True, which works for most versions but can be stripped
# by stricter sanitization in some releases.
if hasattr(st, "html"):
    st.html(_SHERO_CSS)
else:
    st.markdown(_SHERO_CSS, unsafe_allow_html=True)
 
_SHERO_CREST_SVG = """
<svg viewBox="0 0 100 100" width="74" height="74" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="shWing" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#5f7247"/>
      <stop offset="1" stop-color="#a9b98a"/>
    </linearGradient>
  </defs>
  <path d="M50 14 C33 22 22 40 14 60 C26 54 36 50 46 50 C40 62 34 74 30 86 C42 78 50 66 54 54 C60 66 68 76 80 84 C74 70 68 56 62 46 C70 44 78 40 86 32 C70 30 58 34 50 42 C50 32 50 22 50 14 Z"
        fill="url(#shWing)" opacity="0.92"/>
  <circle cx="50" cy="30" r="3.2" fill="#3d4a2c"/>
</svg>
"""
 
 
@st.cache_resource
def get_client():
    if not API_KEY:
        return None
    return genai.Client(api_key=API_KEY)
 
 
@st.cache_data
def get_database():
    return load_database("edc_database.json")
 
 
@st.cache_data
def get_logo_base64(path):
    import base64
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
 
 
# ---------------------------------------------------------------------------
# Safety score
# ---------------------------------------------------------------------------
_SCORE_PENALTIES = {"High": 22, "Medium-High": 14, "Medium": 8, "Low": 3}
 
 
def compute_safety_score(matches):
    """0-100 score: starts at 100, subtracts a weighted penalty per flagged
    chemical based on its risk level. Floors at 0."""
    penalty = sum(_SCORE_PENALTIES.get(m["entry"].get("risk_level"), 5) for m in matches)
    return max(0, 100 - penalty)
 
 
def score_label(score):
    if score >= 85:
        return "Excellent", "#6b8f4e"
    if score >= 60:
        return "Good", "#c9a227"
    if score >= 35:
        return "Caution", "#c98a3f"
    return "Poor", "#b5651d"
 
 
# ---------------------------------------------------------------------------
# Scan history — persisted to a local JSON file (per-machine, single user)
# ---------------------------------------------------------------------------
HISTORY_PATH = "shero_scan_history.json"
MAX_HISTORY = 30
 
 
def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
 
 
def save_history(history):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history[-MAX_HISTORY:], f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # non-fatal — history just won't persist this run
 
 
# ---------------------------------------------------------------------------
# Shareable result card (PNG, built with PIL — no extra assets required)
# ---------------------------------------------------------------------------
def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
 
 
def _load_share_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "C:\\Windows\\Fonts\\georgiab.ttf" if bold else "C:\\Windows\\Fonts\\georgia.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()
 
 
def generate_share_card(product_name, score, matches, ingredient_count):
    W, H = 1080, 1350
    bg, ink, muted, sage, line = (248, 246, 238), (52, 51, 31), (131, 128, 95), (95, 114, 71), (201, 209, 175)
 
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
 
    title_font = _load_share_font(66, bold=True)
    name_font = _load_share_font(32)
    score_font = _load_share_font(140, bold=True)
    label_font = _load_share_font(34)
    small_font = _load_share_font(26)
 
    draw.text((W / 2, 90), "SHERO", font=title_font, fill=sage, anchor="mm")
    draw.text((W / 2, 150), "Scan · Know · Choose Better", font=small_font, fill=muted, anchor="mm")
    draw.line([(W / 2 - 120, 195), (W / 2 + 120, 195)], fill=line, width=2)
 
    draw.text((W / 2, 250), (product_name or "Scanned product")[:42], font=name_font, fill=ink, anchor="mm")
 
    label, color_hex = score_label(score)
    draw.text((W / 2, 460), str(score), font=score_font, fill=_hex_to_rgb(color_hex), anchor="mm")
    draw.text((W / 2, 560), f"SAFETY SCORE — {label.upper()}", font=label_font, fill=ink, anchor="mm")
 
    draw.line([(100, 630), (W - 100, 630)], fill=line, width=2)
 
    y = 690
    draw.text((100, y), f"{len(matches)} of {ingredient_count} ingredients flagged", font=label_font, fill=ink)
    y += 60
    for m in sorted(matches, key=lambda x: RISK_ORDER.get(x["entry"].get("risk_level"), 9))[:9]:
        level = m["entry"].get("risk_level", "?")
        dot_rgb = _hex_to_rgb(RISK_COLORS.get(level, "#999999"))
        draw.ellipse([100, y + 6, 130, y + 36], fill=dot_rgb)
        draw.text((146, y + 21), f"{m['matched_key']} — {level}", font=small_font, fill=ink, anchor="lm")
        y += 54
 
    if not matches:
        draw.text((W / 2, 800), "No known EDCs found 🎉", font=label_font, fill=sage, anchor="mm")
 
    draw.text((W / 2, H - 60), "shero — for her, by her", font=small_font, fill=muted, anchor="mm")
 
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
 
 
client = get_client()
database = get_database()
logo_b64 = get_logo_base64(LOGO_PATH)
st.session_state.setdefault("history", load_history())
 
# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="shero-crest-wrap">', unsafe_allow_html=True)
if logo_b64:
    st.markdown(
        f'<img class="shero-crest" style="width:74px;height:74px;border-radius:16px;" '
        f'src="data:image/png;base64,{logo_b64}">',
        unsafe_allow_html=True,
    )
else:
    st.markdown(f'<div class="shero-crest">{_SHERO_CREST_SVG}</div>', unsafe_allow_html=True)
st.markdown('<div class="shero-eyebrow">Scan · Know · Choose Better</div>', unsafe_allow_html=True)
st.markdown('<div class="shero-header">Shero</div>', unsafe_allow_html=True)
st.markdown('<div class="shero-tagline">For Her, By Her</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="shero-sub">Scan a label. Know what\'s in it. Protect your hormones.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="shero-rule"></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
 
if not client:
    st.error("No GEMINI_API_KEY found. Add one to a .env file (see .env.example) to enable scanning and chat.")
 
# ---------------------------------------------------------------------------
# Sidebar — orientation, legend, reset
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="shero-side-title">How Shero works</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="shero-step"><span>1</span> Upload a label photo, snap one, or paste the ingredient list</div>
        <div class="shero-step"><span>2</span> Tap <b>Analyze</b> — Shero reads and checks every ingredient</div>
        <div class="shero-step"><span>3</span> Review flagged chemicals, risk levels, and what to do about them</div>
        """,
        unsafe_allow_html=True,
    )
 
    st.markdown('<div class="shero-side-title">Risk levels</div>', unsafe_allow_html=True)
    for level, color in RISK_COLORS.items():
        st.markdown(
            f'<div class="shero-legend-row"><span class="shero-dot" style="background:{color};"></span>{level}</div>',
            unsafe_allow_html=True,
        )
 
    st.markdown(f'<div class="shero-side-note">{len(database)} chemicals tracked in the Shero database. {len(st.session_state.get("history", []))} scans saved in your Cabinet.</div>', unsafe_allow_html=True)
 
    if st.session_state.get("last_matches") is not None:
        st.divider()
        if st.button("↺ Clear last scan", use_container_width=True):
            st.session_state.pop("last_matches", None)
            st.session_state.pop("last_raw_text", None)
            st.session_state.pop("last_score", None)
            st.session_state.pop("last_product_name", None)
            st.rerun()
 
tab_scan, tab_cabinet, tab_chat = st.tabs(["📷  Scan Ingredients", "🗄  My Cabinet", "💬  Ask Shero"])
 
# ---------------------------------------------------------------------------
# Scan tab
# ---------------------------------------------------------------------------
with tab_scan:
    st.markdown(
        '<div class="shero-caption">Choose how you\'d like to add ingredients, then tap '
        '<b>Analyze</b>.</div>',
        unsafe_allow_html=True,
    )
 
    input_mode = st.radio(
        "Input method",
        ["📷 Upload photo", "🤳 Use camera", "✍️ Paste text"],
        horizontal=True,
        label_visibility="collapsed",
    )
 
    image_file, camera_file, manual_text = None, None, ""
    if input_mode == "📷 Upload photo":
        image_file = st.file_uploader("Upload a photo of the label", type=["png", "jpg", "jpeg"])
        st.caption("Clear, well-lit, straight-on photos read best.")
    elif input_mode == "🤳 Use camera":
        camera_file = st.camera_input("Take a photo of the label")
    else:
        manual_text = st.text_area(
            "Paste the ingredient list",
            height=110,
            placeholder="e.g. Aqua, Glycerin, Phenoxyethanol, Fragrance, BHA...",
            label_visibility="collapsed",
        )
 
    uploaded = image_file or camera_file
 
    analyze_clicked = st.button("✨ Analyze", use_container_width=True, type="primary")
 
    if not analyze_clicked and st.session_state.get("last_matches") is None:
        st.markdown(
            """
            <div class="shero-empty-state">
              <div class="shero-empty-icon">🌿</div>
              <div class="shero-empty-title">No scan yet</div>
              <div class="shero-empty-sub">Add a label above and tap Analyze to see what's really in it.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
 
    if analyze_clicked:
        raw_ingredients_text = manual_text
        product_name = "Pasted ingredient list"
 
        if uploaded and client:
            with st.spinner("Reading the label..."):
                img = Image.open(uploaded)
                try:
                    ocr_response = client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=[
                            img,
                            "Extract every ingredient name from this product label image. "
                            "Return ONLY a comma-separated list of ingredient names, nothing else — "
                            "no numbering, no extra commentary.",
                        ],
                    )
                    raw_ingredients_text = ocr_response.text or ""
                    product_name = "Scanned label"
                except Exception as e:
                    st.error(
                        f"Gemini API error while reading the label: {e}\n\n"
                        "Common causes: an invalid/expired API key, the key's free-tier quota "
                        "being exceeded, or the Generative Language API not being enabled for "
                        "the key's Google Cloud project."
                    )
                    raw_ingredients_text = ""
 
        if not raw_ingredients_text or not raw_ingredients_text.strip():
            st.warning("I couldn't find any ingredients. Try a clearer photo, or paste the list manually.")
        else:
            ingredients = split_ingredients(raw_ingredients_text)
            matches = match_ingredients(ingredients, database)
            score = compute_safety_score(matches)
 
            st.session_state["last_raw_text"] = raw_ingredients_text
            st.session_state["last_matches"] = matches
            st.session_state["last_ingredient_count"] = len(ingredients)
            st.session_state["last_score"] = score
            st.session_state["last_product_name"] = product_name
 
            st.session_state["history"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "product_name": product_name,
                "ingredient_count": len(ingredients),
                "score": score,
                "matches": matches,
            })
            save_history(st.session_state["history"])
            st.rerun()
 
    # ---- Persisted results (survive reruns, e.g. clicking into an expander) ----
    last_matches = st.session_state.get("last_matches")
    if last_matches is not None:
        with st.expander("📋 What I read", expanded=False):
            st.write(st.session_state.get("last_raw_text", ""))
 
        ingredient_count = st.session_state.get("last_ingredient_count", len(last_matches))
        score = st.session_state.get("last_score", compute_safety_score(last_matches))
        score_lbl, score_color = score_label(score)
 
        st.markdown(
            f"""
            <div class="shero-score-card" style="border-color:{score_color};">
              <div class="shero-score-number" style="color:{score_color};">{score}</div>
              <div class="shero-score-meta">
                <div class="shero-score-label" style="color:{score_color};">{score_lbl}</div>
                <div class="shero-score-sub">Safety Score</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
 
        if not last_matches:
            st.success(f"Scanned {ingredient_count} ingredients — no known EDCs found in our database! 🎉")
        else:
            counts = summarize_risk(last_matches)
            st.markdown("### Results")
            mcols = st.columns(4)
            for c, level in zip(mcols, ["High", "Medium-High", "Medium", "Low"]):
                c.metric(level, counts.get(level, 0))
 
            st.markdown(f"**{len(last_matches)} of {ingredient_count} ingredients flagged.**")
 
            risk_filter = st.multiselect(
                "Filter by risk level",
                ["High", "Medium-High", "Medium", "Low"],
                default=["High", "Medium-High", "Medium", "Low"],
            )
 
            shown = [m for m in last_matches if m["entry"].get("risk_level") in risk_filter]
            if not shown:
                st.info("No chemicals match the selected risk levels.")
 
            for m in sorted(shown, key=lambda x: RISK_ORDER.get(x["entry"].get("risk_level"), 9)):
                entry = m["entry"]
                level = entry.get("risk_level", "?")
                color = RISK_COLORS.get(level, "#999")
 
                st.markdown(f"""
                <div class="edc-card" style="border-left: 6px solid {color};">
                  <div class="edc-card-title">{m['matched_key']}
                    <span class="risk-badge" style="background:{color};">{level}</span>
                  </div>
                  <div class="edc-card-sub">Matched from label text: "{m['ingredient']}" (confidence {m['score']}%)</div>
                </div>
                """, unsafe_allow_html=True)
 
                with st.expander("Details"):
                    st.write(entry.get("scientific_summary", ""))
                    st.write("**Found in:** " + ", ".join(entry.get("found_in", [])))
                    st.write("**Health effects:** " + ", ".join(entry.get("health_effects", [])))
                    reg = entry.get("regulatory_status", "")
                    st.write("**Regulatory status:** " + (reg if isinstance(reg, str) else ", ".join(reg)))
                    if entry.get("recommendations"):
                        st.write("**Recommendations:** " + ", ".join(entry.get("recommendations", [])))
 
        st.divider()
        card_bytes = generate_share_card(
            st.session_state.get("last_product_name", "Scanned product"),
            score,
            last_matches,
            ingredient_count,
        )
        st.download_button(
            "📤 Download shareable result card",
            data=card_bytes,
            file_name="shero_result_card.png",
            mime="image/png",
            use_container_width=True,
        )
 
# ---------------------------------------------------------------------------
# My Cabinet tab — saved scan history
# ---------------------------------------------------------------------------
with tab_cabinet:
    history = st.session_state.get("history", [])
    if not history:
        st.markdown(
            """
            <div class="shero-empty-state">
              <div class="shero-empty-icon">🗄</div>
              <div class="shero-empty-title">Your Cabinet is empty</div>
              <div class="shero-empty-sub">Every product you scan gets saved here automatically.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="shero-caption">{len(history)} product(s) scanned so far.</div>', unsafe_allow_html=True)
        for idx, item in enumerate(reversed(history)):
            real_idx = len(history) - 1 - idx
            lbl, color = score_label(item.get("score", 0))
            flagged = item.get("matches", [])
            top_names = ", ".join(m["matched_key"] for m in flagged[:4]) or "None"
 
            st.markdown(
                f"""
                <div class="edc-card" style="border-left: 6px solid {color};">
                  <div class="edc-card-title">{item.get('product_name', 'Product')}
                    <span class="risk-badge" style="background:{color};">{item.get('score', 0)} · {lbl}</span>
                  </div>
                  <div class="edc-card-sub">{item.get('timestamp', '')} · {item.get('ingredient_count', 0)} ingredients · Flagged: {top_names}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            del_col, _ = st.columns([1, 4])
            if del_col.button("🗑 Delete", key=f"del_hist_{real_idx}"):
                st.session_state["history"].pop(real_idx)
                save_history(st.session_state["history"])
                st.rerun()
 
# ---------------------------------------------------------------------------
# Chat tab
# ---------------------------------------------------------------------------
with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []
 
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="shero-empty-state">
              <div class="shero-empty-icon">🌸</div>
              <div class="shero-empty-title">Ask Shero anything</div>
              <div class="shero-empty-sub">About an ingredient, a chemical, or your last scan.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="shero-caption">Try one of these:</div>', unsafe_allow_html=True)
        suggestion_cols = st.columns(3)
        suggestions = [
            "Is BPA actually dangerous?",
            "What's in my last scan?",
            "How do I avoid phthalates?",
        ]
        clicked_suggestion = None
        for col, suggestion in zip(suggestion_cols, suggestions):
            if col.button(suggestion, use_container_width=True):
                clicked_suggestion = suggestion
    else:
        clicked_suggestion = None
 
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
 
    prompt = st.chat_input("Ask about any ingredient, or your last scan...") or clicked_suggestion
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
 
        if client:
            context = ""
            last_matches = st.session_state.get("last_matches")
            if last_matches:
                found = [m["matched_key"] for m in last_matches]
                context = f"\n\nFor context, the user's last scan flagged: {', '.join(found)}."
 
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=prompt + context,
                            config={"system_instruction": SYSTEM_PROMPT},
                        )
                        reply_text = response.text
                    except Exception as e:
                        reply_text = (
                            f"⚠️ Gemini API error: {e}\n\n"
                            "Common causes: an invalid/expired API key, the key's free-tier "
                            "quota being exceeded, or the Generative Language API not being "
                            "enabled for the key's Google Cloud project."
                        )
                    st.write(reply_text)
            st.session_state.messages.append({"role": "assistant", "content": reply_text})
        else:
            st.error("No GEMINI_API_KEY found.")
