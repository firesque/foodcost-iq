"""Premium visual theme: CSS, Plotly template, reusable UI components."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
INK = "#0F172A"          # near-black slate
PAPER = "#F7F8FA"
CARD = "#FFFFFF"
ACCENT = "#0E7C66"       # deep teal — money/food
ACCENT_SOFT = "#E6F4F1"
GOLD = "#B98900"
RED = "#C0392B"
RED_SOFT = "#FBEDEB"
BLUE = "#1F5FA8"
MUTED = "#64748B"
BORDER = "#E5E9F0"

CATEGORY_COLORS = {
    "PROD": "#2E8B57", "DAIRY": "#4C8BC9", "MEAT PLTRY": "#B0533A",
    "MEAT PORK": "#8F3B2A", "MEAT BEEF": "#7A2F22", "MEAT": "#8F3B2A",
    "DRY": "#8A6FB8", "FZN": "#5BA8B5", "NA BEV": "#7A8A63",
    "NA BEV BIB": "#5F6E4E", "PAPER": "#9AA2AF", "MISC": "#767C87",
    "PREP": "#B98900", "BATCH": "#B98900", "YIELD": "#B98900", "MI": "#B98900",
    "WINE RED": "#722F37", "WINE SPARK": "#C9A66B",
}

VENDOR_COLORS = {"Sysco": "#00539B", "FreshPoint": "#2E8B57"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp, p, div, span, li, td, th, input, label {
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
}
.stApp { background: #F7F8FA; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1250px; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #16233D 100%);
    border-right: 1px solid #0B1220;
}
section[data-testid="stSidebar"] * { color: #D7DEE9 !important; }
section[data-testid="stSidebar"] .stRadio label p {
    font-size: 0.92rem; font-weight: 500; padding: 2px 0;
}
section[data-testid="stSidebar"] hr { border-color: #2A3A57; }

/* ---------- typography ---------- */
h1 { font-weight: 800 !important; letter-spacing: -0.02em; color: #0F172A; }
h2, h3 { font-weight: 700 !important; letter-spacing: -0.01em; color: #0F172A; }

/* ---------- metric cards ---------- */
.metric-card {
    background: #FFFFFF; border: 1px solid #E5E9F0; border-radius: 14px;
    padding: 18px 20px 14px 20px; height: 100%;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
.metric-card .label {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: #64748B; margin-bottom: 6px;
}
.metric-card .value {
    font-size: 1.65rem; font-weight: 800; color: #0F172A; line-height: 1.1;
}
.metric-card .delta { font-size: 0.8rem; font-weight: 600; margin-top: 6px; }
.delta.good { color: #0E7C66; } .delta.bad { color: #C0392B; }
.delta.neutral { color: #64748B; }

/* ---------- insight cards ---------- */
.insight {
    background: #FFFFFF; border: 1px solid #E5E9F0; border-left: 5px solid #64748B;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
.insight.critical    { border-left-color: #C0392B; }
.insight.opportunity { border-left-color: #B98900; }
.insight.positive    { border-left-color: #0E7C66; }
.insight.info        { border-left-color: #1F5FA8; }
.insight .ititle { font-weight: 700; font-size: 1.0rem; color: #0F172A; margin-bottom: 4px;}
.insight .ibody  { font-size: 0.9rem; color: #334155; line-height: 1.5; }
.insight .iaction{
    font-size: 0.85rem; color: #0E7C66; font-weight: 600; margin-top: 8px;
}
.insight .itag {
    display: inline-block; font-size: 0.68rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 2px 9px; border-radius: 20px; margin-right: 6px;
    background: #F1F5F9; color: #475569;
}
.insight .itag.critical    { background: #FBEDEB; color: #C0392B; }
.insight .itag.opportunity { background: #FDF6E3; color: #9A7200; }
.insight .itag.positive    { background: #E6F4F1; color: #0E7C66; }

/* ---------- pills ---------- */
.pill {
    display: inline-block; padding: 3px 12px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 700;
}
.pill.red    { background: #FBEDEB; color: #C0392B; }
.pill.gold   { background: #FDF6E3; color: #9A7200; }
.pill.green  { background: #E6F4F1; color: #0E7C66; }
.pill.gray   { background: #F1F5F9; color: #475569; }

/* ---------- tables ---------- */
[data-testid="stDataFrame"] {
    border: 1px solid #E5E9F0; border-radius: 12px; overflow: hidden;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}

/* ---------- section headers ---------- */
.section-head {
    display: flex; align-items: baseline; gap: 10px;
    margin: 26px 0 10px 0;
}
.section-head .t { font-size: 1.15rem; font-weight: 700; color: #0F172A; }
.section-head .s { font-size: 0.85rem; color: #64748B; }

/* ---------- hero ---------- */
.hero {
    background: linear-gradient(120deg, #0F172A 0%, #1E3A5F 70%, #0E7C66 130%);
    border-radius: 18px; padding: 26px 30px; margin-bottom: 22px; color: white;
}
.hero .h-title { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; }
.hero .h-sub { font-size: 0.9rem; opacity: 0.85; margin-top: 4px; }
.hero .h-badge {
    display:inline-block; background: rgba(255,255,255,0.14);
    padding: 3px 12px; border-radius: 20px; font-size: 0.72rem;
    font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    margin-bottom: 10px;
}
</style>
"""


