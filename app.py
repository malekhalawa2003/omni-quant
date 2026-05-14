import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from backend.auto_trader import auto_trader
from backend.data_feed import feed
from backend.exchange import exchange
from backend.logger import logger
from backend.order_manager import order_manager
from backend.risk_engine import risk_engine
from backend.shared_state import state
from backend.strategy_engine import engine

st.set_page_config(
    page_title="OmniQuant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# CSS — Professional dark terminal theme
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, .stApp {
    background: #080c14 !important;
    font-family: 'Inter', -apple-system, sans-serif;
    color: #c9d1d9;
}
.stApp > header { display: none !important; }
.block-container {
    padding: 0.5rem 1.5rem 0 !important;
    max-width: 100% !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid #161d27 !important;
}
[data-testid="stSidebarContent"] { padding: 1rem 0.9rem !important; }
[data-testid="stSidebar"] label { color: #8b949e !important; font-size: 0.78rem !important; }
[data-testid="stSidebar"] .stRadio label { font-size: 0.82rem !important; }
[data-testid="stSidebar"] p { color: #6e7681; font-size: 0.78rem; }

/* ── Buttons ─────────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em !important;
    transition: all 0.15s ease !important;
    border: 1px solid #30363d !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #238636, #2ea043) !important;
    border-color: #2ea043 !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2ea043, #3fb950) !important;
    box-shadow: 0 0 12px rgba(46,160,67,0.4) !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #58a6ff !important;
    color: #58a6ff !important;
}

/* ── Inputs / Select / Slider ────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 6px !important;
    color: #c9d1d9 !important;
    font-size: 0.8rem !important;
}
.stSlider [data-testid="stThumbValue"] { color: #58a6ff !important; font-size: 0.75rem !important; }
.stSlider .st-bo { background: #21262d !important; }
.stSlider .st-bu { background: #58a6ff !important; }
[data-testid="stNumberInput"] input {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    color: #c9d1d9 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
    border-radius: 6px !important;
}
[data-testid="stTextInput"] input {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    color: #c9d1d9 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    border-radius: 6px !important;
}
[data-testid="stCheckbox"] label span { font-size: 0.8rem !important; color: #8b949e !important; }

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #21262d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #30363d; }

/* ── Dividers ────────────────────────────────────────────────────────── */
hr { border: none !important; border-top: 1px solid #161d27 !important; margin: 0.6rem 0 !important; }

/* ── Alerts ──────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    background: #1a1c24 !important;
    border-radius: 8px !important;
    font-size: 0.78rem !important;
}

/* ── Hide clutter ────────────────────────────────────────────────────── */
#MainMenu, footer, .stDeployButton, [data-testid="stStatusWidget"] { display: none !important; }

/* ── Animations ──────────────────────────────────────────────────────── */
@keyframes live-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(63,185,80,.6); }
    70%  { box-shadow: 0 0 0 5px rgba(63,185,80,0); }
    100% { box-shadow: 0 0 0 0 rgba(63,185,80,0); }
}
@keyframes red-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(248,81,73,.6); }
    70%  { box-shadow: 0 0 0 5px rgba(248,81,73,0); }
    100% { box-shadow: 0 0 0 0 rgba(248,81,73,0); }
}
@keyframes confluence-glow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0,255,136,.15); }
    50%       { box-shadow: 0 0 20px 4px rgba(0,255,136,.25); }
}
@keyframes fade-in {
    from { opacity: 0; transform: translateY(-3px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── COMPONENTS ──────────────────────────────────────────────────────── */

/* Metric card */
.mcard {
    background: #0d1117;
    border: 1px solid #161d27;
    border-radius: 10px;
    padding: 0.75rem 0.9rem;
    position: relative;
    overflow: hidden;
    animation: fade-in 0.2s ease;
    height: 100%;
}
.mcard-top { position: absolute; top: 0; left: 0; width: 100%; height: 2px; }
.mcard-label {
    color: #4a5568;
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
    margin-bottom: 0.3rem;
}
.mcard-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.2rem;
    font-weight: 700;
    color: #e6edf3;
    letter-spacing: -0.02em;
    line-height: 1;
}
.mcard-delta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
    margin-top: 0.3rem;
}

/* Section header */
.sec-hdr {
    color: #30363d;
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-weight: 700;
    margin: 0.7rem 0 0.35rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.sec-hdr::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #161d27;
}

/* Signal row */
.sig-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.4rem 0.6rem;
    border-radius: 6px;
    margin-bottom: 3px;
    transition: background 0.15s;
}
.sig-row:hover { background: #0d1421; }

/* Badge */
.badge {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    font-family: 'Inter', sans-serif;
}
.badge-live   { background:#2d1b1b; color:#f85149; border:1px solid #4d1a1a; }
.badge-paper  { background:#1a2d40; color:#58a6ff; border:1px solid #1a3a5c; }
.badge-auto   { background:#1b2d1b; color:#3fb950; border:1px solid #1b3d1b; }
.badge-testnet{ background:#2d2a1a; color:#d29922; border:1px solid #4d4011; }

/* Confluence panel */
.conf-panel {
    background: #0d1117;
    border: 1px solid #161d27;
    border-radius: 10px;
    padding: 0.75rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.conf-active {
    border-color: rgba(0,255,136,0.4) !important;
    animation: confluence-glow 2s infinite;
}
.conf-bar-track {
    height: 5px;
    background: #161d27;
    border-radius: 3px;
    margin: 0.5rem 0;
    overflow: hidden;
}
.conf-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s cubic-bezier(0.4,0,0.2,1);
}

/* Risk gauge */
.gauge-track {
    height: 6px;
    background: #161d27;
    border-radius: 3px;
    margin: 0.25rem 0 0.6rem;
    overflow: hidden;
    position: relative;
}
.gauge-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}

/* Log terminal */
.log-terminal {
    background: #0d1117;
    border: 1px solid #161d27;
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    max-height: 200px;
    overflow-y: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem;
    line-height: 1.6;
}
.log-row { padding: 0.08rem 0; border-bottom: 1px solid #0d1117; }
.log-ts   { color: #21262d; }
.log-INFO     { color: #58a6ff; }
.log-WARN     { color: #d29922; }
.log-ERROR    { color: #f85149; }
.log-CRITICAL { color: #ff0000; font-weight: 700; }
.log-TRADE    { color: #bc8cff; }
.log-SIGNAL   { color: #3fb950; }

/* Circuit breaker */
.cb-strip {
    background: rgba(248,81,73,0.08);
    border: 1px solid rgba(248,81,73,0.3);
    border-radius: 6px;
    padding: 0.35rem 0.7rem;
    color: #f85149;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-top: 0.3rem;
    animation: red-pulse 2s infinite;
}

/* Panel card */
.panel {
    background: #0d1117;
    border: 1px solid #161d27;
    border-radius: 10px;
    padding: 0.75rem 0.9rem;
    height: 100%;
}

/* Positive / negative */
.pos { color: #3fb950; }
.neg { color: #f85149; }
.dim { color: #4a5568; }
.hi  { color: #e6edf3; }
.mu  { color: #8b949e; }

/* Mono numbers */
.mono { font-family: 'JetBrains Mono', monospace; }

/* Live dot */
.dot-live {
    display: inline-block;
    width: 7px; height: 7px;
    background: #3fb950;
    border-radius: 50%;
    animation: live-pulse 1.5s infinite;
    vertical-align: middle;
    margin-right: 5px;
}
.dot-dead {
    display: inline-block;
    width: 7px; height: 7px;
    background: #f85149;
    border-radius: 50%;
    vertical-align: middle;
    margin-right: 5px;
}
</style>
""", unsafe_allow_html=True)

# ── Backend threads ───────────────────────────────────────────────────────────
if "backend_started" not in st.session_state:
    feed.start()
    engine.start()
    risk_engine.start()
    order_manager.start()
    auto_trader.start()
    logger.log("INFO", "OmniQuant started")
    st.session_state.backend_started = True


# ══════════════════════════════════════════════════════════════════════════════
# HTML component helpers
# ══════════════════════════════════════════════════════════════════════════════

def metric_card(label: str, value: str, delta: str = None,
                delta_up: bool = None, accent: str = "#58a6ff") -> str:
    top_bar = f'<div class="mcard-top" style="background:linear-gradient(90deg,{accent},transparent);"></div>'
    delta_html = ""
    if delta is not None:
        col = "#3fb950" if delta_up else ("#f85149" if delta_up is False else "#8b949e")
        arrow = "▲ " if delta_up else ("▼ " if delta_up is False else "")
        delta_html = f'<div class="mcard-delta" style="color:{col};">{arrow}{delta}</div>'
    return (
        f'<div class="mcard">{top_bar}'
        f'<div class="mcard-label">{label}</div>'
        f'<div class="mcard-value">{value}</div>'
        f'{delta_html}</div>'
    )


def sec_hdr(title: str) -> str:
    return f'<div class="sec-hdr">{title}</div>'


def signal_badge(sig: int, enabled: bool) -> str:
    if not enabled:
        return '<span style="color:#21262d;font-size:.7rem;font-family:\'JetBrains Mono\',mono;">OFF</span>'
    if sig == 1:
        return '<span style="color:#3fb950;font-weight:700;font-size:.78rem;">▲ LONG</span>'
    if sig == -1:
        return '<span style="color:#f85149;font-weight:700;font-size:.78rem;">▼ SHORT</span>'
    return '<span style="color:#30363d;font-size:.78rem;">── FLAT</span>'


def prob_bar(prob: float, sig: int) -> str:
    col = "#3fb950" if sig == 1 else ("#f85149" if sig == -1 else "#21262d")
    w   = int(prob * 100)
    return (
        f'<div style="width:48px;height:3px;background:#161d27;border-radius:2px;overflow:hidden;">'
        f'<div style="width:{w}%;height:100%;background:{col};border-radius:2px;"></div></div>'
    )


def confluence_panel(long_n, short_n, en_n, confluence, ensemble,
                     sl_pct, tp_pct, auto_on) -> str:
    agree   = long_n if ensemble == 1 else short_n
    pct     = (agree / en_n * 100) if en_n > 0 else 0
    cls     = "conf-panel conf-active" if confluence else "conf-panel"
    dir_col = "#3fb950" if ensemble == 1 else ("#f85149" if ensemble == -1 else "#4a5568")
    bar_col = dir_col

    if confluence:
        label = f"{'▲ LONG' if ensemble == 1 else '▼ SHORT'} SIGNAL"
        sub   = f"{agree}/{en_n} strategies in confluence"
    else:
        label = "SCANNING MARKET"
        sub   = f"{long_n}L · {short_n}S · {en_n - long_n - short_n}F active"

    auto_tip = ""
    if auto_on and confluence:
        auto_tip = (
            f'<div style="margin-top:.4rem;padding:.3rem .5rem;background:rgba(63,185,80,.07);'
            f'border:1px solid rgba(63,185,80,.2);border-radius:6px;'
            f'color:#3fb950;font-size:.65rem;letter-spacing:.04em;">⚡ AUTO-ENTRY ARMED'
            f'<span style="color:#4a5568;margin-left:.4rem;">SL {sl_pct:.1f}% / TP {tp_pct:.1f}%</span></div>'
        )

    return (
        f'<div class="{cls}">'
        f'<div style="color:#30363d;font-size:.58rem;letter-spacing:.14em;font-weight:700;margin-bottom:.35rem;">ENSEMBLE SIGNAL</div>'
        f'<div class="conf-bar-track">'
        f'<div class="conf-bar-fill" style="width:{pct:.0f}%;background:{bar_col};'
        f'{"box-shadow:0 0 8px "+bar_col+";" if confluence else ""}"></div></div>'
        f'<div style="color:{dir_col};font-size:.9rem;font-weight:800;letter-spacing:.04em;">{label}</div>'
        f'<div style="color:#30363d;font-size:.65rem;margin-top:.2rem;">{sub}</div>'
        f'{auto_tip}</div>'
    )


def position_card(pos: dict, price: float) -> str:
    side = pos["side"]
    if not side:
        return (
            '<div class="panel" style="display:flex;align-items:center;justify-content:center;min-height:80px;">'
            '<div style="color:#21262d;font-size:.85rem;font-family:\'JetBrains Mono\',mono;letter-spacing:.1em;">⭕ NO POSITION</div>'
            '</div>'
        )
    side_col  = "#3fb950" if side == "long" else "#f85149"
    side_arr  = "▲" if side == "long" else "▼"
    upnl      = pos["unrealized_pnl"]
    upnl_col  = "#3fb950" if upnl >= 0 else "#f85149"
    upnl_arr  = "+" if upnl >= 0 else ""
    cost      = pos["entry_price"] * pos["size"]
    upnl_pct  = (upnl / cost * 100) if cost > 0 else 0.0
    dist      = abs(price - pos["entry_price"])
    dist_pct  = (dist / pos["entry_price"] * 100) if pos["entry_price"] > 0 else 0

    return (
        f'<div class="panel" style="border-top:2px solid {side_col};">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
        f'<div>'
        f'  <div style="font-size:.6rem;color:#4a5568;letter-spacing:.12em;text-transform:uppercase;font-weight:600;">Position</div>'
        f'  <div style="font-size:1.1rem;font-weight:800;color:{side_col};margin-top:.15rem;">{side_arr} {side.upper()}</div>'
        f'  <div style="font-family:\'JetBrains Mono\',mono;font-size:.78rem;color:#8b949e;margin-top:.2rem;">'
        f'    {pos["size"]:.4f} units</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'  <div style="font-size:.6rem;color:#4a5568;letter-spacing:.12em;text-transform:uppercase;font-weight:600;">Entry</div>'
        f'  <div style="font-family:\'JetBrains Mono\',mono;font-size:1rem;font-weight:700;color:#e6edf3;margin-top:.15rem;">'
        f'    ${pos["entry_price"]:,.2f}</div>'
        f'  <div style="font-family:\'JetBrains Mono\',mono;font-size:.72rem;color:#4a5568;margin-top:.2rem;">'
        f'    Δ ${dist:.2f} ({dist_pct:.2f}%)</div>'
        f'</div></div>'
        f'<div style="margin-top:.6rem;padding-top:.5rem;border-top:1px solid #161d27;'
        f'display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="font-size:.58rem;color:#4a5568;letter-spacing:.1em;font-weight:600;">UNREALIZED P&L</div>'
        f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1.1rem;font-weight:700;color:{upnl_col};">'
        f'  {upnl_arr}${abs(upnl):,.2f} '
        f'  <span style="font-size:.7rem;">({upnl_arr}{abs(upnl_pct):.2f}%)</span></div>'
        f'</div></div>'
    )


def gauge_html(label: str, used: float, color: str, text: str) -> str:
    w = int(min(used, 1.0) * 100)
    glow = f"box-shadow: 0 0 6px {color};" if used > 0.6 else ""
    return (
        f'<div style="margin-bottom:.5rem;">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:.2rem;">'
        f'<span style="color:#4a5568;font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">{label}</span>'
        f'<span style="font-family:\'JetBrains Mono\',mono;font-size:.7rem;color:#8b949e;">{text}</span></div>'
        f'<div class="gauge-track">'
        f'<div class="gauge-fill" style="width:{w}%;background:{color};{glow}"></div>'
        f'</div></div>'
    )


def order_row(o: dict) -> str:
    status = o.get("_s", o.get("status", "?"))
    sc = {"PENDING": "#d29922", "FILLED": "#3fb950", "REJECTED": "#f85149",
          "CANCELLED": "#4a5568"}.get(status, "#8b949e")
    fp = f"@ ${o['fill_price']:,.4f}" if o.get("fill_price") else ""
    sl = f"slip ${o['slippage']:.4f}" if o.get("slippage") else ""
    md = o.get("mode", "")
    md_col = "#f85149" if md == "LIVE" else "#4a5568"
    return (
        f'<div style="display:flex;gap:.4rem;align-items:center;'
        f'padding:.2rem 0;border-bottom:1px solid #0d1117;font-family:\'JetBrains Mono\',mono;font-size:.72rem;">'
        f'<span style="color:{sc};width:68px;font-weight:600;">{status}</span>'
        f'<span style="color:{md_col};width:36px;font-size:.62rem;">{md}</span>'
        f'<span style="color:#e6edf3;width:44px;">{o.get("side","").upper()}</span>'
        f'<span style="color:#8b949e;width:56px;">{o.get("size",0):.4f}</span>'
        f'<span style="color:#58a6ff;">{fp}</span>'
        f'<span style="color:#4a5568;font-size:.65rem;">{sl}</span>'
        f'</div>'
    )


def trade_row(t: dict) -> str:
    pnl = t.get("pnl", 0)
    col = "#3fb950" if pnl >= 0 else "#f85149"
    sgn = "+" if pnl >= 0 else ""
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:.18rem 0;border-bottom:1px solid #0d1117;font-family:\'JetBrains Mono\',mono;font-size:.72rem;">'
        f'<span style="color:#30363d;width:56px;">{t.get("time","")}</span>'
        f'<span style="color:#8b949e;">{t.get("side","").upper()}</span>'
        f'<span style="color:{col};font-weight:600;">{sgn}${abs(pnl):.2f}</span>'
        f'</div>'
    )


def log_row(e: dict) -> str:
    lvl   = e.get("level", "INFO")
    ts    = e.get("datetime", "")
    msg   = e.get("message", "")
    lvl_c = {"INFO":"#58a6ff","WARN":"#d29922","ERROR":"#f85149",
              "CRITICAL":"#ff0000","TRADE":"#bc8cff","SIGNAL":"#3fb950"}.get(lvl, "#8b949e")
    return (
        f'<div class="log-row">'
        f'<span class="log-ts">{ts}</span> '
        f'<span style="color:{lvl_c};font-weight:600;">[{lvl}]</span> '
        f'<span style="color:#6e7681;">{msg}</span></div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# Chart
# ══════════════════════════════════════════════════════════════════════════════

_BG   = "#0d1117"
_GRID = "#161d27"


def build_chart(candles) -> go.Figure:
    if not candles:
        fig = go.Figure()
        fig.add_annotation(
            text="⏳ Connecting to Binance…",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False,
            font=dict(color="#30363d", size=16, family="Inter"),
        )
        fig.update_layout(
            paper_bgcolor=_BG, plot_bgcolor=_BG,
            height=430, margin=dict(l=0, r=50, t=0, b=0),
        )
        return fig

    df = pd.DataFrame([{
        "t": pd.Timestamp(c.time, unit="s", tz="UTC"),
        "o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume,
    } for c in candles])

    up   = "#089981"   # TradingView green
    down = "#f23645"   # TradingView red
    bar_colors = [up if r.c >= r.o else down for _, r in df.iterrows()]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.015, row_heights=[0.72, 0.28],
    )

    fig.add_trace(go.Candlestick(
        x=df["t"], open=df["o"], high=df["h"], low=df["l"], close=df["c"],
        increasing=dict(line_color=up,   fillcolor=up),
        decreasing=dict(line_color=down, fillcolor=down),
        line_width=1,
        name=state.symbol,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=df["t"], y=df["v"], marker_color=bar_colors,
        marker_opacity=0.5, name="Volume",
    ), row=2, col=1)

    # Entry line
    with state.acquire():
        pos = dict(state.position)
    if pos["side"] and pos["entry_price"] > 0:
        col_line = up if pos["side"] == "long" else down
        fig.add_hline(
            y=pos["entry_price"], row=1, col=1,
            line=dict(color="#d29922", dash="dot", width=1.5),
            annotation_text=f"  Entry ${pos['entry_price']:,.2f}",
            annotation_font=dict(color="#d29922", size=11, family="JetBrains Mono"),
            annotation_position="right",
        )

    ax = dict(
        gridcolor=_GRID, gridwidth=1, showgrid=True,
        tickfont=dict(color="#30363d", size=10, family="JetBrains Mono"),
        zeroline=False, showline=False,
    )
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(family="Inter", color="#8b949e"),
        xaxis_rangeslider_visible=False,
        height=430, margin=dict(l=0, r=60, t=8, b=0),
        showlegend=False,
        yaxis={**ax, "side": "right", "tickformat": ",.2f"},
        yaxis2={**ax, "side": "right", "tickformat": ",.0f"},
        xaxis=ax, xaxis2=ax,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#161d27", bordercolor="#21262d",
                         font=dict(family="JetBrains Mono", size=11)),
    )
    return fig


def build_depth_chart(bids, asks) -> go.Figure | None:
    if not bids and not asks:
        return None
    fig = go.Figure()
    if bids:
        fig.add_trace(go.Scatter(
            x=[b[0] for b in bids],
            y=list(np.cumsum([b[1] for b in bids])),
            fill="tozeroy", fillcolor="rgba(8,153,129,.15)",
            line=dict(color="#089981", width=1.5), name="Bids",
        ))
    if asks:
        fig.add_trace(go.Scatter(
            x=[a[0] for a in asks],
            y=list(np.cumsum([a[1] for a in asks])),
            fill="tozeroy", fillcolor="rgba(242,54,69,.15)",
            line=dict(color="#f23645", width=1.5), name="Asks",
        ))
    ax = dict(gridcolor=_GRID, showgrid=True, zeroline=False,
               tickfont=dict(color="#30363d", size=9, family="JetBrains Mono"))
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        height=200, margin=dict(l=0, r=0, t=18, b=0),
        showlegend=True,
        legend=dict(orientation="h", y=1.25, x=0,
                     font=dict(size=9, color="#4a5568", family="JetBrains Mono"),
                     bgcolor="rgba(0,0,0,0)"),
        yaxis=ax, xaxis=ax,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#161d27", bordercolor="#21262d",
                         font=dict(family="JetBrains Mono", size=10)),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown(
            '<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem;">'
            '<div style="font-size:1.3rem;font-weight:800;color:#e6edf3;letter-spacing:-.02em;">OmniQuant</div>'
            '<div style="font-size:.62rem;color:#30363d;letter-spacing:.12em;padding-top:.25rem;">v2.0</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        # Symbol / Timeframe
        syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
        tfs  = ["1m", "5m", "15m", "1h"]
        sym  = st.selectbox("Symbol",    syms, index=syms.index(state.symbol) if state.symbol in syms else 0)
        tf   = st.selectbox("Timeframe", tfs,  index=tfs.index(state.timeframe) if state.timeframe in tfs else 0)
        if sym != state.symbol or tf != state.timeframe:
            feed.restart(sym, tf)
        st.divider()

        # Trading mode
        st.markdown('<div style="color:#4a5568;font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Trading Mode</div>', unsafe_allow_html=True)
        mode = st.radio("Mode", ["📄 Paper", "🔴 Live Exchange"],
                         horizontal=True, label_visibility="collapsed",
                         index=1 if state.live_trading else 0)
        want_live = mode == "🔴 Live Exchange"

        if want_live:
            api_key = st.text_input("API Key",    type="password",
                                     value=st.session_state.get("api_key",""),
                                     placeholder="Binance API Key")
            api_sec = st.text_input("API Secret", type="password",
                                     value=st.session_state.get("api_sec",""),
                                     placeholder="Binance Secret")
            testnet = st.checkbox("Use Testnet", value=True)
            c1, c2  = st.columns(2)
            with c1:
                if st.button("Connect", use_container_width=True, type="primary"):
                    st.session_state.api_key = api_key
                    st.session_state.api_sec = api_sec
                    ok = exchange.connect(api_key, api_sec, testnet)
                    if ok:
                        with state.acquire():
                            state.live_trading = True
                        st.rerun()
                    else:
                        st.error(exchange.error or "Failed")
            with c2:
                if st.button("Disconnect", use_container_width=True):
                    exchange.disconnect()
                    with state.acquire():
                        state.live_trading = False
                    st.rerun()

            if state.live_connected:
                bal = state.account_balance
                st.markdown(
                    f'<div style="background:#0d1421;border:1px solid #1a3a5c;border-radius:8px;'
                    f'padding:.5rem .75rem;margin-top:.3rem;text-align:center;">'
                    f'<div style="color:#4a5568;font-size:.58rem;letter-spacing:.12em;font-weight:700;">BALANCE</div>'
                    f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1.1rem;font-weight:700;'
                    f'color:#58a6ff;margin-top:.1rem;">${bal:,.2f} <span style="font-size:.7rem;color:#4a5568;">USDT</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            if state.live_trading:
                exchange.disconnect()
                with state.acquire():
                    state.live_trading = False

        st.divider()

        # Controls
        st.markdown('<div style="color:#4a5568;font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Controls</div>', unsafe_allow_html=True)
        ca, cb_ = st.columns(2)
        with ca:
            if state.trading_active:
                if st.button("⏹  Stop", use_container_width=True):
                    with state.acquire():
                        state.trading_active = False
                    logger.log("INFO", "Trading stopped")
            else:
                can = not any(state.circuit_breakers.values())
                if want_live and not state.live_connected:
                    can = False
                if st.button("▶  Start", use_container_width=True, type="primary", disabled=not can):
                    with state.acquire():
                        state.trading_active    = True
                        state.emergency_stopped = False
                    logger.log("INFO", f"Trading started ({'LIVE' if state.live_trading else 'paper'})")
        with cb_:
            if st.button("🚨 KILL", use_container_width=True):
                order_manager.emergency_stop()

        if any(state.circuit_breakers.values()):
            st.warning("Circuit breaker active")
            if st.button("↺ Reset Breakers", use_container_width=True):
                with state.acquire():
                    for k in state.circuit_breakers:
                        state.circuit_breakers[k] = False
                    state.emergency_stopped = False
                logger.log("WARN", "Breakers reset")

        st.divider()

        # Auto-trader
        st.markdown('<div style="color:#4a5568;font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Auto-Trader</div>', unsafe_allow_html=True)
        auto_on = st.toggle("Enable", value=state.auto_trade)
        with state.acquire():
            state.auto_trade = auto_on
        if auto_on:
            sl  = st.slider("Stop-Loss %",      0.5, 10.0, state.stop_loss_pct,      step=0.5)
            tp  = st.slider("Take-Profit %",    1.0, 20.0, state.take_profit_pct,    step=0.5)
            rpt = st.slider("Risk / Trade %",   0.1,  5.0, state.risk_per_trade_pct, step=0.1)
            with state.acquire():
                state.stop_loss_pct      = sl
                state.take_profit_pct    = tp
                state.risk_per_trade_pct = rpt
            st.caption("Entry: 3+ strategies · Exit: SL / TP / reversal")

        st.divider()

        # Risk limits
        st.markdown('<div style="color:#4a5568;font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Risk Limits</div>', unsafe_allow_html=True)
        dl  = st.slider("Daily Loss Cap ($)",  100,  5_000, int(state.daily_loss_limit),  step=50)
        cap = st.slider("Max Position ($)",    100, 10_000, int(state.position_size_cap), step=100)
        with state.acquire():
            state.daily_loss_limit  = float(dl)
            state.position_size_cap = float(cap)

        st.divider()

        # Strategies
        st.markdown('<div style="color:#4a5568;font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Strategies</div>', unsafe_allow_html=True)
        with state.acquire():
            names = list(state.strategies.keys())
            vals  = {k: v["enabled"] for k, v in state.strategies.items()}
        for name in names:
            en = st.checkbox(name, value=vals[name], key=f"s_{name}")
            with state.acquire():
                state.strategies[name]["enabled"] = en

        st.divider()

        # Manual order
        st.markdown('<div style="color:#4a5568;font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.4rem;">Manual Order</div>', unsafe_allow_html=True)
        side_m = st.radio("Side", ["LONG", "SHORT"], horizontal=True, label_visibility="collapsed")
        size_m = st.number_input("Size", min_value=0.001, value=0.01, step=0.001, format="%.4f", label_visibility="collapsed")
        if st.button("Place Order", use_container_width=True):
            order_manager.place_order(side_m.lower(), size_m)

        st.divider()
        st.caption(f"Log → {logger.log_file}")


render_sidebar()

# ══════════════════════════════════════════════════════════════════════════════
# Header placeholder (rendered each tick)
# ══════════════════════════════════════════════════════════════════════════════
header_ph = st.empty()


def render_header(price, chg_pct, connected, trading_active, live_trading, auto_trade):
    dot   = '<span class="dot-live"></span>' if connected else '<span class="dot-dead"></span>'
    conn  = "LIVE DATA" if connected else "DISCONNECTED"
    trad  = ('<span style="color:#3fb950;font-weight:600;">⬤ TRADING</span>'
              if trading_active else '<span style="color:#30363d;">◯ IDLE</span>')

    badges = ""
    if live_trading:
        badges += '<span class="badge badge-live">LIVE</span> '
    else:
        badges += '<span class="badge badge-paper">PAPER</span> '
    if auto_trade and trading_active:
        badges += '<span class="badge badge-auto">AUTO</span>'

    pnl_col = "#3fb950" if chg_pct >= 0 else "#f85149"
    pnl_sym = "▲" if chg_pct >= 0 else "▼"
    now     = datetime.now().strftime("%H:%M:%S")

    header_ph.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
         padding:.3rem 0 .55rem;border-bottom:1px solid #161d27;margin-bottom:.5rem;">
      <div style="display:flex;align-items:center;gap:.7rem;">
        <span style="font-size:1.4rem;font-weight:800;color:#e6edf3;letter-spacing:-.03em;
              font-family:'Inter',sans-serif;">OmniQuant</span>
        <div style="display:flex;gap:.35rem;align-items:center;">{badges}</div>
        <span style="color:#21262d;">|</span>
        <span style="color:#4a5568;font-size:.82rem;font-family:'JetBrains Mono',mono;">
          {state.symbol} · {state.timeframe}</span>
        <span style="font-family:'JetBrains Mono',mono;font-size:.85rem;color:{pnl_col};">
          {pnl_sym} {abs(chg_pct):.2f}%</span>
      </div>
      <div style="display:flex;align-items:center;gap:1rem;font-size:.75rem;">
        <span>{dot} <span style="color:#4a5568;">{conn}</span></span>
        <span>{trad}</span>
        <span style="color:#21262d;font-family:'JetBrains Mono',mono;">{now}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Main loop
# ══════════════════════════════════════════════════════════════════════════════
main_ph = st.empty()

while True:
    ticker  = state.ticker.copy()
    price   = ticker["price"]
    bid     = ticker["bid"]
    ask     = ticker["ask"]
    spread  = ask - bid
    h24     = ticker["high_24h"]
    l24     = ticker["low_24h"]
    vol24   = ticker["volume_24h"]
    chg_pct = ticker["price_change_pct"]

    render_header(price, chg_pct, state.connected, state.trading_active,
                  state.live_trading, state.auto_trade)

    with main_ph.container():

        # ── Row 1: Ticker metrics ─────────────────────────────────────────
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        pct_up  = chg_pct >= 0
        acc_col = "#3fb950" if pct_up else "#f85149"
        cards   = [
            (c1, metric_card("Last Price", f"${price:,.2f}",
                              f"{chg_pct:+.2f}%", pct_up, acc_col)),
            (c2, metric_card("Bid",  f"${bid:,.4f}",  accent="#089981")),
            (c3, metric_card("Ask",  f"${ask:,.4f}",  accent="#f23645")),
            (c4, metric_card("24h High",  f"${h24:,.2f}", accent="#d29922")),
            (c5, metric_card("24h Low",   f"${l24:,.2f}", accent="#4a5568")),
            (c6, metric_card("24h Volume", f"{vol24:,.0f}", accent="#58a6ff")),
        ]
        for col, html in cards:
            with col:
                st.markdown(html, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:.4rem;'></div>", unsafe_allow_html=True)

        # ── Row 2: Chart + Signals ────────────────────────────────────────
        chart_col, sig_col = st.columns([3, 1], gap="small")

        with chart_col:
            st.plotly_chart(
                build_chart(state.get_candles(200)),
                use_container_width=True,
                config={"displayModeBar": False},
                key="candle_chart",
            )

        with sig_col:
            st.markdown(sec_hdr("Strategies"), unsafe_allow_html=True)

            with state.acquire():
                strats_snap = {k: dict(v) for k, v in state.strategies.items()}
                ensemble    = state.ensemble_signal
                confluence  = state.confluence_met
                sl_pct      = state.stop_loss_pct
                tp_pct      = state.take_profit_pct
                auto_on_s   = state.auto_trade

            long_n  = sum(1 for s in strats_snap.values() if s["enabled"] and s["signal"] == 1)
            short_n = sum(1 for s in strats_snap.values() if s["enabled"] and s["signal"] == -1)
            en_n    = sum(1 for s in strats_snap.values() if s["enabled"])

            rows_html = ""
            for name, s in strats_snap.items():
                sig, prob, en = s["signal"], s["win_prob"], s["enabled"]
                bg = ""
                if en and sig == 1:
                    bg = "background:rgba(8,153,129,.06);"
                elif en and sig == -1:
                    bg = "background:rgba(242,54,69,.06);"
                rows_html += (
                    f'<div class="sig-row" style="{bg}">'
                    f'<div>'
                    f'<div style="color:#4a5568;font-size:.62rem;font-weight:600;'
                    f'letter-spacing:.08em;text-transform:uppercase;">{name}</div>'
                    f'<div style="margin-top:.15rem;">{signal_badge(sig, en)}</div>'
                    f'</div>'
                    f'<div style="text-align:right;">'
                    f'<div style="color:#30363d;font-family:\'JetBrains Mono\',mono;'
                    f'font-size:.68rem;margin-bottom:.2rem;">{prob:.0%}</div>'
                    f'{prob_bar(prob, sig)}'
                    f'</div></div>'
                )

            st.markdown(rows_html, unsafe_allow_html=True)
            st.markdown("<div style='margin-top:.5rem;'></div>", unsafe_allow_html=True)
            st.markdown(
                confluence_panel(long_n, short_n, en_n, confluence,
                                  ensemble, sl_pct, tp_pct, auto_on_s),
                unsafe_allow_html=True,
            )

        # ── Row 3: Position + Risk + Performance ──────────────────────────
        st.markdown(sec_hdr("Risk & Performance"), unsafe_allow_html=True)
        pos_col, risk_col, perf_col = st.columns([1.2, 1.4, 1.4], gap="small")

        with state.acquire():
            pos    = dict(state.position)
            dpnl   = state.daily_pnl
            mdd    = state.max_drawdown
            equity = state.current_equity
            dl_lim = state.daily_loss_limit
            sz_cap = state.position_size_cap
            cb     = dict(state.circuit_breakers)
            perf   = dict(state.performance)
            trades = list(state.session_trades)
            live   = state.live_trading
            bal    = state.account_balance

        with pos_col:
            st.markdown(position_card(pos, price), unsafe_allow_html=True)

        with risk_col:
            dpnl_up = dpnl >= 0
            eq_val  = bal if live else equity
            ri_html = (
                f'<div class="panel">'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem .75rem;margin-bottom:.6rem;">'
                # Daily P&L
                f'<div><div style="color:#4a5568;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">Daily P&L</div>'
                f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1rem;font-weight:700;'
                f'color:{"#3fb950" if dpnl_up else "#f85149"};">'
                f'{"+" if dpnl_up else ""}{dpnl:,.2f}</div></div>'
                # Max DD
                f'<div><div style="color:#4a5568;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">Max Drawdown</div>'
                f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1rem;font-weight:700;'
                f'color:{"#d29922" if mdd > 5 else "#8b949e"};">{mdd:.1f}%</div></div>'
                # Equity
                f'<div><div style="color:#4a5568;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">{"Balance" if live else "Equity"}</div>'
                f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1rem;font-weight:700;color:#e6edf3;">'
                f'${eq_val:,.2f}</div></div>'
                # Spread
                f'<div><div style="color:#4a5568;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">Spread</div>'
                f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1rem;font-weight:700;color:#8b949e;">'
                f'${spread:.4f}</div></div>'
                f'</div>'
            )
            loss_used = min(abs(dpnl) / dl_lim, 1.0) if dpnl < 0 else 0.0
            loss_col  = "#f85149" if loss_used > 0.7 else ("#d29922" if loss_used > 0.4 else "#3fb950")
            heat      = min(pos["size"] / sz_cap, 1.0) if pos["size"] > 0 else 0.0
            heat_col  = "#f85149" if heat > 0.7 else ("#d29922" if heat > 0.4 else "#58a6ff")

            ri_html += gauge_html("Daily Loss", loss_used, loss_col,
                                   f"${abs(dpnl):.0f} / ${dl_lim:.0f}")
            ri_html += gauge_html("Position Heat", heat, heat_col, f"{heat:.0%}")

            for key, trig in cb.items():
                if trig:
                    ri_html += f'<div class="cb-strip">⛔ {key.replace("_"," ").upper()}</div>'

            ri_html += "</div>"
            st.markdown(ri_html, unsafe_allow_html=True)

        with perf_col:
            sharpe = perf["sharpe"]
            wr     = perf["win_rate"]
            pf     = perf["profit_factor"]
            streak = perf["current_streak"]

            sh_c  = "#3fb950" if sharpe > 0.5 else ("#d29922" if sharpe > 0 else "#f85149")
            wr_c  = "#3fb950" if wr > 0.55    else ("#d29922" if wr > 0.45  else "#f85149")
            pf_c  = "#3fb950" if pf > 1.5     else ("#d29922" if pf > 1.0   else "#f85149")
            st_c  = "#3fb950" if streak > 0   else ("#f85149" if streak < 0  else "#4a5568")
            st_s  = f"{'▲' if streak > 0 else '▼'} {abs(streak)}" if streak else "—"
            pf_s  = f"{pf:.2f}" if pf != float("inf") else "∞"

            pe_html = (
                f'<div class="panel">'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem .75rem;margin-bottom:.5rem;">'
                + "".join([
                    f'<div><div style="color:#4a5568;font-size:.6rem;text-transform:uppercase;'
                    f'letter-spacing:.1em;font-weight:600;">{lbl}</div>'
                    f'<div style="font-family:\'JetBrains Mono\',mono;font-size:1rem;'
                    f'font-weight:700;color:{col};">{val}</div></div>'
                    for lbl, val, col in [
                        ("Sharpe (20T)", f"{sharpe:.2f}", sh_c),
                        ("Win Rate",     f"{wr:.1%}",     wr_c),
                        ("Profit Factor",pf_s,            pf_c),
                        ("Streak",       st_s,            st_c),
                    ]
                ])
                + f'</div>'
            )

            pe_html += (
                f'<div style="color:#4a5568;font-size:.58rem;letter-spacing:.1em;'
                f'text-transform:uppercase;font-weight:600;margin-bottom:.3rem;">'
                f'CONSEC. W/L &nbsp; '
                f'<span style="font-family:\'JetBrains Mono\',mono;color:#3fb950;font-size:.75rem;">'
                f'{perf["max_consec_wins"]}W</span>'
                f'<span style="color:#30363d;"> / </span>'
                f'<span style="font-family:\'JetBrains Mono\',mono;color:#f85149;font-size:.75rem;">'
                f'{perf["max_consec_losses"]}L</span></div>'
            )

            if trades:
                pe_html += '<div style="border-top:1px solid #161d27;padding-top:.4rem;">'
                for t in reversed(trades[-6:]):
                    pe_html += trade_row(t)
                pe_html += "</div>"
            else:
                pe_html += '<div style="color:#21262d;font-size:.75rem;font-family:\'JetBrains Mono\',mono;padding:.4rem 0;">No trades this session</div>'

            pe_html += "</div>"
            st.markdown(pe_html, unsafe_allow_html=True)

        # ── Row 4: Order flow ─────────────────────────────────────────────
        st.markdown(sec_hdr("Order Flow"), unsafe_allow_html=True)
        of1, of2, of3 = st.columns([1.5, 1.5, 1], gap="small")

        with of1:
            with state.acquire():
                pending  = list(state.pending_orders[-5:])
                filled   = list(state.filled_orders[-5:])
                rejected = list(state.rejected_orders[-3:])

            all_orders = sorted(
                [dict(o, _s="PENDING")  for o in pending]  +
                [dict(o, _s="FILLED")   for o in filled]   +
                [dict(o, _s="REJECTED") for o in rejected],
                key=lambda x: x.get("created_at", 0), reverse=True,
            )[:8]

            ord_html = '<div class="panel">'
            if all_orders:
                ord_html += "".join(order_row(o) for o in all_orders)
            else:
                ord_html += '<div style="color:#21262d;font-family:\'JetBrains Mono\',mono;font-size:.75rem;padding:.3rem 0;">No orders yet</div>'
            ord_html += "</div>"
            st.markdown(ord_html, unsafe_allow_html=True)

        with of2:
            with state.acquire():
                bids = list(state.orderbook.get("bids", []))
                asks = list(state.orderbook.get("asks", []))

            if bids or asks:
                fig_ob = build_depth_chart(bids, asks)
                if fig_ob:
                    st.plotly_chart(fig_ob, use_container_width=True,
                                    config={"displayModeBar": False},
                                    key="orderbook_chart")
            else:
                ob_html = (
                    '<div class="panel">'
                    f'<div style="display:flex;justify-content:space-between;padding:.25rem 0;'
                    f'border-bottom:1px solid #161d27;">'
                    f'<span style="color:#4a5568;font-size:.68rem;">BID</span>'
                    f'<span style="font-family:\'JetBrains Mono\',mono;color:#089981;font-size:.85rem;font-weight:600;">${bid:,.4f}</span></div>'
                    f'<div style="display:flex;justify-content:space-between;padding:.25rem 0;'
                    f'border-bottom:1px solid #161d27;">'
                    f'<span style="color:#4a5568;font-size:.68rem;">ASK</span>'
                    f'<span style="font-family:\'JetBrains Mono\',mono;color:#f23645;font-size:.85rem;font-weight:600;">${ask:,.4f}</span></div>'
                    f'<div style="display:flex;justify-content:space-between;padding:.25rem 0;">'
                    f'<span style="color:#4a5568;font-size:.68rem;">SPREAD</span>'
                    f'<span style="font-family:\'JetBrains Mono\',mono;color:#4a5568;font-size:.85rem;">${spread:.4f}</span></div>'
                    f'</div>'
                )
                st.markdown(ob_html, unsafe_allow_html=True)

        with of3:
            with state.acquire():
                slips = list(state.slippage_records[-20:])

            slip_html = '<div class="panel">'
            slip_html += '<div style="color:#4a5568;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;margin-bottom:.4rem;">Slippage Tracker</div>'
            if slips:
                for lbl, val in [
                    ("Avg",   f"${np.mean(slips):.4f}"),
                    ("Max",   f"${max(slips):.4f}"),
                    ("Total", f"${sum(slips):.4f}"),
                ]:
                    slip_html += (
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:.2rem 0;border-bottom:1px solid #161d27;">'
                        f'<span style="color:#4a5568;font-size:.68rem;">{lbl}</span>'
                        f'<span style="font-family:\'JetBrains Mono\',mono;color:#8b949e;'
                        f'font-size:.8rem;">{val}</span></div>'
                    )
            else:
                slip_html += '<div style="color:#21262d;font-size:.75rem;font-family:\'JetBrains Mono\',mono;">No fills yet</div>'
            slip_html += "</div>"
            st.markdown(slip_html, unsafe_allow_html=True)

        # ── Row 5: Log ────────────────────────────────────────────────────
        st.markdown(sec_hdr("Live Log"), unsafe_allow_html=True)

        with state.acquire():
            logs = list(state.log_entries)

        log_html = '<div class="log-terminal">'
        if logs:
            log_html += "".join(log_row(e) for e in reversed(logs))
        else:
            log_html += '<span style="color:#21262d;">Waiting for events…</span>'
        log_html += "</div>"
        st.markdown(log_html, unsafe_allow_html=True)

        # Bottom padding
        st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

    time.sleep(1)