def inject() -> None:
    """Inject CSS and register the Plotly template. Call once per page run."""
    st.markdown(CSS, unsafe_allow_html=True)
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family="Inter, sans-serif", size=12.5, color=INK),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=[ACCENT, BLUE, GOLD, RED, "#8A6FB8", "#5BA8B5", "#C89B4A"],
        margin=dict(l=10, r=10, t=42, b=10),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(font_family="Inter"),
    )
    pio.templates["foodcost"] = template
    pio.templates.default = "foodcost"


def metric_card(label: str, value: str, delta: str = "",
                mood: str = "neutral") -> str:
    d = f'<div class="delta {mood}">{delta}</div>' if delta else ""
    return (f'<div class="metric-card"><div class="label">{label}</div>'
            f'<div class="value">{value}</div>{d}</div>')


def metric_row(cards: list[tuple]) -> None:
    """Render a row of metric cards. cards = [(label, value, delta, mood), ...]"""
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        label, value, *rest = card
        delta = rest[0] if rest else ""
        mood = rest[1] if len(rest) > 1 else "neutral"
        col.markdown(metric_card(label, value, delta, mood),
                     unsafe_allow_html=True)


def section(title: str, sub: str = "") -> None:
    st.markdown(
        f'<div class="section-head"><span class="t">{title}</span>'
        f'<span class="s">{sub}</span></div>', unsafe_allow_html=True)


def insight_card(severity: str, title: str, body: str, action: str,
                 impact: float = 0.0) -> str:
    tag = f'<span class="itag {severity}">{severity}</span>'
    money = (f'<span class="itag">≈ ${impact:,.0f}</span>'
             if impact and abs(impact) >= 50 else "")
    return (f'<div class="insight {severity}">{tag}{money}'
            f'<div class="ititle">{title}</div>'
            f'<div class="ibody">{body}</div>'
            f'<div class="iaction">→ {action}</div></div>')


def hero(title: str, sub: str, badge: str = "FOODCOST IQ") -> None:
    st.markdown(
        f'<div class="hero"><div class="h-badge">{badge}</div>'
        f'<div class="h-title">{title}</div>'
        f'<div class="h-sub">{sub}</div></div>', unsafe_allow_html=True)


def fmt_money(x: float, decimals: int = 0) -> str:
    try:
        return f"${x:,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(x: float, decimals: int = 1) -> str:
    try:
        return f"{x:,.{decimals}f}%"
    except (TypeError, ValueError):
        return "—"
