# =============================================================================
# AIRISE BOT - CRYPTO FUTURES ANALYZER PRO
# =============================================================================

from __future__ import annotations
import requests
import json
import os
import re
import base64
import uuid
import textwrap
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List, Any
from datetime import datetime
import ccxt
import numpy as np
import pandas as pd
import streamlit as st
import ta
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# =============================================================================
# KONFIGURASI
# =============================================================================

BOT_NAME: str = "AIRISE BOT"
BOT_TAGLINE: str = "Crypto Futures Analyzer Pro"

LOGIN_USERNAME: str = "Swijaya07"
LOGIN_PASSWORD: str = "000000"

EXCHANGES: Dict[str, Dict[str, Any]] = {
    "OKX": {"id": ["okx"], "options": {"defaultType": "swap"}},
    "Gate.io": {"id": ["gate", "gateio"], "options": {"defaultType": "swap"}}
}

TIMEFRAMES: List[str] = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]

MTF_HIGHER: Dict[str, Tuple[str, ...]] = {
    "1m": ("5m", "15m"),
    "5m": ("15m", "1h"),
    "15m": ("1h", "4h"),
    "1h": ("4h", "1d"),
    "4h": ("1d", "1w"),
    "1d": ("1d", "1w"),
    "1w": ("1d", "1w")
}

POPULAR_SYMBOLS: List[str] = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT"
]

SCANNER_DEFAULT_SYMBOLS: List[str] = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "TON/USDT",
    "DOT/USDT", "TRX/USDT", "MATIC/USDT", "LTC/USDT", "SHIB/USDT",
    "NEAR/USDT", "APT/USDT", "ARB/USDT", "OP/USDT", "SUI/USDT",
]

SCANNER_MAX_SYMBOLS: int = 150
MICIN_PRICE_MIN: float = 0.0
MICIN_PRICE_MAX: float = 5.0
MICIN_DEFAULT_COUNT: int = 100

# =============================================================================
# PENYIMPANAN PERMANEN
# =============================================================================
_BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
TRADE_HISTORY_DIR: str = os.path.join(_BASE_DIR, "airise_data")
TRADE_HISTORY_FILE: str = os.path.join(TRADE_HISTORY_DIR, "trade_history.json")
WALLET_STATE_FILE: str = os.path.join(TRADE_HISTORY_DIR, "wallet_state.json")
MAX_HISTORY_RECORDS: int = 3000
DEMO_DEFAULT_BALANCE: float = 10000.0
MAINTENANCE_MARGIN_RATE: float = 0.005

# =============================================================================
# LOGO
# =============================================================================
LOGO_FILENAME: str = "airise_logo.png"
LOGO_CANDIDATE_PATHS: List[str] = [
    os.path.join(_BASE_DIR, "assets", LOGO_FILENAME),
    os.path.join(_BASE_DIR, LOGO_FILENAME),
    os.path.join(os.getcwd(), "assets", LOGO_FILENAME),
    os.path.join(os.getcwd(), LOGO_FILENAME),
]

_FALLBACK_ROBOT_SVG: str = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" style="height:{h}px;width:auto;display:block;{extra}">
  <defs>
    <linearGradient id="airiseGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2979ff"/>
      <stop offset="100%" stop-color="#00e5ff"/>
    </linearGradient>
  </defs>
  <rect x="14" y="22" width="36" height="28" rx="8" fill="url(#airiseGrad)" opacity="0.18" stroke="url(#airiseGrad)" stroke-width="2.5"/>
  <circle cx="25" cy="36" r="4.2" fill="#00e5ff"/>
  <circle cx="39" cy="36" r="4.2" fill="#2979ff"/>
  <rect x="27" y="44" width="10" height="3" rx="1.5" fill="#6fa8dc"/>
  <line x1="32" y1="22" x2="32" y2="12" stroke="url(#airiseGrad)" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="32" cy="9" r="3.2" fill="#00e5ff"/>
  <rect x="8" y="30" width="6" height="12" rx="3" fill="#2979ff" opacity="0.7"/>
  <rect x="50" y="30" width="6" height="12" rx="3" fill="#00e5ff" opacity="0.7"/>
</svg>
"""

@st.cache_data(show_spinner=False)
def _load_logo_base64() -> Optional[str]:
    for path in LOGO_CANDIDATE_PATHS:
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            continue
    return None

def render_logo_img(height_px: int = 64, extra_style: str = "") -> str:
    b64 = _load_logo_base64()
    if not b64:
        return _FALLBACK_ROBOT_SVG.format(h=height_px, extra=extra_style)
    return (f'<img src="data:image/png;base64,{b64}" '
            f'style="height:{height_px}px; width:auto; display:block; {extra_style}" alt="AIRISE logo" />')

def logo_file_found() -> bool:
    return _load_logo_base64() is not None

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_price(price: Optional[float], symbol: str = "") -> str:
    if price is None:
        return "-"
    try:
        if np.isnan(price):
            return "-"
    except TypeError:
        return "-"
    if price == 0:
        return "0"

    if "DOGE" in symbol or "SHIB" in symbol or "PEPE" in symbol:
        decimals = 8
    elif "XRP" in symbol or "ADA" in symbol:
        decimals = 4
    elif "SOL" in symbol or "BNB" in symbol or "ETH" in symbol:
        decimals = 2
    elif price >= 1000:
        decimals = 2
    elif price >= 100:
        decimals = 2
    elif price >= 1:
        decimals = 3
    elif price >= 0.01:
        decimals = 4
    elif price >= 0.0001:
        decimals = 6
    else:
        decimals = 8

    try:
        return f"{price:,.{decimals}f}"
    except (ValueError, TypeError):
        return f"{price:.2f}"

def format_number(num: Optional[float], decimals: int = 2) -> str:
    if num is None:
        return "0"
    try:
        if np.isnan(num):
            return "0"
        return f"{num:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(num)

def format_percentage(num: Optional[float]) -> str:
    if num is None:
        return "0.00%"
    try:
        if np.isnan(num):
            return "0.00%"
        return f"{num:+.2f}%"
    except (ValueError, TypeError):
        return f"{num:.2f}%"

def format_volume(volume: Optional[float]) -> str:
    if volume is None:
        return "-"
    try:
        if np.isnan(volume):
            return "-"
    except TypeError:
        return "-"
    try:
        if volume >= 1e9:
            return f"{volume/1e9:.2f}B"
        if volume >= 1e6:
            return f"{volume/1e6:.2f}M"
        if volume >= 1e3:
            return f"{volume/1e3:.2f}K"
        return f"{volume:.2f}"
    except (ValueError, TypeError):
        return str(volume)

def safe_pct_change(target: Optional[float], base: Optional[float]) -> float:
    if target is None or base is None or base == 0:
        return 0.0
    try:
        if np.isnan(target) or np.isnan(base):
            return 0.0
    except TypeError:
        return 0.0
    return (target / base - 1) * 100

def send_telegram_message(message: str, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False

# =============================================================================
# EXCHANGE FUNCTIONS
# =============================================================================

def _resolve_ccxt_class(candidate_ids: List[str]) -> Any:
    for cid in candidate_ids:
        cls = getattr(ccxt, cid, None)
        if cls is not None:
            return cls
    raise AttributeError(
        f"Tidak ditemukan exchange ccxt dengan id: {', '.join(candidate_ids)}. "
        f"Kemungkinan versi ccxt yang terpasang sudah berganti nama exchange ini — "
        f"cek 'pip show ccxt' dan daftar exchange terbaru di dokumentasi ccxt."
    )

@st.cache_resource(show_spinner=False)
def get_exchange(exchange_name: str) -> Any:
    cfg = EXCHANGES.get(exchange_name, next(iter(EXCHANGES.values())))
    exchange_class = _resolve_ccxt_class(cfg["id"])
    return exchange_class({"enableRateLimit": True, "options": cfg["options"]})

@st.cache_data(ttl=3600, show_spinner=False)
def get_symbols(exchange_name: str) -> List[str]:
    exchange = get_exchange(exchange_name)
    markets = exchange.load_markets()
    return sorted([
        s for s, m in markets.items()
        if (m.get("swap") or m.get("future")) and m.get("quote") == "USDT" and m.get("active", True)
    ])

def resolve_symbol(target: str, all_symbols: List[str]) -> Optional[str]:
    if target in all_symbols:
        return target
    base = target.split("/")[0]
    for s in all_symbols:
        if s.startswith(f"{base}/USDT"):
            return s
    return None

# Semua pemanggil get_ohlcv() untuk keperluan Wallet Trading (form order, reconcile
# posisi, auto-bot) WAJIB memakai limit yang SAMA persis untuk symbol+timeframe yang
# sama, supaya ketiganya berbagi SATU entri cache & satu request jaringan per siklus
# refresh — bukan tiga request terpisah (yang sebelumnya memicu rate-limit exchange
# seperti Gate.io "TOO_MANY_REQUESTS").
WALLET_OHLCV_LIMIT: int = 300

@st.cache_data(ttl=60, show_spinner=False)
def get_ohlcv(exchange_name: str, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    try:
        exchange = get_exchange(exchange_name)
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        msg = str(e)
        if "TOO_MANY_REQUESTS" in msg or "Rate Limit" in msg or "rate limit" in msg:
            st.warning(
                f"⏳ Rate limit exchange tercapai untuk {symbol} ({timeframe}) — data akan dicoba lagi otomatis "
                "beberapa saat lagi. Kalau sering muncul, coba perbesar interval Auto-Refresh di sidebar/panel."
            )
        else:
            st.error(f"Error mengambil data OHLCV: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=10, show_spinner=False)
def get_live_data(exchange_name: str, symbol: str) -> Dict[str, Any]:
    try:
        exchange = get_exchange(exchange_name)
        ticker = exchange.fetch_ticker(symbol)
        return {
            'price': ticker.get('last', 0) or 0,
            'change': ticker.get('percentage', 0) or 0,
            'high': ticker.get('high', 0) or 0,
            'low': ticker.get('low', 0) or 0,
            'volume': ticker.get('quoteVolume', 0) or 0
        }
    except Exception:
        return {'price': 0, 'change': 0, 'high': 0, 'low': 0, 'volume': 0}

@st.cache_data(ttl=60, show_spinner=False)
def get_all_tickers_bulk(exchange_name: str) -> Dict[str, Dict[str, Any]]:
    exchange = get_exchange(exchange_name)
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        st.warning(f"Gagal mengambil bulk ticker ({e}). Coba lagi nanti.")
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for sym, t in tickers.items():
        price = t.get("last") or t.get("close")
        if price is None:
            continue
        out[sym] = {
            "price": float(price),
            "change": t.get("percentage", 0) or 0.0,
            "quote_volume": t.get("quoteVolume", 0) or 0.0,
            "base_volume": t.get("baseVolume", 0) or 0.0,
        }
    return out

@st.cache_data(ttl=120, show_spinner=False)
def get_funding_rate(exchange_name: str, symbol: str) -> Optional[float]:
    try:
        exchange = get_exchange(exchange_name)
        if not exchange.has.get("fetchFundingRate"):
            return None
        data = exchange.fetch_funding_rate(symbol)
        rate = data.get("fundingRate")
        return float(rate) if rate is not None else None
    except Exception:
        return None

def find_micin_candidates(exchange_name: str, price_min: float = MICIN_PRICE_MIN,
                           price_max: float = MICIN_PRICE_MAX,
                           count: int = MICIN_DEFAULT_COUNT) -> List[str]:
    try:
        all_symbols = set(get_symbols(exchange_name))
    except Exception:
        all_symbols = set()

    tickers = get_all_tickers_bulk(exchange_name)
    if not tickers:
        return []

    candidates: List[Tuple[str, float, float]] = []
    for sym, t in tickers.items():
        if all_symbols and sym not in all_symbols:
            continue
        if not sym.endswith("USDT") and "/USDT" not in sym:
            continue
        price = t["price"]
        if price <= 0 or price < price_min or price > price_max:
            continue
        candidates.append((sym, price, t["quote_volume"]))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return [c[0] for c in candidates[:count]]

# =============================================================================
# MARKET CAP / TRENDING (CoinGecko)
# =============================================================================

COINGECKO_MARKETS_URL: str = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_TRENDING_URL: str = "https://api.coingecko.com/api/v3/search/trending"

@st.cache_data(ttl=300, show_spinner=False)
def get_market_overview(vs_currency: str = "usd", per_page: int = 100) -> pd.DataFrame:
    try:
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d",
        }
        r = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        return pd.DataFrame({"_error": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def get_trending_coins() -> List[Dict[str, Any]]:
    try:
        r = requests.get(COINGECKO_TRENDING_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        return [c.get("item", {}) for c in data.get("coins", [])]
    except Exception:
        return []

def render_market_overview_ui() -> None:
    st.markdown("### 📈 Market Cap & Trending (Global — CoinGecko)")
    st.caption(
        "Data ranking market cap & coin yang sedang trending diambil dari CoinGecko (sumber publik, "
        "berlaku global — bukan cuma dari exchange futures OKX/Gate.io kamu). Berguna untuk melihat "
        "coin mana yang 'lagi hype' sebelum dicek lebih dalam di Coin Scanner / Grafik & Analisa."
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        per_page = st.slider("Jumlah coin (ranking market cap)", 20, 250, 100, 10, key="mc_per_page")
    with col_b:
        st.write("")
        refresh_mc = st.button("🔄 Refresh Data", use_container_width=True, key="mc_refresh_btn")
    if refresh_mc:
        get_market_overview.clear()
        get_trending_coins.clear()

    df = get_market_overview(per_page=per_page)
    if df.empty or "_error" in df.columns:
        err = df["_error"].iloc[0] if "_error" in df.columns and not df.empty else "Tidak ada data."
        st.warning(
            f"⚠️ Gagal mengambil data CoinGecko ({err}). Ini biasanya karena koneksi internet keluar "
            "(egress) diblokir di lingkungan saat ini, atau rate-limit publik CoinGecko sedang penuh. "
            "Di server deployment kamu sendiri (mis. Streamlit Cloud/VPS) fitur ini akan jalan normal "
            "selama ada akses internet keluar ke api.coingecko.com."
        )
        return

    show = df[[
        "market_cap_rank", "symbol", "name", "current_price", "market_cap",
        "total_volume", "price_change_percentage_1h_in_currency",
        "price_change_percentage_24h_in_currency", "price_change_percentage_7d_in_currency",
    ]].copy()
    show.columns = ["Rank", "Symbol", "Nama", "Harga", "Market Cap", "Volume 24h", "1h %", "24h %", "7d %"]
    show["Symbol"] = show["Symbol"].str.upper()
    show["Harga"] = show["Harga"].apply(lambda x: f"${format_price(x)}")
    show["Market Cap"] = show["Market Cap"].apply(lambda x: f"${format_volume(x)}")
    show["Volume 24h"] = show["Volume 24h"].apply(lambda x: f"${format_volume(x)}")
    for c in ["1h %", "24h %", "7d %"]:
        show[c] = show[c].apply(lambda x: format_percentage(x) if pd.notna(x) else "-")

    top_gainers = df.sort_values("price_change_percentage_24h_in_currency", ascending=False).head(10)
    top_losers = df.sort_values("price_change_percentage_24h_in_currency", ascending=True).head(10)

    m1, m2 = st.columns(2)
    with m1:
        st.markdown("#### 🚀 Top Gainer 24h")
        g = top_gainers[["symbol", "current_price", "price_change_percentage_24h_in_currency"]].copy()
        g.columns = ["Symbol", "Harga", "24h %"]
        g["Symbol"] = g["Symbol"].str.upper()
        g["Harga"] = g["Harga"].apply(lambda x: f"${format_price(x)}")
        g["24h %"] = g["24h %"].apply(format_percentage)
        st.dataframe(g, use_container_width=True, hide_index=True, height=280)
    with m2:
        st.markdown("#### 📉 Top Loser 24h")
        l = top_losers[["symbol", "current_price", "price_change_percentage_24h_in_currency"]].copy()
        l.columns = ["Symbol", "Harga", "24h %"]
        l["Symbol"] = l["Symbol"].str.upper()
        l["Harga"] = l["Harga"].apply(lambda x: f"${format_price(x)}")
        l["24h %"] = l["24h %"].apply(format_percentage)
        st.dataframe(l, use_container_width=True, hide_index=True, height=280)

    st.markdown("---")
    st.markdown("#### 🔥 Sedang Trending (Paling Banyak Dicari)")
    trending = get_trending_coins()
    if trending:
        base_syms: List[str] = []
        t_cols = st.columns(5)
        for i, item in enumerate(trending[:10]):
            sym = (item.get("symbol") or "").upper()
            name = item.get("name", "-")
            rank = item.get("market_cap_rank", "-")
            if sym:
                base_syms.append(sym)
            with t_cols[i % 5]:
                st.markdown(
                    f"""<div style="border:1px solid rgba(0,229,255,0.25); border-radius:10px;
                    padding:8px 10px; margin-bottom:8px; background:rgba(255,255,255,0.03);">
                    <div style="font-weight:700; color:#00e5ff; font-size:12px;">#{i+1} {sym}</div>
                    <div style="font-size:10.5px; color:#8aa0b5;">{name}</div>
                    <div style="font-size:10px; color:#5c7188;">MCap Rank: {rank}</div>
                    </div>""", unsafe_allow_html=True
                )
        jc1, jc2 = st.columns([1, 2])
        with jc1:
            if st.button("📥 Kirim Trending ke Coin Scanner", use_container_width=True, key="send_trending_to_scanner"):
                symbols_str = ", ".join(f"{s}/USDT" for s in dict.fromkeys(base_syms))
                st.session_state["scanner_symbols_input"] = symbols_str
                st.session_state.active_section = "scanner"
                st.rerun()
        with jc2:
            st.caption("Coin trending akan dimasukkan otomatis ke daftar Coin Scanner supaya bisa langsung dianalisa teknikal-nya.")
    else:
        st.caption("Data trending tidak tersedia saat ini.")

    st.markdown("---")
    st.markdown(f"#### 📋 Ranking Market Cap (Top {len(show)})")
    st.dataframe(show, use_container_width=True, hide_index=True, height=420)
    st.caption("💡 Bukan nasihat keuangan. Market cap besar & trending tidak selalu berarti aman untuk entry — tetap DYOR.")

# =============================================================================
# INDIKATOR TEKNIKAL
# =============================================================================

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["ema_9"] = ta.trend.EMAIndicator(result["close"], window=9).ema_indicator()
    result["ema_21"] = ta.trend.EMAIndicator(result["close"], window=21).ema_indicator()
    result["ema_50"] = ta.trend.EMAIndicator(result["close"], window=50).ema_indicator()
    result["ema_200"] = ta.trend.EMAIndicator(result["close"], window=200).ema_indicator()

    result["rsi_14"] = ta.momentum.RSIIndicator(result["close"], window=14).rsi()

    macd = ta.trend.MACD(result["close"], window_slow=26, window_fast=12, window_sign=9)
    result["macd"] = macd.macd()
    result["macd_signal"] = macd.macd_signal()
    result["macd_hist"] = macd.macd_diff()

    bb = ta.volatility.BollingerBands(result["close"], window=20, window_dev=2)
    result["bb_upper"] = bb.bollinger_hband()
    result["bb_mid"] = bb.bollinger_mavg()
    result["bb_lower"] = bb.bollinger_lband()

    result["atr_14"] = ta.volatility.AverageTrueRange(
        result["high"], result["low"], result["close"], window=14
    ).average_true_range()

    stoch = ta.momentum.StochasticOscillator(
        result["high"], result["low"], result["close"], window=14, smooth_window=3
    )
    result["stoch_k"] = stoch.stoch()
    result["stoch_d"] = stoch.stoch_signal()

    result["volume_ma"] = result["volume"].rolling(window=20).mean()
    result["volume_ratio"] = result["volume"] / result["volume_ma"].replace(0, np.nan)

    result["adx"] = ta.trend.ADXIndicator(result["high"], result["low"], result["close"], window=14).adx()

    return result

# =============================================================================
# SIGNAL ENGINE
# =============================================================================

@dataclass
class Signal:
    direction: str
    score: float
    confidence: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    ema_status: str = "Neutral"
    rsi_value: float = 0.0
    rsi_status: str = "Neutral"
    macd_status: str = "Neutral"
    bb_status: str = "Neutral"
    stoch_status: str = "Neutral"
    volume_status: str = "Neutral"
    trend_strength: str = "Weak"
    adx_value: float = 0.0
    reasons: List[str] = field(default_factory=list)
    is_actionable: bool = False
    bias: str = "Neutral"
    raw_score: float = 0.0
    mtf_status: str = "Not checked"
    mtf_aligned: Optional[bool] = None
    funding_rate: Optional[float] = None

def analyze_single_timeframe(df: pd.DataFrame) -> Signal:
    if len(df) < 2:
        return Signal("HOLD", 0.0, "Rendah", 0.0, 0.0, 0.0, 0.0, reasons=["Data tidak cukup"])

    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 0.0
    reasons: List[str] = []
    ema_status = "Neutral"
    rsi_status = "Neutral"
    macd_status = "Neutral"
    bb_status = "Neutral"
    stoch_status = "Neutral"
    volume_status = "Neutral"
    trend_strength = "Weak"
    adx_value = 0.0
    rsi_value = 50.0

    if all(pd.notna([last.get("ema_21"), last.get("ema_50")])):
        if last["close"] > last["ema_21"] > last["ema_50"]:
            score += 2.0
            ema_status = "Bullish"
            reasons.append("✅ EMA Bullish: Price > EMA21 > EMA50")
        elif last["close"] < last["ema_21"] < last["ema_50"]:
            score -= 2.0
            ema_status = "Bearish"
            reasons.append("❌ EMA Bearish: Price < EMA21 < EMA50")

    if all(pd.notna([prev.get("ema_9"), prev.get("ema_21"), last.get("ema_9"), last.get("ema_21")])):
        if prev["ema_9"] <= prev["ema_21"] and last["ema_9"] > last["ema_21"]:
            score += 1.5
            reasons.append("📈 Golden Cross: EMA9 > EMA21")
        elif prev["ema_9"] >= prev["ema_21"] and last["ema_9"] < last["ema_21"]:
            score -= 1.5
            reasons.append("📉 Death Cross: EMA9 < EMA21")

    if pd.notna(last.get("ema_200")):
        if last["close"] > last["ema_200"]:
            score += 0.5
            reasons.append("📈 Above EMA200")
        else:
            score -= 0.5
            reasons.append("📉 Below EMA200")

    if not np.isnan(last.get("rsi_14", np.nan)):
        rsi_value = last["rsi_14"]
        if rsi_value <= 20:
            score += 2.5
            rsi_status = "Extreme Oversold"
            reasons.append(f"🔴 RSI Extreme Oversold ({rsi_value:.1f})")
        elif rsi_value <= 30:
            score += 2.0
            rsi_status = "Oversold"
            reasons.append(f"🟡 RSI Oversold ({rsi_value:.1f})")
        elif rsi_value >= 80:
            score -= 2.5
            rsi_status = "Extreme Overbought"
            reasons.append(f"🔴 RSI Extreme Overbought ({rsi_value:.1f})")
        elif rsi_value >= 70:
            score -= 2.0
            rsi_status = "Overbought"
            reasons.append(f"🟡 RSI Overbought ({rsi_value:.1f})")
        elif rsi_value >= 50:
            score += 0.5
            rsi_status = "Bullish Bias"
        else:
            score -= 0.5
            rsi_status = "Bearish Bias"

    if all(pd.notna([prev.get("macd"), prev.get("macd_signal"), last.get("macd"), last.get("macd_signal")])):
        if prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]:
            score += 2.0
            macd_status = "Bullish Crossover"
            reasons.append("📈 MACD Bullish Crossover")
        elif prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]:
            score -= 2.0
            macd_status = "Bearish Crossover"
            reasons.append("📉 MACD Bearish Crossover")

    if not np.isnan(last.get("macd_hist", np.nan)):
        if last["macd_hist"] > 0:
            score += 0.5
            if macd_status == "Neutral":
                macd_status = "Bullish"
        else:
            score -= 0.5
            if macd_status == "Neutral":
                macd_status = "Bearish"

    if all(pd.notna([last.get("bb_upper"), last.get("bb_lower"), last.get("close")])):
        bb_width = last["bb_upper"] - last["bb_lower"]
        if bb_width > 0:
            position = (last["close"] - last["bb_lower"]) / bb_width
            if position <= 0.05:
                score += 2.0
                bb_status = "Extreme Oversold"
                reasons.append("🔴 At BB Lower Band")
            elif position <= 0.2:
                score += 1.5
                bb_status = "Oversold"
                reasons.append("🟡 Near BB Lower Band")
            elif position >= 0.95:
                score -= 2.0
                bb_status = "Extreme Overbought"
                reasons.append("🔴 At BB Upper Band")
            elif position >= 0.8:
                score -= 1.5
                bb_status = "Overbought"
                reasons.append("🟡 Near BB Upper Band")
            elif position > 0.5:
                score += 0.3
                bb_status = "Bullish"
            else:
                score -= 0.3
                bb_status = "Bearish"

    if all(pd.notna([last.get("stoch_k"), last.get("stoch_d")])):
        k = last["stoch_k"]
        d = last["stoch_d"]
        if k < 20:
            score += 1.0
            stoch_status = "Oversold"
            if k > d:
                score += 0.5
                stoch_status = "Bullish Crossover"
                reasons.append("📈 Stochastic Bullish Crossover")
        elif k > 80:
            score -= 1.0
            stoch_status = "Overbought"
            if k < d:
                score -= 0.5
                stoch_status = "Bearish Crossover"
                reasons.append("📉 Stochastic Bearish Crossover")
        elif k > 50:
            score += 0.3
            stoch_status = "Bullish"
        else:
            score -= 0.3
            stoch_status = "Bearish"

    if not np.isnan(last.get("volume_ratio", np.nan)):
        vol_ratio = last["volume_ratio"]
        if vol_ratio > 2.0:
            score += 1.0 if score > 0 else -1.0
            volume_status = "High Volume"
            reasons.append(f"📊 High Volume ({vol_ratio:.1f}x)")
        elif vol_ratio > 1.5:
            score += 0.5 if score > 0 else -0.5
            volume_status = "Above Average"
            reasons.append(f"📊 Above Avg Volume ({vol_ratio:.1f}x)")
        elif vol_ratio < 0.5:
            volume_status = "Low Volume"

    if not np.isnan(last.get("adx", np.nan)):
        adx_value = last["adx"]
        if adx_value > 40:
            trend_strength = "Very Strong"
            score += 0.5 if score > 0 else -0.5
            reasons.append(f"💪 ADX {adx_value:.1f}")
        elif adx_value > 25:
            trend_strength = "Strong"
            score += 0.3 if score > 0 else -0.3
            reasons.append(f"💪 ADX {adx_value:.1f}")
        elif adx_value > 20:
            trend_strength = "Moderate"
        else:
            trend_strength = "Weak"
            reasons.append(f"ADX {adx_value:.1f}")

    if score >= 3.0:
        direction = "BUY"
    elif score <= -3.0:
        direction = "SELL"
    else:
        direction = "HOLD"

    if abs(score) >= 5.0:
        confidence = "Sangat Tinggi"
    elif abs(score) >= 4.0:
        confidence = "Tinggi"
    elif abs(score) >= 3.0:
        confidence = "Sedang"
    elif abs(score) >= 1.5:
        confidence = "Rendah"
    else:
        confidence = "Sangat Rendah"

    entry = float(last["close"])
    atr = float(last["atr_14"]) if not np.isnan(last.get("atr_14", np.nan)) else entry * 0.01
    atr = atr if atr > 0 else entry * 0.01

    is_actionable = direction in ("BUY", "SELL")
    if direction == "BUY":
        bias = "Bullish"
        sl = entry - 1.5 * atr
        risk = entry - sl
        tp1 = entry + 1.5 * risk
        tp2 = entry + 3.0 * risk
    elif direction == "SELL":
        bias = "Bearish"
        sl = entry + 1.5 * atr
        risk = sl - entry
        tp1 = entry - 1.5 * risk
        tp2 = entry - 3.0 * risk
    else:
        bias = "Bullish (lemah)" if score > 0 else ("Bearish (lemah)" if score < 0 else "Netral")
        if score >= 0:
            sl = entry - 1.5 * atr
            risk = entry - sl
            tp1 = entry + 1.5 * risk
            tp2 = entry + 3.0 * risk
        else:
            sl = entry + 1.5 * atr
            risk = sl - entry
            tp1 = entry - 1.5 * risk
            tp2 = entry - 3.0 * risk
        if not reasons:
            reasons.append("⚠️ HOLD - Wait for confirmation")

    return Signal(
        direction=direction, score=round(score, 2), confidence=confidence,
        entry=entry, sl=sl, tp1=tp1, tp2=tp2, ema_status=ema_status,
        rsi_value=rsi_value, rsi_status=rsi_status, macd_status=macd_status,
        bb_status=bb_status, stoch_status=stoch_status, volume_status=volume_status,
        trend_strength=trend_strength, adx_value=adx_value, reasons=reasons[:15],
        is_actionable=is_actionable, bias=bias, raw_score=round(score, 2)
    )


def apply_mtf_confirmation(signal: Signal, exchange_name: str, symbol: str, timeframe: str,
                            limit: int = 250) -> Signal:
    higher_tfs = MTF_HIGHER.get(timeframe)
    if not higher_tfs:
        return signal
    htf = higher_tfs[0]
    try:
        htf_df = get_ohlcv(exchange_name, symbol, htf, limit)
        if htf_df.empty or len(htf_df) < 55:
            signal.mtf_status = f"Data {htf} tidak cukup — MTF dilewati"
            return signal
        htf_df = add_indicators(htf_df)
        htf_signal = analyze_single_timeframe(htf_df)
    except Exception:
        signal.mtf_status = "Gagal ambil data timeframe lebih tinggi"
        return signal

    if htf_signal.direction == "HOLD":
        signal.mtf_status = f"HTF {htf} netral (score {htf_signal.score:+.1f}) — tidak ada konfirmasi tambahan"
        signal.mtf_aligned = None
        return signal

    aligned = (signal.direction == htf_signal.direction) or (
        signal.direction == "HOLD" and (
            (signal.raw_score > 0 and htf_signal.direction == "BUY") or
            (signal.raw_score < 0 and htf_signal.direction == "SELL")
        )
    )

    if aligned:
        signal.score = round(signal.score + np.sign(signal.score or htf_signal.score) * 1.0, 2) if signal.score != 0 else signal.score
        signal.mtf_status = f"✅ Selaras dengan {htf} ({htf_signal.direction}, score {htf_signal.score:+.1f})"
        signal.mtf_aligned = True
        signal.reasons = (signal.reasons + [f"✅ MTF {htf} searah ({htf_signal.direction})"])[:15]
    else:
        signal.mtf_status = f"⚠️ Berlawanan dengan {htf} ({htf_signal.direction}, score {htf_signal.score:+.1f})"
        signal.mtf_aligned = False
        signal.reasons = (signal.reasons + [f"⚠️ MTF {htf} berlawanan ({htf_signal.direction}) — sinyal didinginkan"])[:15]
        if signal.direction in ("BUY", "SELL"):
            signal.direction = "HOLD"
            signal.is_actionable = False
            signal.confidence = "Rendah (konflik MTF)"

    return signal


def compute_pump_score(df: pd.DataFrame) -> Tuple[float, List[str]]:
    if len(df) < 25:
        return 0.0, []

    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3] if len(df) >= 3 else prev
    score = 0.0
    tags: List[str] = []

    vol_ratio = last.get("volume_ratio", np.nan)
    if pd.notna(vol_ratio):
        if vol_ratio >= 3.0:
            score += 3.0
            tags.append(f"🚀 Volume meledak {vol_ratio:.1f}x rata-rata")
        elif vol_ratio >= 2.0:
            score += 2.0
            tags.append(f"📊 Volume tinggi {vol_ratio:.1f}x rata-rata")
        elif vol_ratio >= 1.5:
            score += 1.0
            tags.append(f"📊 Volume di atas rata-rata {vol_ratio:.1f}x")

    rsi = last.get("rsi_14", np.nan)
    rsi_prev = prev.get("rsi_14", np.nan)
    if pd.notna(rsi) and pd.notna(rsi_prev):
        if 35 <= rsi <= 68 and rsi > rsi_prev:
            score += 2.0
            tags.append(f"📈 RSI bangkit dari area rendah ({rsi_prev:.0f} → {rsi:.0f})")
        elif rsi > 70:
            score -= 1.0

    hist = last.get("macd_hist", np.nan)
    hist_prev = prev.get("macd_hist", np.nan)
    hist_prev2 = prev2.get("macd_hist", np.nan)
    if pd.notna(hist) and pd.notna(hist_prev) and pd.notna(hist_prev2):
        if hist > hist_prev > hist_prev2:
            score += 2.0
            tags.append("📈 MACD histogram menguat 2 candle beruntun")
        elif hist > hist_prev and hist_prev <= 0 < hist:
            score += 1.5
            tags.append("📈 MACD histogram baru saja berbalik positif")

    bb_mid = last.get("bb_mid", np.nan)
    bb_mid_prev = prev.get("bb_mid", np.nan)
    if pd.notna(bb_mid) and pd.notna(bb_mid_prev):
        if last["close"] > bb_mid and prev["close"] <= bb_mid_prev:
            score += 1.5
            tags.append("💥 Breakout di atas BB Midline")

    if len(df) >= 4:
        c0, c1, c2, c3 = df["close"].iloc[-4], df["close"].iloc[-3], df["close"].iloc[-2], df["close"].iloc[-1]
        chg1 = safe_pct_change(c1, c0)
        chg2 = safe_pct_change(c2, c1)
        chg3 = safe_pct_change(c3, c2)
        if chg3 > 0 and chg2 > 0 and chg3 >= chg2 >= chg1:
            score += 1.5
            tags.append("⚡ Momentum harga mempercepat 3 candle terakhir")

    return round(min(score, 10.0), 2), tags


# =============================================================================
# PENJELASAN DETAIL UNTUK "REASONS"
# =============================================================================

def reason_sentiment(reason: str) -> str:
    bearish_keywords = ["Bearish", "Death Cross", "Overbought", "Below EMA200", "Upper Band", "berlawanan"]
    bullish_keywords = ["Bullish", "Golden Cross", "Oversold", "Above EMA200", "Lower Band", "searah"]
    for kw in bearish_keywords:
        if kw in reason:
            return "bearish"
    for kw in bullish_keywords:
        if kw in reason:
            return "bullish"
    return "neutral"

def reason_explanation(reason: str) -> str:
    checks: List[Tuple[str, str]] = [
        ("EMA Bullish",
         "Harga saat ini berada di atas EMA21, dan EMA21 berada di atas EMA50 (Price > EMA21 > EMA50). "
         "Susunan rapi seperti ini disebut \"stacked bullish\" — menandakan tren jangka pendek dan menengah "
         "kompak mengarah naik. Semakin rapi urutannya, semakin kuat indikasi tren naik yang sedang berlangsung."),
        ("EMA Bearish",
         "Harga berada di bawah EMA21, dan EMA21 di bawah EMA50 (Price < EMA21 < EMA50) — susunan "
         "\"stacked bearish\". Ini menandakan tren turun yang konsisten di berbagai kerangka waktu "
         "pendek-menengah, sering dipakai sebagai konfirmasi bahwa tekanan jual masih mendominasi."),
        ("Golden Cross",
         "EMA9 (rata-rata bergerak cepat) baru saja memotong ke atas EMA21 (rata-rata lebih lambat). "
         "Persilangan ini sering disebut \"Golden Cross\" jangka pendek dan biasanya jadi salah satu sinyal "
         "awal bahwa momentum mulai berbalik naik."),
        ("Death Cross",
         "EMA9 baru saja memotong ke bawah EMA21 — disebut \"Death Cross\" jangka pendek. Ini mengindikasikan "
         "momentum jangka pendek mulai melemah dan tekanan jual mulai mengambil alih."),
        ("Above EMA200",
         "Harga berada di atas EMA200, garis rata-rata jangka sangat panjang yang sering dipakai untuk "
         "menentukan tren besar (bull market vs bear market). Posisi di atas EMA200 umumnya dianggap sebagai "
         "konteks bullish jangka panjang."),
        ("Below EMA200",
         "Harga berada di bawah EMA200. Ini biasanya menandakan konteks bearish jangka panjang, sehingga "
         "sinyal beli jangka pendek sebaiknya lebih diwaspadai karena melawan arah tren besar."),
        ("RSI Extreme Oversold",
         "RSI berada jauh di bawah 20 — kondisi jenuh jual ekstrem. Artinya harga sudah turun sangat cepat "
         "dalam waktu singkat, sehingga peluang terjadi technical rebound (pantulan naik) meningkat. Namun "
         "perlu diingat, RSI ekstrem bisa bertahan lama saat tren turun sangat kuat — jangan asal beli hanya "
         "karena RSI rendah."),
        ("RSI Oversold",
         "RSI di bawah 30 menandakan momentum jual sudah cukup jenuh. Area ini sering dipakai trader sebagai "
         "potensi titik pembalikan naik, tapi sebaiknya dikombinasikan dengan indikator lain untuk konfirmasi."),
        ("RSI Extreme Overbought",
         "RSI berada di atas 80 — kondisi jenuh beli ekstrem. Harga naik sangat cepat sehingga risiko "
         "koreksi/turun dalam waktu dekat meningkat."),
        ("RSI Overbought",
         "RSI di atas 70 menandakan momentum beli mulai jenuh. Bisa jadi sinyal peringatan bahwa kenaikan "
         "harga mulai kehabisan tenaga."),
        ("MACD Bullish Crossover",
         "Garis MACD baru saja memotong ke atas garis Signal-nya. Persilangan ini adalah salah satu sinyal "
         "momentum paling umum dipakai untuk menandai potensi awal tren naik."),
        ("MACD Bearish Crossover",
         "Garis MACD memotong ke bawah garis Signal-nya — indikasi momentum mulai melemah dan berpotensi "
         "berbalik turun."),
        ("At BB Lower Band",
         "Harga menyentuh atau sangat dekat dengan pita bawah Bollinger Bands. Secara statistik harga jarang "
         "bertahan lama di luar pita ini, sehingga area ini sering dianggap \"murah sementara\" dan berpotensi "
         "memantul naik."),
        ("Near BB Lower Band",
         "Harga mendekati pita bawah Bollinger Bands, menandakan harga relatif rendah dibanding volatilitas "
         "rata-rata 20 periode terakhir."),
        ("At BB Upper Band",
         "Harga menyentuh pita atas Bollinger Bands — kondisi \"mahal sementara\" secara statistik, rawan "
         "koreksi turun dalam waktu dekat."),
        ("Near BB Upper Band",
         "Harga mendekati pita atas Bollinger Bands, menandakan harga relatif tinggi dibanding volatilitas "
         "rata-rata 20 periode terakhir."),
        ("Stochastic Bullish Crossover",
         "Stochastic %K memotong ke atas %D saat berada di area oversold (di bawah 20). Kombinasi oversold + "
         "crossover naik ini sering dipakai sebagai sinyal entry beli jangka pendek."),
        ("Stochastic Bearish Crossover",
         "Stochastic %K memotong ke bawah %D saat berada di area overbought (di atas 80). Kombinasi ini "
         "sering dipakai sebagai sinyal entry jual atau keluar dari posisi beli."),
        ("High Volume",
         "Volume transaksi saat ini jauh di atas rata-rata 20 periode terakhir. Volume tinggi menambah "
         "keyakinan bahwa pergerakan harga saat ini didukung oleh partisipasi pasar yang kuat, bukan sekadar "
         "noise/pergerakan tipis."),
        ("Above Avg Volume",
         "Volume transaksi sedikit di atas rata-rata — partisipasi pasar mulai meningkat, memberi sedikit "
         "tambahan keyakinan pada arah sinyal yang terbentuk."),
        ("MTF",
         "Konfirmasi Multi-Timeframe: sinyal di timeframe utama dibandingkan dengan timeframe yang lebih besar. "
         "Kalau searah, keyakinan bertambah. Kalau berlawanan, sinyal didinginkan/diturunkan jadi HOLD karena "
         "melawan tren yang lebih besar biasanya berisiko lebih tinggi."),
        ("HOLD",
         "Skor sinyal belum cukup kuat ke arah manapun (belum mencapai ambang ±3.0), atau sinyal aktif tadi "
         "didinginkan karena berlawanan dengan timeframe lebih besar (MTF). Kombinasi indikator saat ini masih "
         "campur aduk / saling melemahkan, sehingga lebih bijak menunggu konfirmasi tambahan sebelum entry."),
        ("Data tidak cukup",
         "Jumlah candle yang tersedia belum cukup untuk menghitung seluruh indikator dengan akurat. Tambah "
         "jumlah candle di sidebar atau tunggu data lebih lengkap sebelum mengandalkan sinyal ini."),
    ]
    for keyword, explanation in checks:
        if keyword in reason:
            return explanation

    if "ADX" in reason:
        match = re.search(r"(\d+(\.\d+)?)", reason)
        adx_val = float(match.group(1)) if match else 0.0
        if adx_val > 40:
            return ("ADX di atas 40 menunjukkan tren sedang SANGAT KUAT — baik naik maupun turun. ADX sendiri "
                    "tidak menunjukkan arah, hanya kekuatan tren, jadi tetap gunakan indikator arah seperti "
                    "EMA/MACD untuk menentukan sisi mana yang dikonfirmasi.")
        elif adx_val > 25:
            return ("ADX di atas 25 menunjukkan tren sedang berlangsung dengan cukup kuat, memperbesar "
                    "keyakinan bahwa pergerakan harga saat ini bukan sekadar sideways/choppy.")
        else:
            return ("ADX di bawah 20 menandakan pasar sedang cenderung sideways / tanpa tren yang jelas. "
                    "Sinyal breakout atau reversal dalam kondisi ini punya risiko lebih tinggi untuk gagal "
                    "(false signal), jadi sebaiknya ukuran posisi lebih kecil dari biasanya atau tunggu ADX "
                    "menguat dulu.")

    return "Faktor ini turut berkontribusi pada total skor sinyal di atas."

# =============================================================================
# RIWAYAT TRADE PERMANEN (disk)
# =============================================================================

def _ensure_history_dir() -> None:
    try:
        os.makedirs(TRADE_HISTORY_DIR, exist_ok=True)
    except Exception:
        pass

def _serialize_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(trade)
    for k in ("entry_time", "exit_time"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    out.pop("current_price", None)
    return out

def load_trade_history_from_disk() -> List[Dict[str, Any]]:
    _ensure_history_dir()
    try:
        if not os.path.exists(TRADE_HISTORY_FILE):
            return []
        with open(TRADE_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def append_trade_to_disk(trade: Dict[str, Any], context: Tuple[str, str, str], mode: str) -> None:
    _ensure_history_dir()
    try:
        history = load_trade_history_from_disk()
        record = _serialize_trade(trade)
        record["exchange"] = context[0]
        record["symbol_context"] = context[1]
        record["timeframe"] = context[2]
        record["sim_mode"] = mode
        uid = f"{record.get('entry_time')}_{record.get('symbol_context')}_{record.get('direction')}_{record.get('entry_price')}"
        record["trade_uid"] = uid
        if any(h.get("trade_uid") == uid for h in history):
            return
        history.append(record)
        if len(history) > MAX_HISTORY_RECORDS:
            history = history[-MAX_HISTORY_RECORDS:]
        with open(TRADE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def trade_history_dataframe(history: List[Dict[str, Any]]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    keep = ["entry_time", "exit_time", "exchange", "symbol_context", "timeframe", "sim_mode",
            "direction", "leverage", "entry_price", "exit_price", "roi_pct", "pnl_usdt", "exit_reason"]
    keep = [c for c in keep if c in df.columns]
    return df[keep]

# =============================================================================
# WALLET ENGINE — DEMO (virtual, permanen di disk) & REAL (live via ccxt)
# =============================================================================
# Prinsip desain:
#  - "Sumber kebenaran" (source of truth) BUKAN st.session_state, melainkan file
#    JSON di disk (WALLET_STATE_FILE). Artinya posisi & saldo TIDAK bergantung
#    pada sesi browser — kalau tab/browser ditutup lalu dibuka lagi (bahkan di
#    device lain), posisi & saldo yang sama tetap terbaca dari disk.
#  - Wallet Demo = cross margin virtual: SATU saldo dipakai bersama untuk semua
#    posisi/coin, saldo bisa diedit manual kapan saja (top up / koreksi) tanpa
#    perlu tombol reset. Saldo bertambah/berkurang otomatis setiap kali posisi
#    demo ditutup (profit/loss direalisasikan ke saldo).
#  - Wallet Real = eksekusi order sungguhan ke exchange (via ccxt) memakai API
#    key. Kredensial API TIDAK disimpan ke disk (alasan keamanan) — hanya hidup
#    selama sesi browser. Posisi real sendiri tetap dicatat ke disk supaya kamu
#    tetap bisa melihat riwayat/estimasi walau sesi terputus, tapi PENGECEKAN
#    SL/TP otomatis saat app offline untuk wallet real bergantung pada apakah
#    native stop-order berhasil dipasang di exchange (lihat try_place_native_protection).
#  - "Reconcile": setiap kali halaman Wallet Trading dibuka/refresh, sistem
#    mengambil candle historis sejak posisi terakhir dicek dan mengecek apakah
#    SL/TP/Liquidation sempat tersentuh selama itu (termasuk saat offline),
#    lalu menutup posisi secara otomatis dengan harga yang sesuai. Ini membuat
#    Entry/SL/TP selalu singkron dengan apa yang "seharusnya" terjadi di pasar,
#    bukan cuma dicek waktu app sedang terbuka saja.

LIVE_CREDS_KEY: str = "live_creds"

def _default_wallet_state() -> Dict[str, Any]:
    now = datetime.now().isoformat()
    return {
        "demo": {"balance": DEMO_DEFAULT_BALANCE, "positions": [], "last_checked": now, "auto_bot": None},
        "real": {"positions": [], "last_checked": now, "auto_bot": None},
    }

def load_wallet_state() -> Dict[str, Any]:
    _ensure_history_dir()
    try:
        if not os.path.exists(WALLET_STATE_FILE):
            state = _default_wallet_state()
            save_wallet_state(state)
            return state
        with open(WALLET_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        default = _default_wallet_state()
        for k in default:
            if k not in data:
                data[k] = default[k]
        data["demo"].setdefault("positions", [])
        data["real"].setdefault("positions", [])
        data["demo"].setdefault("balance", DEMO_DEFAULT_BALANCE)
        data["demo"].setdefault("auto_bot", None)
        data["real"].setdefault("auto_bot", None)
        return data
    except Exception:
        return _default_wallet_state()

def save_wallet_state(state: Dict[str, Any]) -> None:
    _ensure_history_dir()
    try:
        with open(WALLET_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def adjust_demo_balance(state: Dict[str, Any], new_balance: float) -> None:
    state["demo"]["balance"] = float(new_balance)
    save_wallet_state(state)

def _calc_liq_price(direction: str, entry: float, leverage: int, mmr: float = MAINTENANCE_MARGIN_RATE) -> Optional[float]:
    if not entry or leverage <= 0:
        return None
    if direction == "LONG":
        return entry * (1 - 1.0 / leverage + mmr)
    else:
        return entry * (1 + 1.0 / leverage - mmr)

def _position_unrealized(pos: Dict[str, Any], mark_price: float) -> Tuple[float, float]:
    if not mark_price:
        return 0.0, 0.0
    if pos["direction"] == "LONG":
        pnl = pos["qty"] * (mark_price - pos["entry_price"])
    else:
        pnl = pos["qty"] * (pos["entry_price"] - mark_price)
    margin = pos.get("margin") or 0.0
    roi_pct = (pnl / margin * 100) if margin else 0.0
    return pnl, roi_pct

def wallet_used_margin(wallet: Dict[str, Any]) -> float:
    return sum(p.get("margin", 0.0) for p in wallet.get("positions", []))

def wallet_equity(wallet: Dict[str, Any], mark_prices: Dict[str, float]) -> float:
    total_unrl = 0.0
    for p in wallet.get("positions", []):
        mp = mark_prices.get(p["symbol"])
        if mp:
            pnl, _ = _position_unrealized(p, mp)
            total_unrl += pnl
    return wallet.get("balance", 0.0) + total_unrl

def open_position(state: Dict[str, Any], mode: str, exchange_name: str, symbol: str, timeframe: str,
                   direction: str, price: float, leverage: int, margin_usdt: float,
                   sl: float, tp1: float, tp2: float, source: str = "manual") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    wallet = state[mode]
    if mode == "demo":
        available = wallet["balance"] - wallet_used_margin(wallet)
        if margin_usdt <= 0:
            return None, "Margin harus lebih besar dari 0."
        if margin_usdt > available:
            return None, f"Margin melebihi saldo tersedia (${available:,.2f})."
    if not price or price <= 0:
        return None, "Harga live tidak tersedia."

    qty = (margin_usdt * leverage) / price
    pos = {
        "id": str(uuid.uuid4())[:8],
        "exchange": exchange_name, "symbol": symbol, "timeframe": timeframe,
        "direction": direction, "entry_price": float(price), "qty": float(qty),
        "leverage": int(leverage), "margin": float(margin_usdt), "notional": float(qty) * float(price),
        "sl": float(sl) if sl else None, "tp1": float(tp1) if tp1 else None, "tp2": float(tp2) if tp2 else None,
        "liq_price": _calc_liq_price(direction, price, leverage),
        "entry_time": datetime.now().isoformat(),
        "last_checked": datetime.now().isoformat(),
        "source": source, "status": "OPEN",
    }
    wallet["positions"].append(pos)
    save_wallet_state(state)
    return pos, None

def close_position(state: Dict[str, Any], mode: str, pos_id: str, exit_price: float,
                    reason: str, client: Any = None) -> Optional[Dict[str, Any]]:
    wallet = state[mode]
    pos = next((p for p in wallet["positions"] if p["id"] == pos_id), None)
    if not pos:
        return None

    if mode == "real":
        if client is None:
            return None
        fill_price, err = place_live_exit(client, pos["symbol"], pos["direction"], pos["qty"])
        cancel_all_open_orders(client, pos["symbol"])
        if err:
            return None
        exit_price = fill_price

    pnl, roi_pct = _position_unrealized(pos, exit_price)
    wallet["balance"] = wallet.get("balance", 0.0) + (pnl if mode == "demo" else 0.0)
    wallet["positions"] = [p for p in wallet["positions"] if p["id"] != pos_id]

    trade_record = dict(pos)
    trade_record.update({
        "exit_time": datetime.now().isoformat(), "exit_price": float(exit_price),
        "pnl_usdt": pnl, "roi_pct": roi_pct, "exit_reason": reason,
        "balance_after": wallet.get("balance"),
    })
    append_trade_to_disk(trade_record, (pos["exchange"], pos["symbol"], pos["timeframe"]), mode.upper())
    save_wallet_state(state)
    return trade_record

def reconcile_wallet_positions(state: Dict[str, Any], mode: str, client: Any = None) -> List[Dict[str, Any]]:
    """Cek posisi terbuka terhadap candle historis sejak terakhir dicek, supaya
    SL/TP/Liquidation yang kena SELAGI APP TERTUTUP tetap terdeteksi & posisi
    otomatis ditutup dengan benar begitu app dibuka lagi."""
    wallet = state[mode]
    if not wallet.get("positions"):
        wallet["last_checked"] = datetime.now().isoformat()
        save_wallet_state(state)
        return []

    closed: List[Dict[str, Any]] = []
    still_open: List[Dict[str, Any]] = []

    for pos in list(wallet["positions"]):
        exit_price = None
        exit_reason = None
        try:
            since_raw = pos.get("last_checked") or pos.get("entry_time")
            since_dt = datetime.fromisoformat(since_raw) if since_raw else None
        except Exception:
            since_dt = None

        tf = pos.get("timeframe") or "5m"
        try:
            df = get_ohlcv(pos["exchange"], pos["symbol"], tf, limit=WALLET_OHLCV_LIMIT)
        except Exception:
            df = pd.DataFrame()

        if not df.empty:
            recent = df[df["date"] > since_dt] if since_dt is not None else df
            for _, candle in recent.iterrows():
                hi, lo = float(candle["high"]), float(candle["low"])
                if pos["direction"] == "LONG":
                    if pos.get("liq_price") and lo <= pos["liq_price"]:
                        exit_price, exit_reason = pos["liq_price"], "Liquidation"; break
                    if pos.get("sl") and lo <= pos["sl"]:
                        exit_price, exit_reason = pos["sl"], "SL Hit"; break
                    if pos.get("tp2") and hi >= pos["tp2"]:
                        exit_price, exit_reason = pos["tp2"], "TP2 Hit"; break
                    if pos.get("tp1") and hi >= pos["tp1"]:
                        exit_price, exit_reason = pos["tp1"], "TP1 Hit"; break
                else:
                    if pos.get("liq_price") and hi >= pos["liq_price"]:
                        exit_price, exit_reason = pos["liq_price"], "Liquidation"; break
                    if pos.get("sl") and hi >= pos["sl"]:
                        exit_price, exit_reason = pos["sl"], "SL Hit"; break
                    if pos.get("tp2") and lo <= pos["tp2"]:
                        exit_price, exit_reason = pos["tp2"], "TP2 Hit"; break
                    if pos.get("tp1") and lo <= pos["tp1"]:
                        exit_price, exit_reason = pos["tp1"], "TP1 Hit"; break

        if exit_price is not None:
            if mode == "real" and client is None:
                pos["_offline_alert"] = f"Harga historis sempat menyentuh {exit_reason} (~{exit_price}). Cek posisi ini langsung di exchange."
                still_open.append(pos)
                continue
            trade = close_position(state, mode, pos["id"], exit_price, exit_reason, client)
            if trade:
                closed.append(trade)
            continue

        pos["last_checked"] = datetime.now().isoformat()
        pos.pop("_offline_alert", None)
        still_open.append(pos)

    wallet["positions"] = still_open
    save_wallet_state(state)
    return closed

def connect_live_exchange(exchange_name: str, api_key: str, api_secret: str) -> Tuple[Optional[Any], Optional[str]]:
    if not api_key or not api_secret:
        return None, "API Key / Secret kosong."
    try:
        cfg = EXCHANGES.get(exchange_name, next(iter(EXCHANGES.values())))
        exchange_class = _resolve_ccxt_class(cfg["id"])
        client = exchange_class({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": cfg["options"],
        })
        client.load_markets()
        return client, None
    except Exception as e:
        return None, str(e)

def fetch_usdt_balance(client: Any) -> Tuple[Optional[float], Optional[str]]:
    try:
        bal = client.fetch_balance()
        usdt = bal.get("USDT", {})
        free = usdt.get("free", usdt.get("total"))
        return (float(free) if free is not None else None), None
    except Exception as e:
        return None, str(e)

def _amount_for_notional(client: Any, symbol: str, usdt_notional: float, price: float) -> float:
    raw_amount = usdt_notional / price if price > 0 else 0.0
    try:
        return float(client.amount_to_precision(symbol, raw_amount))
    except Exception:
        return round(raw_amount, 6)

def try_set_leverage(client: Any, symbol: str, leverage: int) -> None:
    try:
        client.set_leverage(leverage, symbol)
    except Exception:
        pass

def place_live_exit(client: Any, symbol: str, direction: str, amount: float) -> Tuple[Optional[float], Optional[str]]:
    try:
        side = "sell" if direction == "LONG" else "buy"
        order = client.create_order(symbol, "market", side, amount, params={"reduceOnly": True})
        ticker = client.fetch_ticker(symbol)
        fallback_price = ticker.get("last") or ticker.get("close")
        filled_price = order.get("average") or order.get("price") or fallback_price
        return float(filled_price), None
    except Exception as e:
        return None, str(e)

def try_place_native_protection(client: Any, exchange_name: str, symbol: str, direction: str,
                                 amount: float, sl: Optional[float], tp: Optional[float]) -> Optional[str]:
    """Best-effort: pasang stop-loss/take-profit NATIVE di exchange (bukan di
    app) supaya posisi REAL tetap terlindungi meski app ditutup. Ini bergantung
    dukungan unified ccxt exchange yang dipakai — kalau gagal, fungsi ini
    mengembalikan pesan peringatan (bukan exception) supaya alur order tidak
    terganggu, tapi user WAJIB diberi tahu agar cek manual di exchange."""
    close_side = "sell" if direction == "LONG" else "buy"
    warnings: List[str] = []
    try:
        if sl:
            client.create_order(symbol, "market", close_side, amount,
                                 params={"reduceOnly": True, "stopLossPrice": sl})
    except Exception as e:
        warnings.append(f"SL native gagal dipasang ({e})")
    try:
        if tp:
            client.create_order(symbol, "market", close_side, amount,
                                 params={"reduceOnly": True, "takeProfitPrice": tp})
    except Exception as e:
        warnings.append(f"TP native gagal dipasang ({e})")
    return " · ".join(warnings) if warnings else None

def cancel_all_open_orders(client: Any, symbol: str) -> None:
    try:
        client.cancel_all_orders(symbol)
    except Exception:
        pass


# =============================================================================
# AUTO-BOT — LONG/SHORT OTOMATIS mengikuti signal engine (Demo & Real)
# =============================================================================
# Bot ini bekerja dengan prinsip "catch-up replay": setiap kali halaman Wallet
# Trading dibuka/refresh, sistem mengambil candle historis sejak terakhir bot
# dicek, lalu MEREPLAY candle demi candle — kalau sedang flat & sinyal
# BUY/SELL muncul, bot "membuka" posisi persis di candle itu; kalau sedang
# ada posisi, bot mengecek SL/TP/Liquidation di tiap candle sampai posisi
# tertutup, lalu lanjut mencari sinyal berikutnya. Dengan cara ini, bot tetap
# "berjalan sesuai analisa" walau app/browser kamu tutup — begitu dibuka lagi
# ia mengejar apa yang seharusnya terjadi selama itu (dibatasi jumlah candle
# yang bisa diambil dari exchange, mis. 500 candle terakhir).
#
# Demi keamanan, untuk Wallet REAL, bot HANYA mengeksekusi order BUKA posisi
# baru bila sinyalnya berasal dari candle yang benar-benar baru (beberapa
# menit terakhir) — bukan dari histori lama — supaya tidak asal entry live
# di harga masa lalu yang sudah tidak relevan. Menutup posisi (SL/TP) tetap
# otomatis mengejar histori seperti biasa karena itu memang seharusnya
# terjadi kapan pun candle-nya.

AUTO_BOT_MAX_CANDLES: int = WALLET_OHLCV_LIMIT
AUTO_BOT_REAL_FRESH_MINUTES: int = 5

TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60, "5m": 300, "15m": 900, "1h": 3600,
    "4h": 14400, "1d": 86400, "1w": 604800,
}

def _seconds_until_next_candle(timeframe: str) -> int:
    """Hitung berapa detik lagi sampai candle berikutnya terbentuk pada
    timeframe tertentu — dipakai sebagai 'timer' Auto-Bot supaya user tahu
    kapan bot akan mengevaluasi ulang sinyal (candle baru)."""
    interval = TIMEFRAME_SECONDS.get(timeframe, 900)
    now_ts = datetime.now().timestamp()
    elapsed = now_ts % interval
    return int(interval - elapsed)

def _format_countdown(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}j {m:02d}m {s:02d}d"
    return f"{m:02d}:{s:02d}"

def _default_auto_bot_cfg(exchange_name: str, symbol: str, timeframe: str) -> Dict[str, Any]:
    return {
        "enabled": False, "exchange": exchange_name, "symbol": symbol, "timeframe": timeframe,
        "leverage": 10, "margin_pct": 10.0, "margin_usdt": 50.0,
        "tp_pct": 3.0, "sl_pct": 5.0,
        "last_checked": datetime.now().isoformat(),
    }

def run_auto_bot_catchup(state: Dict[str, Any], mode: str, client: Any = None) -> List[Dict[str, Any]]:
    wallet = state[mode]
    bot_cfg = wallet.get("auto_bot")
    if not bot_cfg or not bot_cfg.get("enabled"):
        return []

    exchange_name = bot_cfg["exchange"]
    symbol = bot_cfg["symbol"]
    timeframe = bot_cfg["timeframe"]

    try:
        since_dt = datetime.fromisoformat(bot_cfg.get("last_checked")) if bot_cfg.get("last_checked") else None
    except Exception:
        since_dt = None

    try:
        df = get_ohlcv(exchange_name, symbol, timeframe, limit=AUTO_BOT_MAX_CANDLES)
    except Exception:
        df = pd.DataFrame()
    if df.empty or len(df) < 60:
        return []
    df = add_indicators(df)

    events: List[Dict[str, Any]] = []
    open_pos = next((p for p in wallet["positions"]
                      if p.get("source") == "auto-bot" and p["symbol"] == symbol), None)

    start_idx = 60
    if since_dt is not None:
        mask = df["date"] > since_dt
        if mask.any():
            start_idx = max(60, int(np.argmax(mask.values)))
        else:
            start_idx = len(df)

    last_processed_time = bot_cfg.get("last_checked")

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        row_time = row["date"]
        hi, lo, close_price = float(row["high"]), float(row["low"]), float(row["close"])

        if open_pos is not None:
            exit_price = None
            exit_reason = None
            if open_pos["direction"] == "LONG":
                if open_pos.get("liq_price") and lo <= open_pos["liq_price"]:
                    exit_price, exit_reason = open_pos["liq_price"], "Liquidation"
                elif open_pos.get("sl") and lo <= open_pos["sl"]:
                    exit_price, exit_reason = open_pos["sl"], "SL Hit"
                elif open_pos.get("tp1") and hi >= open_pos["tp1"]:
                    exit_price, exit_reason = open_pos["tp1"], "TP Hit"
            else:
                if open_pos.get("liq_price") and hi >= open_pos["liq_price"]:
                    exit_price, exit_reason = open_pos["liq_price"], "Liquidation"
                elif open_pos.get("sl") and hi >= open_pos["sl"]:
                    exit_price, exit_reason = open_pos["sl"], "SL Hit"
                elif open_pos.get("tp1") and lo <= open_pos["tp1"]:
                    exit_price, exit_reason = open_pos["tp1"], "TP Hit"

            if exit_price is not None:
                if mode == "real" and client is None:
                    open_pos["_offline_alert"] = (
                        f"Auto-Bot: histori menyentuh {exit_reason} (~{exit_price}). Cek posisi ini di exchange."
                    )
                else:
                    trade = close_position(state, mode, open_pos["id"], exit_price, f"Auto-Bot {exit_reason}", client)
                    if trade:
                        events.append(trade)
                    open_pos = None
            last_processed_time = row_time.isoformat()
            continue

        sub_df = df.iloc[: i + 1]
        sig = analyze_single_timeframe(sub_df)
        if sig.direction in ("BUY", "SELL"):
            direction = "LONG" if sig.direction == "BUY" else "SHORT"

            if direction == "LONG":
                sl = close_price * (1 - bot_cfg["sl_pct"] / 100)
                tp = close_price * (1 + bot_cfg["tp_pct"] / 100)
            else:
                sl = close_price * (1 + bot_cfg["sl_pct"] / 100)
                tp = close_price * (1 - bot_cfg["tp_pct"] / 100)

            if mode == "demo":
                available = wallet["balance"] - wallet_used_margin(wallet)
                margin_usdt = max(available, 0) * bot_cfg["margin_pct"] / 100
                if margin_usdt > 1:
                    pos, err = open_position(state, "demo", exchange_name, symbol, timeframe, direction,
                                              close_price, bot_cfg["leverage"], margin_usdt, sl, tp, tp,
                                              source="auto-bot")
                    if pos:
                        pos["entry_time"] = row_time.isoformat()
                        pos["last_checked"] = row_time.isoformat()
                        save_wallet_state(state)
                        open_pos = pos
                        events.append({"opened": True, "symbol": symbol, "direction": direction,
                                        "entry_price": close_price, "pnl_usdt": 0.0, "exit_reason": "Auto-Bot Open"})
            else:
                is_fresh = row_time >= (datetime.now() - pd.Timedelta(minutes=AUTO_BOT_REAL_FRESH_MINUTES))
                if client is not None and is_fresh:
                    margin_usdt = bot_cfg["margin_usdt"]
                    notional = margin_usdt * bot_cfg["leverage"]
                    try_set_leverage(client, symbol, bot_cfg["leverage"])
                    amount = _amount_for_notional(client, symbol, notional, close_price)
                    if amount > 0:
                        side = "buy" if direction == "LONG" else "sell"
                        try:
                            order = client.create_order(symbol, "market", side, amount)
                            filled_price = float(order.get("average") or order.get("price") or close_price)
                            filled_amount = float(order.get("filled") or amount)
                            pos = {
                                "id": str(uuid.uuid4())[:8], "exchange": exchange_name, "symbol": symbol,
                                "timeframe": timeframe, "direction": direction, "entry_price": filled_price,
                                "qty": filled_amount, "leverage": int(bot_cfg["leverage"]),
                                "margin": float(margin_usdt), "notional": filled_amount * filled_price,
                                "sl": float(sl), "tp1": float(tp), "tp2": float(tp),
                                "liq_price": _calc_liq_price(direction, filled_price, bot_cfg["leverage"]),
                                "entry_time": row_time.isoformat(), "last_checked": row_time.isoformat(),
                                "source": "auto-bot", "status": "OPEN",
                            }
                            try_place_native_protection(client, exchange_name, symbol, direction,
                                                         filled_amount, sl, tp)
                            wallet["positions"].append(pos)
                            save_wallet_state(state)
                            open_pos = pos
                            events.append({"opened": True, "symbol": symbol, "direction": direction,
                                            "entry_price": filled_price, "pnl_usdt": 0.0, "exit_reason": "Auto-Bot Open"})
                        except Exception:
                            pass

        last_processed_time = row_time.isoformat()

    bot_cfg["last_checked"] = last_processed_time or datetime.now().isoformat()
    wallet["auto_bot"] = bot_cfg
    save_wallet_state(state)
    return events


# =============================================================================
# COIN SCANNER — REKOMENDASI MULTI-COIN (BUY / SELL / HOLD)
# =============================================================================

@dataclass
class ScanResult:
    symbol: str
    resolved_symbol: Optional[str]
    ok: bool
    error: Optional[str] = None
    price: float = 0.0
    change_24h: float = 0.0
    signal: Optional[Signal] = None
    pump_score: float = 0.0
    pump_tags: List[str] = field(default_factory=list)
    funding_rate: Optional[float] = None

def scan_symbol(exchange_name: str, target_symbol: str, all_symbols: List[str],
                 timeframe: str, limit: int, mtf_enabled: bool = True,
                 include_funding: bool = False) -> ScanResult:
    resolved = resolve_symbol(target_symbol, all_symbols) if all_symbols else target_symbol
    if resolved is None:
        return ScanResult(symbol=target_symbol, resolved_symbol=None, ok=False,
                           error="Symbol tidak ditemukan di exchange ini")
    try:
        df = get_ohlcv(exchange_name, resolved, timeframe, limit)
        if df.empty or len(df) < 55:
            return ScanResult(symbol=target_symbol, resolved_symbol=resolved, ok=False,
                               error="Data candle tidak cukup (butuh 55+)")
        df = add_indicators(df)
        signal = analyze_single_timeframe(df)
        if mtf_enabled:
            signal = apply_mtf_confirmation(signal, exchange_name, resolved, timeframe, limit=min(limit, 200))
        pump_score, pump_tags = compute_pump_score(df)
        live = get_live_data(exchange_name, resolved)
        price = live.get("price") or float(df.iloc[-1]["close"])
        change_24h = live.get("change") or 0.0
        funding = get_funding_rate(exchange_name, resolved) if include_funding else None
        return ScanResult(symbol=target_symbol, resolved_symbol=resolved, ok=True,
                           price=price, change_24h=change_24h, signal=signal,
                           pump_score=pump_score, pump_tags=pump_tags, funding_rate=funding)
    except Exception as e:
        return ScanResult(symbol=target_symbol, resolved_symbol=resolved, ok=False, error=str(e))

@st.cache_data(ttl=45, show_spinner=False)
def scan_multiple_symbols(exchange_name: str, symbols: Tuple[str, ...], timeframe: str,
                           limit: int, mtf_enabled: bool = True,
                           include_funding: bool = False) -> List[Dict[str, Any]]:
    try:
        all_symbols = get_symbols(exchange_name)
    except Exception:
        all_symbols = POPULAR_SYMBOLS

    rows: List[Dict[str, Any]] = []
    for sym in symbols:
        r = scan_symbol(exchange_name, sym, all_symbols, timeframe, limit, mtf_enabled, include_funding)
        if not r.ok or r.signal is None:
            rows.append({
                "symbol": r.symbol, "ok": False, "error": r.error,
                "direction": "ERROR", "score": 0.0, "confidence": "-",
                "price": 0.0, "change_24h": 0.0, "entry": 0.0, "sl": 0.0,
                "tp1": 0.0, "tp2": 0.0, "rsi": 0.0, "trend_strength": "-",
                "adx": 0.0, "is_actionable": False, "bias": "-",
                "pump_score": 0.0, "pump_tags": [], "mtf_status": "-", "funding_rate": None,
            })
        else:
            s = r.signal
            rows.append({
                "symbol": r.symbol, "ok": True, "error": None,
                "direction": s.direction, "score": s.score, "confidence": s.confidence,
                "price": r.price, "change_24h": r.change_24h,
                "entry": s.entry, "sl": s.sl, "tp1": s.tp1, "tp2": s.tp2,
                "rsi": s.rsi_value, "trend_strength": s.trend_strength, "adx": s.adx_value,
                "is_actionable": s.is_actionable, "bias": s.bias,
                "pump_score": r.pump_score, "pump_tags": r.pump_tags,
                "mtf_status": s.mtf_status, "funding_rate": r.funding_rate,
            })
    return rows

def _render_quick_jump_buttons(rows: List[Dict[str, Any]], key_prefix: str, max_buttons: int = 30) -> None:
    if not rows:
        return
    rows = rows[:max_buttons]
    st.caption("👉 Klik salah satu coin di bawah untuk langsung membuka **Grafik & Analisa Sinyal**-nya:")
    n_cols = 6
    cols = st.columns(n_cols)
    for i, r in enumerate(rows):
        label = f"📊 {r['symbol']}"
        if cols[i % n_cols].button(label, key=f"jump_{key_prefix}_{r['symbol']}", use_container_width=True):
            st.session_state.selected_symbol = r["symbol"]
            st.session_state.active_section = "chart"
            st.rerun()
    if len(rows) >= max_buttons:
        st.caption(f"(Menampilkan {max_buttons} tombol teratas saja, sisanya tetap ada di tabel di atas.)")

def render_coin_scanner_ui(exchange_name: str, timeframe_default: str, mtf_enabled: bool) -> None:
    st.markdown("### 📡 Coin Scanner — Rekomendasi Multi-Coin")
    st.caption(
        "Memindai banyak coin sekaligus memakai signal engine yang sama dengan tab Analisa "
        "(EMA + RSI + MACD + Bollinger + Stochastic + Volume + ADX" +
        (" + konfirmasi MTF" if mtf_enabled else "") +
        "), lalu meranking berdasarkan skor. ⚠️ Bukan nasihat keuangan — tetap DYOR sebelum entry."
    )
    if mtf_enabled:
        st.caption("✅ MTF aktif (dari pengaturan sidebar) — sinyal yang berlawanan dengan timeframe lebih besar otomatis didinginkan jadi HOLD.")
    else:
        st.caption("ℹ️ MTF nonaktif — aktifkan checkbox 'Enable MTF' di sidebar untuk hasil yang lebih selektif/konsisten dengan tren besar.")

    st.markdown("#### 🔥 Mode Coin Micin (harga murah, berpotensi pump)")
    mc1, mc2, mc3, mc4 = st.columns([1, 1, 1, 1.4])
    with mc1:
        micin_min = st.number_input("Harga min ($)", value=MICIN_PRICE_MIN, min_value=0.0,
                                     step=0.01, key="micin_price_min")
    with mc2:
        micin_max = st.number_input("Harga max ($)", value=MICIN_PRICE_MAX, min_value=0.01,
                                     step=0.5, key="micin_price_max")
    with mc3:
        micin_count = st.number_input("Jumlah coin", value=MICIN_DEFAULT_COUNT, min_value=10,
                                       max_value=SCANNER_MAX_SYMBOLS, step=10, key="micin_count")
    with mc4:
        st.write("")
        fill_micin = st.button("🔥 Auto-isi Coin Micin ke Daftar", use_container_width=True)

    if fill_micin:
        with st.spinner(f"Mencari coin ${micin_min:g}-${micin_max:g} paling likuid di {exchange_name}..."):
            candidates = find_micin_candidates(exchange_name, micin_min, micin_max, int(micin_count))
        if not candidates:
            st.warning("Tidak ada coin ditemukan di rentang harga tersebut, atau bulk ticker gagal diambil.")
        else:
            base_syms = sorted(set(c.split(":")[0] for c in candidates))
            st.session_state["scanner_symbols_input"] = ", ".join(base_syms)
            st.success(f"✅ {len(base_syms)} coin micin (${micin_min:g}-${micin_max:g}) berhasil diisi ke daftar di bawah, urut dari volume 24h tertinggi.")
            st.rerun()

    st.markdown("---")

    default_list_str = ", ".join(SCANNER_DEFAULT_SYMBOLS)
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        symbols_input = st.text_area(
            f"Daftar coin yang dipindai (pisahkan koma, format BASE/USDT, maks {SCANNER_MAX_SYMBOLS} coin)",
            value=default_list_str, height=90, key="scanner_symbols_input"
        )
    with c2:
        scan_timeframe = st.selectbox(
            "Timeframe Scanner", TIMEFRAMES,
            index=TIMEFRAMES.index(timeframe_default) if timeframe_default in TIMEFRAMES else 2,
            key="scanner_timeframe"
        )
    with c3:
        scan_limit = st.selectbox("Candles", [100, 150, 200, 300], index=1, key="scanner_limit")

    symbols_list = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]
    symbols_list = symbols_list[:SCANNER_MAX_SYMBOLS]

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.6])
    with c1:
        run_scan = st.button("🔍 Scan Sekarang", type="primary", use_container_width=True)
    with c2:
        only_actionable = st.checkbox("Hanya BUY/SELL", value=False, key="scanner_only_actionable")
    with c3:
        include_funding = st.checkbox("+ Funding Rate", value=False, key="scanner_include_funding",
                                       help="Ambil funding rate futures per coin (request tambahan per coin, scan jadi lebih lambat).")
    with c4:
        st.caption(f"Total coin: **{len(symbols_list)}** (maks {SCANNER_MAX_SYMBOLS}/scan)")
        if len(symbols_list) > 60:
            st.caption("⏳ Scan >60 coin butuh waktu lebih lama — mohon sabar saat menekan Scan.")

    if "scanner_results" not in st.session_state:
        st.session_state["scanner_results"] = None
        st.session_state["scanner_last_run"] = None

    if run_scan:
        if not symbols_list:
            st.warning("Daftar coin kosong.")
        else:
            with st.spinner(f"Memindai {len(symbols_list)} coin di {exchange_name} ({scan_timeframe})..."):
                rows = scan_multiple_symbols(exchange_name, tuple(symbols_list), scan_timeframe, scan_limit,
                                              mtf_enabled, include_funding)
            st.session_state["scanner_results"] = rows
            st.session_state["scanner_last_run"] = datetime.now()

    rows = st.session_state.get("scanner_results")
    if not rows:
        st.info("Tekan **🔥 Auto-isi Coin Micin** untuk mengisi otomatis, lalu tekan **Scan Sekarang**.")
        return

    last_run = st.session_state.get("scanner_last_run")
    if last_run:
        st.caption(f"Terakhir scan: {last_run.strftime('%Y-%m-%d %H:%M:%S')} · {exchange_name} · TF {scan_timeframe}"
                   + (" · MTF ✅" if mtf_enabled else ""))

    df_scan = pd.DataFrame(rows)

    valid = df_scan[df_scan["ok"]].copy()
    errored = df_scan[~df_scan["ok"]].copy()

    if only_actionable:
        valid = valid[valid["is_actionable"]]

    valid = valid.sort_values("score", ascending=False)

    buy_df = valid[valid["direction"] == "BUY"].sort_values("score", ascending=False)
    sell_df = valid[valid["direction"] == "SELL"].sort_values("score", ascending=True)
    hold_df = valid[valid["direction"] == "HOLD"].sort_values("score", ascending=False)
    pump_df = valid[valid["pump_score"] >= 4.0].sort_values("pump_score", ascending=False)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🟢 BUY", len(buy_df))
    m2.metric("🔴 SELL", len(sell_df))
    m3.metric("🟡 HOLD", len(hold_df))
    m4.metric("🔥 Potensi Pump", len(pump_df))
    m5.metric("⚠️ Gagal", len(errored))

    def _style_table(d: pd.DataFrame, show_pump: bool = False) -> pd.DataFrame:
        cols = ["symbol", "price", "change_24h", "direction", "score", "confidence",
                "entry", "sl", "tp1", "tp2", "rsi", "adx", "trend_strength"]
        headers = ["Coin", "Harga", "24h %", "Sinyal", "Score", "Confidence",
                   "Entry", "SL", "TP1", "TP2", "RSI", "ADX", "Trend"]
        if include_funding:
            cols.append("funding_rate")
            headers.append("Funding")
        if show_pump:
            cols.append("pump_score")
            headers.append("🔥 Pump Score")
        show = d[cols].copy()
        show["price"] = [format_price(p, s) for p, s in zip(show["price"], show["symbol"])]
        show["change_24h"] = show["change_24h"].apply(format_percentage)
        show["entry"] = [format_price(p, s) for p, s in zip(show["entry"], show["symbol"])]
        show["sl"] = [format_price(p, s) for p, s in zip(show["sl"], show["symbol"])]
        show["tp1"] = [format_price(p, s) for p, s in zip(show["tp1"], show["symbol"])]
        show["tp2"] = [format_price(p, s) for p, s in zip(show["tp2"], show["symbol"])]
        show["rsi"] = show["rsi"].apply(lambda x: f"{x:.1f}")
        show["adx"] = show["adx"].apply(lambda x: f"{x:.1f}")
        if include_funding:
            show["funding_rate"] = show["funding_rate"].apply(lambda x: f"{x*100:+.4f}%" if x is not None else "-")
        if show_pump:
            show["pump_score"] = show["pump_score"].apply(lambda x: f"{x:.1f}/10")
        show.columns = headers
        return show

    st.markdown("---")
    st.markdown(f"#### 🔥 Potensi Pump — Coin Micin dengan Momentum Awal ({len(pump_df)})")
    st.caption(
        "Diranking berdasarkan **Pump Score** (0-10): kombinasi lonjakan volume, RSI baru bangkit dari area "
        "rendah, histogram MACD menguat, breakout dari BB midline, dan momentum harga yang mempercepat. "
        "Ini heuristik momentum jangka pendek, **bukan jaminan pump beneran terjadi** — volatilitas coin "
        "micin sangat tinggi dan risiko rugi besar juga tinggi. Selalu pakai position size kecil & SL ketat."
    )
    if not pump_df.empty:
        st.dataframe(_style_table(pump_df, show_pump=True), use_container_width=True, hide_index=True)
        _render_quick_jump_buttons(pump_df.to_dict("records"), key_prefix="pump")
        with st.expander("📋 Detail alasan Pump Score per coin", expanded=False):
            pump_rows_full = [r for r in rows if r.get("pump_score", 0) >= 4.0]
            pump_rows_full.sort(key=lambda r: r.get("pump_score", 0), reverse=True)
            for r in pump_rows_full:
                tags = r.get("pump_tags") or []
                tag_str = " · ".join(tags) if tags else "-"
                st.markdown(f"**{r['symbol']}** — Pump Score `{r['pump_score']:.1f}/10`  \n{tag_str}")
    else:
        st.caption("Belum ada coin dengan Pump Score ≥ 4.0 dari daftar saat ini. Coba scan ulang atau perluas daftar coin.")

    st.markdown("---")
    st.markdown(f"#### 🟢 Rekomendasi BUY ({len(buy_df)})")
    if not buy_df.empty:
        st.dataframe(_style_table(buy_df), use_container_width=True, hide_index=True)
        _render_quick_jump_buttons(buy_df.to_dict("records"), key_prefix="buy")
    else:
        st.caption("Tidak ada coin dengan sinyal BUY aktif (score ≥ 3.0" + (", dan selaras MTF" if mtf_enabled else "") + ") saat ini.")

    st.markdown(f"#### 🔴 Rekomendasi SELL ({len(sell_df)})")
    if not sell_df.empty:
        st.dataframe(_style_table(sell_df), use_container_width=True, hide_index=True)
        _render_quick_jump_buttons(sell_df.to_dict("records"), key_prefix="sell")
    else:
        st.caption("Tidak ada coin dengan sinyal SELL aktif (score ≤ -3.0" + (", dan selaras MTF" if mtf_enabled else "") + ") saat ini.")

    with st.expander(f"🟡 HOLD / Belum ada konfirmasi ({len(hold_df)})", expanded=False):
        if not hold_df.empty:
            st.caption(
                "Coin di bawah ini skornya belum tembus ambang ±3.0, atau tadinya BUY/SELL tapi didinginkan "
                "karena berlawanan dengan timeframe lebih besar (MTF). Kolom Entry/SL/TP1/TP2 hanya "
                "REFERENSI arah condong (bias) sesaat, BUKAN sinyal aktif — jangan dipakai untuk entry."
            )
            st.dataframe(_style_table(hold_df), use_container_width=True, hide_index=True)
            _render_quick_jump_buttons(hold_df.to_dict("records"), key_prefix="hold")
        else:
            st.caption("Semua coin di daftar sudah punya arah (BUY/SELL).")

    if not errored.empty:
        with st.expander(f"⚠️ Gagal dipindai ({len(errored)})", expanded=False):
            for _, row in errored.iterrows():
                st.caption(f"`{row['symbol']}` — {row['error']}")

    st.caption(
        "💡 Score dihitung dari kombinasi EMA/RSI/MACD/Bollinger/Stochastic/Volume/ADX" +
        (" + konfirmasi MTF terhadap timeframe lebih besar" if mtf_enabled else "") +
        " — sama dengan engine di tab Analisa. Semakin besar |score|, semakin banyak indikator yang searah. "
        "⚠️ Bukan nasihat keuangan, selalu DYOR & gunakan position sizing yang wajar — coin micin/harga "
        "murah umumnya likuiditasnya lebih tipis dan volatilitasnya jauh lebih tinggi dari BTC/ETH."
    )


# =============================================================================
# CHART
# =============================================================================

def create_chart(df: pd.DataFrame, symbol: str, signal: Optional[Signal] = None) -> go.Figure:
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.45, 0.2, 0.2, 0.15],
        vertical_spacing=0.03,
        subplot_titles=(f"{symbol} — Price / EMA / Bollinger Bands", "MACD", "RSI + Stochastic", "Volume")
    )

    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Price"
    ), row=1, col=1)

    ema_colors = {
        "ema_9": ("EMA 9", "#f5c542"),
        "ema_21": ("EMA 21", "#42a5f5"),
        "ema_50": ("EMA 50", "#ab47bc"),
        "ema_200": ("EMA 200", "#ff6d00")
    }
    for col, (name, color) in ema_colors.items():
        if col in df.columns and not df[col].isna().all():
            fig.add_trace(go.Scatter(
                x=df["date"], y=df[col], mode="lines", name=name,
                line=dict(width=1.2, color=color, dash="solid" if col != "ema_200" else "dash")
            ), row=1, col=1)

    if all(c in df.columns for c in ["bb_upper", "bb_lower"]):
        fig.add_trace(go.Scatter(x=df["date"], y=df["bb_upper"], mode="lines", name="BB Upper",
                                  line=dict(width=1, color="rgba(150,150,150,0.6)")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["date"], y=df["bb_lower"], mode="lines", name="BB Lower",
                                  line=dict(width=1, color="rgba(150,150,150,0.6)"),
                                  fill="tonexty", fillcolor="rgba(150,150,150,0.08)"), row=1, col=1)

    if signal and signal.direction != "HOLD":
        signal_color = "green" if signal.direction == "BUY" else "red"
        fig.add_trace(go.Scatter(
            x=[df["date"].iloc[-1]], y=[signal.entry],
            mode="markers+text", name=f"Signal: {signal.direction}",
            marker=dict(size=15, color=signal_color, symbol="star"),
            text=[signal.direction], textposition="top center", textfont=dict(size=12, color="white")
        ), row=1, col=1)
        fig.add_hline(y=signal.sl, line_dash="dash", line_color="red", annotation_text=f"SL {signal.sl:.2f}", row=1, col=1)
        fig.add_hline(y=signal.tp1, line_dash="dash", line_color="green", annotation_text=f"TP1 {signal.tp1:.2f}", row=1, col=1)
        fig.add_hline(y=signal.tp2, line_dash="dash", line_color="#00c853", annotation_text=f"TP2 {signal.tp2:.2f}", row=1, col=1)

    if "macd_hist" in df.columns:
        colors = np.where(df["macd_hist"] >= 0, "#26a69a", "#ef5350")
        fig.add_trace(go.Bar(x=df["date"], y=df["macd_hist"], name="MACD Hist", marker_color=colors), row=2, col=1)
    if "macd" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["macd"], mode="lines", name="MACD",
                                  line=dict(width=1.5, color="#2962ff")), row=2, col=1)
    if "macd_signal" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["macd_signal"], mode="lines", name="Signal",
                                  line=dict(width=1.5, color="#ff6d00")), row=2, col=1)
    fig.add_hline(y=0, line_dash="solid", line_color="rgba(128,128,128,0.3)", row=2, col=1)

    if "rsi_14" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["rsi_14"], mode="lines", name="RSI 14",
                                  line=dict(width=1.8, color="#7e57c2")), row=3, col=1)
    if "stoch_k" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["stoch_k"], mode="lines", name="Stoch K",
                                  line=dict(width=1.2, color="#ff6f00")), row=3, col=1)
    if "stoch_d" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["stoch_d"], mode="lines", name="Stoch D",
                                  line=dict(width=1.2, color="#ffab00")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    if "volume" in df.columns and "close" in df.columns:
        vol_colors = np.where(df["close"] > df["open"], "#26a69a", "#ef5350")
        fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="Volume", marker_color=vol_colors, opacity=0.7), row=4, col=1)
    if "volume_ma" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["volume_ma"], mode="lines", name="Vol MA 20",
                                  line=dict(width=1.5, color="#ff6d00", dash="dash")), row=4, col=1)

    fig.update_layout(
        height=700, xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,22,30,0.55)",
        font=dict(color="#d8e3ee"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=8)),
        margin=dict(l=10, r=10, t=30, b=10)
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="RSI / Stoch", row=3, col=1, range=[0, 100])
    fig.update_yaxes(title_text="Volume", row=4, col=1)

    return fig

# =============================================================================
# TELEGRAM
# =============================================================================

def init_telegram_if_enabled() -> None:
    cfg = st.session_state.get("telegram_cfg", {})
    if not cfg.get("enabled", False):
        return

    bot_token = cfg.get("bot_token", "")
    chat_id = cfg.get("chat_id", "")

    if not bot_token or not chat_id:
        st.sidebar.warning("⚠️ Telegram: Isi Bot Token dan Chat ID")
        return

    if st.session_state.get("telegram_started_sent", False):
        return

    try:
        test_msg = f"🤖 {BOT_NAME} Started!\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ok = send_telegram_message(test_msg, bot_token, chat_id)
        st.session_state["telegram_started_sent"] = True
        if ok:
            st.sidebar.success("✅ Telegram bot aktif")
        else:
            st.sidebar.error("❌ Gagal mengirim pesan Telegram")
    except Exception as e:
        st.sidebar.error(f"❌ Telegram error: {e}")

# =============================================================================
# UI RENDER FUNCTIONS
# =============================================================================

def render_live_price_ui(exchange_name: str, symbol: str) -> None:
    data = get_live_data(exchange_name, symbol)
    color = "🟢" if data['change'] > 0 else "🔴" if data['change'] < 0 else "⚪"

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.metric(f"{color} Price", f"${format_price(data['price'], symbol)}", format_percentage(data['change']))
    c2.metric("📈 24h High", f"${format_price(data['high'], symbol)}")
    c3.metric("📉 24h Low", f"${format_price(data['low'], symbol)}")
    c4.metric("📊 24h Volume", f"${format_volume(data['volume'])}")
    st.caption(f"🔄 Update terakhir: {datetime.now().strftime('%H:%M:%S')} (auto-refresh tiap beberapa detik)")


_fragment_decorator = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)


def render_live_price_fragment(exchange_name: str, symbol: str, refresh_sec: int = 5) -> None:
    if _fragment_decorator is None:
        render_live_price_ui(exchange_name, symbol)
        st.info("ℹ️ Update Streamlit ke versi >=1.37 agar harga live auto-refresh tanpa reload halaman.")
        return

    @_fragment_decorator(run_every=refresh_sec)
    def _price_fragment():
        render_live_price_ui(exchange_name, symbol)

    _price_fragment()


def render_analysis_fragment(exchange_name: str, symbol: str, timeframe: str, limit: int,
                              mtf_enabled: bool, refresh_sec: int, auto_refresh: bool) -> None:
    def _body():
        _render_analysis_body(exchange_name, symbol, timeframe, limit, mtf_enabled)

    if not auto_refresh or _fragment_decorator is None:
        _body()
        return

    @_fragment_decorator(run_every=refresh_sec)
    def _fragment_body():
        _body()

    _fragment_body()


def _render_analysis_body(exchange_name: str, symbol: str, timeframe: str, limit: int, mtf_enabled: bool) -> None:
    try:
        df = get_ohlcv(exchange_name, symbol, timeframe, limit)
        if df.empty:
            st.error("Data tidak tersedia untuk symbol/timeframe ini.")
            return
        df = add_indicators(df)
    except Exception as e:
        st.error(f"Error memproses data: {e}")
        return

    if len(df) < 55:
        st.warning("⚠️ Data tidak cukup (butuh 55+ candle)")
        return

    signal = analyze_single_timeframe(df)
    if mtf_enabled:
        signal = apply_mtf_confirmation(signal, exchange_name, symbol, timeframe, limit=min(limit, 250))

    badge_map = {
        "BUY": '<span class="signal-buy">🟢 BUY</span>',
        "SELL": '<span class="signal-sell">🔴 SELL</span>',
        "HOLD": '<span class="signal-hold">🟡 HOLD</span>'
    }

    c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1], gap="small")
    c1.markdown(f"### Signal: {badge_map.get(signal.direction, '')}", unsafe_allow_html=True)
    c2.metric("Score", f"{signal.score:.1f}")
    c3.metric("Confidence", signal.confidence)
    c4.metric("MTF", "✅" if mtf_enabled else "❌")
    c5.metric("Trend", signal.trend_strength)

    if mtf_enabled:
        mtf_icon = "✅" if signal.mtf_aligned else ("⚠️" if signal.mtf_aligned is False else "ℹ️")
        st.caption(f"{mtf_icon} MTF: {signal.mtf_status}")

    if not signal.is_actionable:
        st.info(
            f"ℹ️ Status **HOLD** — skor ({signal.score:.1f}) belum mencapai ambang ±3.0 untuk sinyal aktif"
            + (", atau sinyal didinginkan karena berlawanan dengan timeframe lebih besar (MTF)" if mtf_enabled else "")
            + f". Level Entry/SL/TP1/TP2 di bawah ini hanya **referensi arah condong ({signal.bias})**, "
              f"**BUKAN rekomendasi entry**. Tunggu konfirmasi tambahan sebelum membuka posisi."
        )

    cols = st.columns(4, gap="small")
    entry_label = "Entry (Referensi)" if not signal.is_actionable else "Entry"
    sl_label = "SL (Referensi)" if not signal.is_actionable else "SL"
    tp1_label = "TP1 (Referensi)" if not signal.is_actionable else "TP1"
    tp2_label = "TP2 (Referensi)" if not signal.is_actionable else "TP2"
    cols[0].metric(entry_label, f"${format_price(signal.entry, symbol)}")
    cols[1].metric(sl_label, f"${format_price(signal.sl, symbol)}", format_percentage(safe_pct_change(signal.sl, signal.entry)))
    cols[2].metric(tp1_label, f"${format_price(signal.tp1, symbol)}", format_percentage(safe_pct_change(signal.tp1, signal.entry)))
    cols[3].metric(tp2_label, f"${format_price(signal.tp2, symbol)}", format_percentage(safe_pct_change(signal.tp2, signal.entry)))

    st.divider()

    with st.expander("📊 Signal Details", expanded=True):
        c1, c2, c3 = st.columns(3, gap="small")
        c1.markdown(f"**EMA:** {signal.ema_status}\n\n**RSI:** {signal.rsi_value:.1f} ({signal.rsi_status})\n\n**MACD:** {signal.macd_status}")
        c2.markdown(f"**Bollinger:** {signal.bb_status}\n\n**Stochastic:** {signal.stoch_status}\n\n**Volume:** {signal.volume_status}")
        c3.markdown(f"**ADX:** {signal.adx_value:.1f} ({signal.trend_strength})\n\n**Confidence:** {signal.confidence}\n\n**Score:** {signal.score:.1f}")

        st.markdown("---")
        st.markdown("#### 📋 Reasons — Penjelasan Detail")
        st.caption(
            "Penjelasan di bawah ditulis agar mudah dipahami meski kamu baru belajar analisa teknikal — "
            "setiap kartu menunjukkan mengapa faktor tersebut menambah/mengurangi skor sinyal."
        )
        sentiment_style = {
            "bullish": ("#00c853", "#00e676"),
            "bearish": ("#ff5252", "#ff6e6e"),
            "neutral": ("#ffc107", "#ffd54f"),
        }
        for reason in signal.reasons:
            sentiment = reason_sentiment(reason)
            detail = reason_explanation(reason)
            border_color, title_color = sentiment_style[sentiment]
            st.markdown(
                f"""<div style="border-left:3px solid {border_color}; background:rgba(255,255,255,0.03);
border-radius:8px; padding:10px 14px; margin-bottom:10px;">
<div style="font-weight:700; font-size:13px; color:{title_color}; margin-bottom:4px;">{reason}</div>
<div style="font-size:12px; color:#c3d2e0; line-height:1.55;">{detail}</div>
</div>""",
                unsafe_allow_html=True
            )

    fig = create_chart(df, symbol, signal)
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{exchange_name}_{symbol}_{timeframe}")

    with st.expander("📊 Raw Data (last 20)", expanded=False):
        raw_cols = ["date", "open", "high", "low", "close", "volume", "rsi_14", "macd", "stoch_k", "adx"]
        display_df = df[raw_cols].tail(20)
        st.dataframe(display_df.style.format({
            "open": lambda x: format_price(x, symbol),
            "high": lambda x: format_price(x, symbol),
            "low": lambda x: format_price(x, symbol),
            "close": lambda x: format_price(x, symbol),
            "volume": lambda x: format_volume(x),
            "rsi_14": "{:.1f}",
            "macd": "{:.4f}",
            "stoch_k": "{:.1f}",
            "adx": "{:.1f}"
        }), use_container_width=True, height=250)

    st.caption(f"🔄 Update terakhir: {datetime.now().strftime('%H:%M:%S')}")


# =============================================================================
# WALLET TRADING UI — Demo (virtual) & Real (live), Long/Short, Cross Margin
# =============================================================================

def _render_demo_balance_editor(state: Dict[str, Any]) -> None:
    with st.expander("✏️ Atur Saldo Demo (manual, tersimpan permanen)", expanded=False):
        st.caption(
            "Ubah saldo demo kapan saja — misalnya 'top up' virtual atau koreksi saldo. Tidak perlu tombol "
            "reset — saldo ini tersimpan di server dan otomatis bertambah/berkurang tiap kali posisi demo "
            "ditutup (profit/loss)."
        )
        new_bal = st.number_input(
            "Saldo Demo (USDT)", min_value=0.0, value=float(state["demo"]["balance"]),
            step=100.0, key="demo_balance_input"
        )
        if st.button("💾 Simpan Saldo Demo", key="save_demo_balance_btn"):
            adjust_demo_balance(state, new_bal)
            st.success(f"Saldo demo diperbarui menjadi ${format_number(new_bal)}.")
            st.rerun()


def _render_real_wallet_connection(exchange_name: str) -> Optional[Any]:
    creds = st.session_state.setdefault(LIVE_CREDS_KEY, {"connected": False, "client": None, "balance": None})
    with st.expander("🔐 Koneksi Exchange (Wallet Real)", expanded=not creds.get("connected", False)):
        st.error(
            "⚠️ **UANG SUNGGUHAN.** Gunakan API key dengan pembatasan IP dan **TANPA izin withdraw**. "
            "Kredensial API TIDAK disimpan ke disk (hanya hidup selama sesi browser ini) untuk alasan keamanan."
        )
        c1, c2 = st.columns(2)
        with c1:
            api_key = st.text_input("API Key", type="password", key="live_api_key")
        with c2:
            api_secret = st.text_input("API Secret", type="password", key="live_api_secret")
        if st.button("🔌 Konek & Cek Saldo", key="real_connect_btn"):
            client, err = connect_live_exchange(exchange_name, api_key, api_secret)
            if err:
                st.error(f"❌ Gagal konek: {err}")
                creds.update({"connected": False, "client": None})
            else:
                bal, berr = fetch_usdt_balance(client)
                if berr:
                    st.error(f"❌ Konek berhasil tapi gagal ambil saldo: {berr}")
                    creds.update({"connected": False, "client": None})
                else:
                    creds.update({"connected": True, "client": client, "balance": bal})
                    st.success(f"✅ Terhubung. Saldo USDT tersedia: ${format_number(bal)}")
        if creds.get("connected"):
            st.caption(f"🟢 Terhubung · Saldo terakhir: ${format_number(creds.get('balance'))}")
            st.caption(
                "ℹ️ Karena app ini tidak berjalan di background, perlindungan SL/TP untuk posisi REAL saat "
                "kamu offline bergantung pada order stop native yang dipasang ke exchange saat posisi dibuka. "
                "Selalu cek juga langsung di exchange kamu untuk memastikan."
            )
    return creds.get("client") if creds.get("connected") else None


def _render_auto_bot_panel(state: Dict[str, Any], mode: str, exchange_name: str, symbol: str,
                            timeframe: str, client: Any) -> None:
    wallet = state[mode]
    existing_cfg = wallet.get("auto_bot")
    bot_cfg = existing_cfg or _default_auto_bot_cfg(exchange_name, symbol, timeframe)
    was_enabled = bool(existing_cfg and existing_cfg.get("enabled"))
    was_same_target = bool(
        existing_cfg and existing_cfg.get("symbol") == symbol
        and existing_cfg.get("timeframe") == timeframe and existing_cfg.get("exchange") == exchange_name
    )

    with st.expander("🤖 Auto-Bot LONG/SHORT Otomatis", expanded=bot_cfg.get("enabled", False)):
        st.caption(
            "Bot membuka posisi **LONG/SHORT otomatis** mengikuti sinyal analisa (EMA+RSI+MACD+Bollinger+"
            "Stochastic+Volume+ADX) pada coin & timeframe yang sedang aktif — tanpa perlu klik tombol manual. "
            "Karena app tidak berjalan di background, saat kamu buka lagi halaman ini bot akan mengejar candle "
            "historis sejak terakhir dicek untuk membuka/menutup posisi seolah berjalan terus (dibatasi "
            f"maksimum {AUTO_BOT_MAX_CANDLES} candle terakhir). Auto-Bot tidak memakai konfirmasi MTF supaya "
            "proses catch-up konsisten & ringan, dan hanya 1 posisi otomatis aktif per coin."
        )
        if mode == "real":
            st.caption(
                f"⚠️ Untuk Wallet Real, Auto-Bot hanya MEMBUKA posisi baru dari sinyal yang benar-benar baru "
                f"(≤{AUTO_BOT_REAL_FRESH_MINUTES} menit terakhir) demi keamanan — tidak entry live di harga "
                "masa lalu. Menutup posisi (SL/TP) tetap otomatis mengejar histori seperti biasa."
            )

        # --- Timer / countdown: kapan bot akan mengevaluasi ulang sinyal ---
        secs_left = _seconds_until_next_candle(timeframe)
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("⏱️ Candle Berikutnya", _format_countdown(secs_left))
        last_checked_disp = "-"
        if existing_cfg and existing_cfg.get("last_checked"):
            try:
                last_checked_disp = datetime.fromisoformat(existing_cfg["last_checked"]).strftime("%H:%M:%S")
            except Exception:
                last_checked_disp = "-"
        tc2.metric("🔎 Terakhir Dicek Bot", last_checked_disp)
        tc3.metric("🔄 Auto-Refresh", "aktif" if _fragment_decorator is not None else "manual")
        st.caption(
            "Bot mengevaluasi ulang sinyal setiap kali halaman ini refresh DAN ada candle baru yang terbentuk "
            "(timer di atas menghitung mundur ke penutupan candle berikutnya pada timeframe yang aktif)."
        )

        c1, c2 = st.columns([1, 2])
        with c1:
            enabled = st.checkbox("Aktifkan Auto-Bot", value=bot_cfg.get("enabled", False), key=f"autobot_enabled_{mode}")
        with c2:
            st.caption(f"Coin & timeframe aktif: **{symbol} · {timeframe} · {exchange_name}**")

        c1, c2 = st.columns(2)
        with c1:
            leverage = st.slider("Leverage Bot", 1, 125, int(bot_cfg.get("leverage", 10)), 1, key=f"autobot_leverage_{mode}")
        with c2:
            if mode == "demo":
                margin_pct = st.slider("Margin per Posisi (% saldo tersedia)", 1, 100,
                                        int(bot_cfg.get("margin_pct", 10)), 1, key=f"autobot_marginpct_{mode}")
                margin_usdt = bot_cfg.get("margin_usdt", 50.0)
            else:
                margin_usdt = st.number_input("Margin per Posisi (USDT)", min_value=5.0,
                                               value=float(bot_cfg.get("margin_usdt", 50.0)), step=5.0,
                                               key=f"autobot_marginusdt_{mode}")
                margin_pct = bot_cfg.get("margin_pct", 10.0)

        c1, c2 = st.columns(2)
        with c1:
            tp_pct = st.slider("🎯 Target Profit / Win Rate (%)", 1.0, 10.0,
                                float(bot_cfg.get("tp_pct", 3.0)), 0.5, key=f"autobot_tp_{mode}")
        with c2:
            sl_pct = st.slider("🛑 Stop Loss (%)", 1.0, 15.0,
                                float(bot_cfg.get("sl_pct", 5.0)), 0.5, key=f"autobot_sl_{mode}")
        st.caption(
            f"Posisi LONG: TP di harga +{tp_pct:.1f}%, SL di -{sl_pct:.1f}% dari entry. "
            f"Posisi SHORT: TP di -{tp_pct:.1f}%, SL di +{sl_pct:.1f}% dari entry."
        )

        confirm_real_bot = True
        if mode == "real":
            confirm_real_bot = st.checkbox(
                "Saya paham Auto-Bot akan membuka order live otomatis dengan uang sungguhan",
                key="confirm_real_autobot"
            )

        save_disabled = mode == "real" and enabled and not confirm_real_bot
        if st.button("💾 Simpan Pengaturan Auto-Bot", key=f"save_autobot_{mode}", disabled=save_disabled):
            # Reset checkpoint (last_checked) kalau ini aktivasi baru (sebelumnya nonaktif, atau target
            # coin/timeframe/exchange berubah) — supaya sinyal yang SUDAH TAMPIL di layar saat ini langsung
            # dievaluasi bot, bukan dianggap "sudah pernah dicek" dan malah dilewati.
            fresh_activation = enabled and (not was_enabled or not was_same_target)
            new_last_checked = None if fresh_activation else (bot_cfg.get("last_checked") or datetime.now().isoformat())

            new_cfg = {
                "enabled": enabled, "exchange": exchange_name, "symbol": symbol, "timeframe": timeframe,
                "leverage": int(leverage), "margin_pct": float(margin_pct), "margin_usdt": float(margin_usdt),
                "tp_pct": float(tp_pct), "sl_pct": float(sl_pct),
                "last_checked": new_last_checked,
            }
            wallet["auto_bot"] = new_cfg
            save_wallet_state(state)
            msg = "Pengaturan Auto-Bot disimpan."
            if enabled:
                msg += " Bot sekarang AKTIF" + (" — akan langsung mengevaluasi sinyal saat ini." if fresh_activation else ".")
            st.success(msg)
            st.rerun()

        current_cfg = wallet.get("auto_bot") or {}
        if current_cfg.get("enabled"):
            st.success(f"🟢 Auto-Bot AKTIF di {current_cfg.get('symbol')} ({current_cfg.get('timeframe')})")
        else:
            st.caption("⚪ Auto-Bot nonaktif.")


def _render_order_form(state: Dict[str, Any], mode: str, exchange_name: str, symbol: str,
                        timeframe: str, client: Any, mark_price: float) -> None:
    st.markdown("#### 🎯 Buka Posisi Baru")
    if mode == "real" and client is None:
        st.warning("Hubungkan API key dulu di panel di atas untuk membuka posisi real.")
        return
    if not mark_price:
        st.warning("Harga live belum tersedia, coba refresh sebentar lagi.")
        return

    wallet = state[mode]
    default_sl, default_tp1, default_tp2 = mark_price * 0.99, mark_price * 1.015, mark_price * 1.03
    try:
        df = get_ohlcv(exchange_name, symbol, timeframe, WALLET_OHLCV_LIMIT)
        if not df.empty and len(df) >= 55:
            sig = analyze_single_timeframe(add_indicators(df))
            default_sl, default_tp1, default_tp2 = sig.sl, sig.tp1, sig.tp2
    except Exception:
        pass

    c1, c2, c3 = st.columns(3)
    with c1:
        leverage = st.slider("Leverage", 1, 125, 10, 1, key=f"order_leverage_{mode}")
    with c2:
        if mode == "demo":
            available = wallet["balance"] - wallet_used_margin(wallet)
            pct_quick = st.select_slider(
                "Margin (% saldo tersedia)", options=[5, 10, 25, 50, 75, 100], value=10,
                key="order_margin_pct"
            )
            margin_usdt = round(max(available, 0) * pct_quick / 100, 2)
            st.caption(f"Margin dipakai: **${margin_usdt:,.2f}** dari tersedia ${format_number(available)}")
        else:
            margin_usdt = st.number_input("Margin (USDT)", min_value=5.0, value=50.0, step=5.0, key="order_margin_real")
    with c3:
        st.metric("Harga Sekarang", f"${format_price(mark_price, symbol)}")

    notional = margin_usdt * leverage
    qty_preview = (notional / mark_price) if mark_price else 0.0
    liq_long = _calc_liq_price("LONG", mark_price, leverage)
    liq_short = _calc_liq_price("SHORT", mark_price, leverage)

    c1, c2, c3 = st.columns(3)
    with c1:
        sl_price = st.number_input("Stop Loss (harga)", value=float(default_sl), format="%.6f", key=f"order_sl_{mode}")
    with c2:
        tp1_price = st.number_input("Take Profit 1 (harga)", value=float(default_tp1), format="%.6f", key=f"order_tp1_{mode}")
    with c3:
        tp2_price = st.number_input("Take Profit 2 (harga)", value=float(default_tp2), format="%.6f", key=f"order_tp2_{mode}")

    st.caption(
        f"📐 Notional: **${notional:,.2f}** · Qty ≈ **{qty_preview:.6f}** · "
        f"Est. Liq jika LONG ≈ ${format_price(liq_long, symbol)} · "
        f"Est. Liq jika SHORT ≈ ${format_price(liq_short, symbol)}"
    )

    confirm_real = True
    if mode == "real":
        confirm_real = st.checkbox("Saya paham ini order live dengan uang sungguhan", key="confirm_real_order")

    cbtn1, cbtn2 = st.columns(2)
    with cbtn1:
        if st.button("🟢 Buka LONG", use_container_width=True, type="primary",
                      disabled=not confirm_real, key=f"btn_open_long_{mode}"):
            _execute_open(state, mode, exchange_name, symbol, timeframe, "LONG", mark_price,
                          leverage, margin_usdt, sl_price, tp1_price, tp2_price, client)
    with cbtn2:
        if st.button("🔴 Buka SHORT", use_container_width=True,
                      disabled=not confirm_real, key=f"btn_open_short_{mode}"):
            _execute_open(state, mode, exchange_name, symbol, timeframe, "SHORT", mark_price,
                          leverage, margin_usdt, sl_price, tp1_price, tp2_price, client)


def _execute_open(state: Dict[str, Any], mode: str, exchange_name: str, symbol: str, timeframe: str,
                   direction: str, price: float, leverage: int, margin_usdt: float,
                   sl: float, tp1: float, tp2: float, client: Any) -> None:
    if mode == "demo":
        pos, err = open_position(state, "demo", exchange_name, symbol, timeframe, direction,
                                  price, leverage, margin_usdt, sl, tp1, tp2)
        if err:
            st.error(err)
        else:
            st.success(f"✅ Posisi {direction} dibuka @ ${format_price(price, symbol)} (leverage {leverage}x)")
            st.rerun()
        return

    notional = margin_usdt * leverage
    try_set_leverage(client, symbol, leverage)
    amount = _amount_for_notional(client, symbol, notional, price)
    if amount <= 0:
        st.error("Ukuran order terlalu kecil, perbesar margin atau leverage.")
        return
    side = "buy" if direction == "LONG" else "sell"
    try:
        order = client.create_order(symbol, "market", side, amount)
        filled_price = float(order.get("average") or order.get("price") or price)
        filled_amount = float(order.get("filled") or amount)
    except Exception as e:
        st.error(f"❌ Gagal membuka posisi live: {e}")
        return

    pos = {
        "id": str(uuid.uuid4())[:8], "exchange": exchange_name, "symbol": symbol, "timeframe": timeframe,
        "direction": direction, "entry_price": filled_price, "qty": filled_amount,
        "leverage": int(leverage), "margin": float(margin_usdt), "notional": filled_amount * filled_price,
        "sl": float(sl) if sl else None, "tp1": float(tp1) if tp1 else None, "tp2": float(tp2) if tp2 else None,
        "liq_price": _calc_liq_price(direction, filled_price, leverage),
        "entry_time": datetime.now().isoformat(), "last_checked": datetime.now().isoformat(),
        "source": "manual", "status": "OPEN",
    }
    warn = try_place_native_protection(client, exchange_name, symbol, direction, filled_amount, sl, tp2)
    state["real"]["positions"].append(pos)
    save_wallet_state(state)
    st.success(f"✅ [LIVE] Posisi {direction} dibuka @ ${format_price(filled_price, symbol)} (leverage {leverage}x)")
    if warn:
        st.warning(f"⚠️ {warn} — pasang manual di exchange sebagai cadangan agar tetap terlindungi saat app offline.")
    st.rerun()


def _render_open_positions(state: Dict[str, Any], mode: str, mark_prices: Dict[str, float], client: Any) -> None:
    wallet = state[mode]
    positions = wallet.get("positions", [])
    st.markdown(f"#### 📌 Posisi Terbuka ({len(positions)})")
    if not positions:
        st.info("Belum ada posisi terbuka.")
        return
    for pos in positions:
        mp = mark_prices.get(pos["symbol"]) or pos["entry_price"]
        pnl, roi = _position_unrealized(pos, mp)
        color = "#00e676" if pnl > 0 else ("#ff5252" if pnl < 0 else "#d8e3ee")
        with st.container(border=True):
            if pos.get("_offline_alert"):
                st.warning(f"⚠️ {pos['_offline_alert']}")
            c1, c2, c3, c4, c5, c6 = st.columns([1.3, 1, 1, 1.3, 1, 1.2])
            src_badge = "🤖 Auto" if pos.get("source") == "auto-bot" else "🖐️ Manual"
            c1.markdown(f"**{'🟢' if pos['direction']=='LONG' else '🔴'} {pos['symbol']}** · {pos['leverage']}x · {src_badge}")
            c2.markdown(f"Entry\n`${format_price(pos['entry_price'], pos['symbol'])}`")
            c3.markdown(f"Mark\n`${format_price(mp, pos['symbol'])}`")
            c4.markdown(
                f"SL/TP1/TP2\n`{format_price(pos.get('sl'), pos['symbol'])}` / "
                f"`{format_price(pos.get('tp1'), pos['symbol'])}` / `{format_price(pos.get('tp2'), pos['symbol'])}`"
            )
            c5.markdown(f"Liq\n`${format_price(pos.get('liq_price'), pos['symbol'])}`")
            c6.markdown(
                f"<span style='color:{color}'>{pnl:+.2f} USDT<br/>({roi:+.2f}%)</span>",
                unsafe_allow_html=True
            )
            if st.button("✖️ Tutup Posisi", key=f"close_{mode}_{pos['id']}"):
                trade = close_position(state, mode, pos["id"], mp, "Manual Close", client)
                if trade:
                    st.success(f"Posisi ditutup: {trade['pnl_usdt']:+.2f} USDT ({trade['roi_pct']:+.2f}%)")
                    st.rerun()
                else:
                    st.error("Gagal menutup posisi (untuk mode Real, pastikan API masih terhubung).")


def _render_equity_history_chart(mode: str) -> None:
    history = load_trade_history_from_disk()
    history = [h for h in history if (h.get("sim_mode") or "").lower() == mode]
    balances = [{"time": h.get("exit_time"), "balance": h.get("balance_after")}
                for h in history if h.get("exit_time") and h.get("balance_after") is not None]
    if len(balances) < 2:
        return
    df_eq = pd.DataFrame(balances)
    df_eq["time"] = pd.to_datetime(df_eq["time"])
    df_eq = df_eq.sort_values("time").set_index("time")
    st.markdown("#### 📈 Riwayat Saldo (dari trade yang sudah ditutup)")
    st.line_chart(df_eq["balance"])


def render_persistent_trade_history_ui(symbol: str, mode_filter: Optional[str] = None) -> None:
    st.markdown("---")
    st.markdown("### 💾 Riwayat Trade Permanen (Tersimpan di Disk)")
    st.caption(
        "Setiap kali posisi ditutup (SL/TP/Liquidation/manual), trade langsung disimpan ke file di server — "
        "singkron otomatis dengan wallet & posisi di atas, dan tetap ada meski browser/tab kamu tutup atau "
        "halaman ini di-refresh. Gunakan tombol Export CSV di bawah sebagai cadangan tambahan."
    )

    history = load_trade_history_from_disk()
    if mode_filter:
        history = [h for h in history if (h.get("sim_mode") or "").lower() == mode_filter.lower()]

    hc1, hc2, hc3 = st.columns([1, 1, 2])
    with hc1:
        st.metric("Total Trade Tersimpan", len(history))
    with hc2:
        only_this_symbol = st.checkbox(f"Hanya {symbol}", value=False, key="history_filter_symbol")
    with hc3:
        st.write("")

    filtered = history
    if only_this_symbol:
        filtered = [h for h in history if h.get("symbol_context") == symbol]

    df_hist = trade_history_dataframe(filtered)
    if df_hist.empty:
        st.info("Belum ada riwayat trade permanen tersimpan.")
        return

    display_df = df_hist.copy()
    display_df = display_df.sort_values("exit_time", ascending=False)
    st.dataframe(display_df, use_container_width=True, height=320, hide_index=True)

    csv_bytes = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export Riwayat Trade (CSV)", data=csv_bytes,
        file_name=f"airise_trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv", use_container_width=True
    )


def render_wallet_trading_ui(exchange_name: str, symbol: str, timeframe: str, mtf_enabled: bool) -> None:
    st.markdown("### 💰 Wallet Trading — Futures Simulator")
    st.caption(
        "Wallet Demo memakai saldo virtual yang bisa kamu atur manual dan tersimpan permanen di server "
        "(cross margin — satu saldo dipakai bersama untuk semua posisi/coin). Wallet Real mengeksekusi "
        "order sungguhan ke exchange kamu. Posisi terbuka disimpan di disk (bukan hanya sesi browser) — "
        "saat kamu buka lagi appnya, sistem mengecek data candle historis untuk tahu apakah SL/TP/Liquidasi "
        "sempat tersentuh selagi kamu offline, lalu menyingkronkan otomatis."
    )

    mode_label = st.radio("Pilih Wallet", ["🧪 Demo", "🔴 Real"], horizontal=True, key="wallet_mode_choice")
    mode = "demo" if mode_label.startswith("🧪") else "real"

    refresh_sec = st.selectbox("Interval Refresh Harga/Posisi", [5, 10, 15, 30], index=1,
                                format_func=lambda s: f"{s}s", key="wallet_refresh_sec")
    st.caption(
        "ℹ️ Interval lebih pendek = lebih real-time, tapi lebih sering memanggil API exchange. Kalau muncul "
        "error 'Rate Limit Exceeded', perbesar interval ini (mis. 15s/30s)."
    )

    render_wallet_trading_fragment(exchange_name, symbol, timeframe, mtf_enabled, mode, refresh_sec)


def render_wallet_trading_fragment(exchange_name: str, symbol: str, timeframe: str, mtf_enabled: bool,
                                    mode: str, refresh_sec: int) -> None:
    def _body():
        _wallet_trading_body(exchange_name, symbol, timeframe, mtf_enabled, mode)

    if _fragment_decorator is None:
        _body()
        st.info("ℹ️ Update Streamlit ke versi >=1.37 agar wallet auto-refresh tanpa reload halaman.")
        return

    @_fragment_decorator(run_every=refresh_sec)
    def _fragment_body():
        _body()

    _fragment_body()


def _wallet_trading_body(exchange_name: str, symbol: str, timeframe: str, mtf_enabled: bool, mode: str) -> None:
    state = load_wallet_state()

    client = None
    if mode == "real":
        client = _render_real_wallet_connection(exchange_name)
    else:
        _render_demo_balance_editor(state)

    _render_auto_bot_panel(state, mode, exchange_name, symbol, timeframe, client)
    state = load_wallet_state()

    bot_events = run_auto_bot_catchup(state, mode, client)
    if bot_events:
        state = load_wallet_state()
        for ev in bot_events:
            if ev.get("opened"):
                st.toast(f"🤖 Auto-Bot membuka {ev['direction']} {ev['symbol']} @ ${format_price(ev['entry_price'], ev['symbol'])}")
            else:
                st.toast(f"🤖 Auto-Bot menutup {ev['symbol']} {ev['direction']} ({ev['exit_reason']}) {ev['pnl_usdt']:+.2f} USDT")

    closed_now = reconcile_wallet_positions(state, mode, client)
    if closed_now:
        state = load_wallet_state()
        for t in closed_now:
            st.toast(f"🔔 Posisi {t['symbol']} {t['direction']} ditutup ({t['exit_reason']}) {t['pnl_usdt']:+.2f} USDT")

    wallet = state[mode]

    symbols_needed = set(p["symbol"] for p in wallet.get("positions", [])) | {symbol}
    mark_prices: Dict[str, float] = {}
    for sym in symbols_needed:
        d = get_live_data(exchange_name, sym)
        mark_prices[sym] = d.get("price") or 0.0

    used_margin = wallet_used_margin(wallet)
    c1, c2, c3, c4 = st.columns(4)
    if mode == "demo":
        equity = wallet_equity(wallet, mark_prices)
        c1.metric("Equity (MTM)", f"${format_number(equity)}", format_percentage(safe_pct_change(equity, wallet["balance"])))
        c2.metric("Saldo Tersimpan", f"${format_number(wallet['balance'])}")
        c3.metric("Margin Terpakai", f"${format_number(used_margin)}")
        c4.metric("Margin Tersedia", f"${format_number(wallet['balance'] - used_margin)}")
    else:
        live_bal = None
        if client is not None:
            live_bal, _ = fetch_usdt_balance(client)
        c1.metric("Saldo USDT (Live)", f"${format_number(live_bal)}" if live_bal is not None else "-")
        c2.metric("Posisi Terbuka", len(wallet.get("positions", [])))
        c3.metric("Margin Terpakai (est.)", f"${format_number(used_margin)}")
        c4.metric("", "")

    st.divider()
    _render_order_form(state, mode, exchange_name, symbol, timeframe, client, mark_prices.get(symbol, 0.0))

    st.divider()
    _render_open_positions(state, mode, mark_prices, client)

    _render_equity_history_chart(mode)

    render_persistent_trade_history_ui(symbol, mode_filter=mode)


def render_telegram_ui() -> None:
    st.markdown("### 🤖 Telegram Bot")

    cfg = st.session_state.setdefault("telegram_cfg", {"enabled": False, "bot_token": "", "chat_id": ""})

    enabled = st.checkbox("Enable Telegram", value=cfg.get("enabled", False))
    cfg["enabled"] = enabled
    if enabled:
        c1, c2 = st.columns(2)
        with c1:
            cfg["bot_token"] = st.text_input("Bot Token", value=cfg.get("bot_token", ""), type="password")
        with c2:
            cfg["chat_id"] = st.text_input("Chat ID", value=cfg.get("chat_id", ""))

        if st.button("📱 Test Notification"):
            test_msg = f"✅ Test notification dari {BOT_NAME}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            if send_telegram_message(test_msg, cfg["bot_token"], cfg["chat_id"]):
                st.success("✅ Terkirim!")
            else:
                st.error("❌ Gagal! Cek Bot Token / Chat ID.")

def render_mtf_ui() -> bool:
    st.markdown("### ⏱️ Multi-Timeframe")
    st.info("Kalau aktif: sinyal BUY/SELL di timeframe utama dicek ulang terhadap 1 timeframe "
            "lebih besar. Kalau berlawanan arah, sinyal otomatis didinginkan jadi HOLD (dipakai di "
            "tab Analisa dan Coin Scanner).")
    return st.checkbox("Enable MTF", value=True)

# =============================================================================
# STYLE — BACKGROUND & LOGO (TEMA ROBOT/MECHA BIRU-PUTIH, SESUAI LOGO AIRISE)
# =============================================================================

def inject_transformer_theme() -> None:
    css = f"""
<style>
html {{
    scroll-behavior: smooth;
}}
.stApp, .main, section[data-testid="stSidebar"],
div[data-testid="stVerticalBlock"], div[data-testid="stDataFrame"],
.block-container {{
    -webkit-overflow-scrolling: touch;
    scroll-behavior: smooth;
}}
* {{
    -webkit-tap-highlight-color: transparent;
}}
.stApp {{
    font-size: 12px;
    overscroll-behavior-y: contain;
    background:
        radial-gradient(circle at 15% 10%, rgba(0,229,255,0.10) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(255,61,61,0.08) 0%, transparent 40%),
        repeating-linear-gradient(135deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 2px, transparent 2px, transparent 26px),
        linear-gradient(160deg, #10161d 0%, #1b2530 45%, #0d1218 100%);
    background-attachment: fixed;
    transform: translateZ(0);
    will-change: scroll-position;
}}
.airise-header {{
    display: flex; align-items: center; gap: 14px;
    padding: 14px 20px; margin-bottom: 6px;
    border-radius: 14px;
    background: linear-gradient(90deg, rgba(41,121,255,0.14), rgba(0,0,0,0));
    border: 1px solid rgba(0,229,255,0.25);
    box-shadow: 0 0 18px rgba(0,229,255,0.08) inset;
}}
.airise-title {{
    font-size: 26px; font-weight: 800; letter-spacing: 1px;
    background: linear-gradient(90deg, #2f7fd6, #6fa8dc, #2f7fd6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0;
}}
.airise-tagline {{
    font-size: 12px; color: #8aa0b5; margin: 0; letter-spacing: 0.5px;
}}
.airise-menu-btn button {{
    background: linear-gradient(90deg, #2979ff, #00e5ff) !important;
    color: #08131c !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
}}
div[data-testid="stMetric"] {{
    font-size: 12px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 8px 10px 6px 10px;
}}
div[data-testid="stMetric"] label,
div[data-testid="stMetricLabel"] {{
    font-size: 10px !important;
    color: #8aa0b5 !important;
    white-space: normal !important;
}}
div[data-testid="stMetricValue"] {{
    font-size: 15px !important;
    line-height: 1.2 !important;
}}
div[data-testid="stMetricDelta"] {{
    font-size: 10.5px !important;
}}
div[data-testid="column"] {{
    padding: 0 4px;
}}
.stButton button {{
    font-size: 12px; padding: 4px 12px;
    border: 1px solid rgba(0,229,255,0.3) !important;
}}
.stDataFrame {{ font-size: 11px; }}
.signal-buy {{ background: #1a3a1a; color: #00ff88; padding: 4px 12px; border-radius: 12px; border: 1px solid #00ff8855; }}
.signal-sell {{ background: #3a1a1a; color: #ff5555; padding: 4px 12px; border-radius: 12px; border: 1px solid #ff555555; }}
.signal-hold {{ background: #3a3a1a; color: #ffe600; padding: 4px 12px; border-radius: 12px; border: 1px solid #ffe60055; }}
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #131a22 0%, #0d1218 100%);
    border-right: 1px solid rgba(0,229,255,0.15);
}}
.airise-nav-active button {{
    background: linear-gradient(90deg, #2979ff, #00e5ff) !important;
    color: #08131c !important;
    font-weight: 800 !important;
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)

def render_sidebar_toggle_button() -> None:
    if "sidebar_open" not in st.session_state:
        st.session_state.sidebar_open = True

    label = "☰ Tutup Menu" if st.session_state.sidebar_open else "☰ Buka Menu"
    st.markdown('<div class="airise-menu-btn">', unsafe_allow_html=True)
    if st.button(label, key="sidebar_toggle_btn", use_container_width=False):
        st.session_state.sidebar_open = not st.session_state.sidebar_open
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if not st.session_state.sidebar_open:
        st.markdown(
            """<style>
            section[data-testid="stSidebar"] { display: none !important; }
            </style>""",
            unsafe_allow_html=True
        )

def render_header() -> None:
    logo_img = render_logo_img(height_px=56)
    header_html = (
        f'<div class="airise-header">{logo_img}'
        f'<div><p class="airise-title">{BOT_NAME}</p>'
        f'<p class="airise-tagline">{BOT_TAGLINE} · 7 Indikator + MTF nyata + Market Cap/Trending + Live Price + Coin Scanner</p>'
        f'</div></div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)
    if not logo_file_found():
        st.caption(
            "ℹ️ File logo `assets/airise_logo.png` belum ditemukan di server — memakai ikon robot vektor "
            "bawaan sebagai gantinya. Untuk memakai logo PNG kamu sendiri, upload file ke salah satu folder: "
            + ", ".join(f"`{p}`" for p in LOGO_CANDIDATE_PATHS)
        )

# =============================================================================
# LOGIN GATE
# =============================================================================

def inject_login_theme() -> None:
    css = """
<style>
html { scroll-behavior: smooth; }
.block-container {
    max-width: 380px !important;
    padding-top: 4.5rem !important;
    padding-bottom: 2rem !important;
}
.login-logo-wrap {
    display: flex;
    justify-content: center;
    margin-bottom: 4px;
}
.login-title {
    text-align: center;
    font-size: 25px;
    font-weight: 800;
    letter-spacing: 1px;
    background: linear-gradient(90deg, #2f7fd6, #6fa8dc, #2f7fd6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 4px 0 2px 0;
}
.login-subtitle {
    text-align: center;
    color: #8aa0b5;
    font-size: 12.5px;
    margin-bottom: 20px;
}
div[data-testid="stForm"] {
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(0,229,255,0.18);
    border-radius: 14px;
    padding: 26px 24px 20px 24px;
    box-shadow: 0 8px 28px rgba(0,0,0,0.35);
}
div[data-testid="stForm"] .stTextInput input {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13px;
    color: #e6eef5;
}
div[data-testid="stForm"] .stTextInput input:focus {
    border-color: #00e5ff;
    box-shadow: 0 0 0 2px rgba(0,229,255,0.18);
}
div[data-testid="stForm"] label p {
    font-size: 11.5px !important;
    color: #8aa0b5 !important;
}
div[data-testid="stFormSubmitButton"] button {
    width: 100%;
    background: linear-gradient(90deg, #2979ff, #00e5ff);
    border: none;
    border-radius: 8px;
    padding: 10px 0;
    font-weight: 700;
    font-size: 13.5px;
    color: #08131c;
    margin-top: 8px;
}
div[data-testid="stFormSubmitButton"] button:hover {
    filter: brightness(1.08);
}
.login-divider {
    display: flex;
    align-items: center;
    text-align: center;
    color: #5c7188;
    font-size: 11px;
    margin: 18px 0 14px 0;
}
.login-divider::before, .login-divider::after {
    content: "";
    flex: 1;
    border-bottom: 1px solid rgba(255,255,255,0.12);
}
.login-divider::before { margin-right: 10px; }
.login-divider::after { margin-left: 10px; }
.login-footnote {
    text-align: center;
    color: #5c7188;
    font-size: 11px;
    margin-top: 18px;
    line-height: 1.5;
}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)

def render_login_page() -> None:
    logo_img = render_logo_img(height_px=110)
    st.markdown(f'<div class="login-logo-wrap">{logo_img}</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="login-title">{BOT_NAME}</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="login-subtitle">Masuk untuk mengakses Analyzer &amp; Live Trading</p>',
        unsafe_allow_html=True
    )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Username")
        password = st.text_input("PIN / Password", type="password", placeholder="PIN / Password")
        submitted = st.form_submit_button("Log In")

    if submitted:
        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            st.session_state["authenticated"] = True
            st.session_state["login_attempts"] = 0
            st.rerun()
        else:
            st.session_state["login_attempts"] = st.session_state.get("login_attempts", 0) + 1
            st.error("Username atau PIN salah. Coba lagi.")

    st.markdown('<div class="login-divider">AIRISE BOT</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="login-footnote">🔒 Halaman ini melindungi akses ke fitur Live Trading.<br>'
        'Jangan bagikan Username/PIN ke siapa pun.</p>',
        unsafe_allow_html=True
    )

def render_logout_button() -> None:
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

# =============================================================================
# NAVIGASI UTAMA (pengganti st.tabs)
# =============================================================================

SECTION_LABELS: Dict[str, str] = {
    "chart": "📊 Grafik & Analisa Sinyal",
    "sim": "💰 Wallet Trading",
    "scanner": "📡 Coin Scanner",
    "market": "📈 Market Cap & Trending",
}

def render_main_navigation() -> str:
    if "active_section" not in st.session_state:
        st.session_state.active_section = "chart"

    keys = list(SECTION_LABELS.keys())
    cols = st.columns(len(keys))
    for i, key in enumerate(keys):
        is_active = st.session_state.active_section == key
        wrapper_class = "airise-nav-active" if is_active else ""
        with cols[i]:
            st.markdown(f'<div class="{wrapper_class}">', unsafe_allow_html=True)
            if st.button(SECTION_LABELS[key], key=f"nav_btn_{key}", use_container_width=True):
                st.session_state.active_section = key
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state.active_section

# =============================================================================
# MAIN APP
# =============================================================================

def main() -> None:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    page_layout = "centered" if not st.session_state.authenticated else "wide"
    st.set_page_config(page_title=BOT_NAME, page_icon="🤖", layout=page_layout, initial_sidebar_state="expanded")

    inject_transformer_theme()

    if not st.session_state.authenticated:
        inject_login_theme()
        render_login_page()
        st.stop()

    render_header()
    render_sidebar_toggle_button()
    st.warning("⚠️ Bukan nasihat keuangan. Selalu DYOR!")

    if "selected_symbol" not in st.session_state:
        st.session_state.selected_symbol = "BTC/USDT"
    if "exchange_name" not in st.session_state:
        st.session_state.exchange_name = next(iter(EXCHANGES.keys()))
    if "timeframe" not in st.session_state:
        st.session_state.timeframe = "15m"

    with st.sidebar:
        st.markdown(f"### ⚙️ {BOT_NAME} Settings")
        render_logout_button()
        st.divider()

        exchange_name = st.selectbox(
            "Exchange",
            list(EXCHANGES.keys()),
            index=list(EXCHANGES.keys()).index(st.session_state.exchange_name) if st.session_state.exchange_name in EXCHANGES else 0
        )
        st.session_state.exchange_name = exchange_name

        timeframe = st.selectbox(
            "Timeframe",
            TIMEFRAMES,
            index=TIMEFRAMES.index(st.session_state.timeframe) if st.session_state.timeframe in TIMEFRAMES else 2
        )
        st.session_state.timeframe = timeframe

        limit = st.slider("Candles", 100, 500, 300, 50)

        st.divider()
        mtf_enabled = render_mtf_ui()

        st.divider()
        st.markdown("### 🔄 Auto-Refresh")
        live_price_refresh = st.selectbox("Interval Harga Live", [2, 3, 5, 10], index=1,
                                           format_func=lambda s: f"{s}s", key="live_price_refresh_sec")
        auto_refresh_chart = st.checkbox("Auto-refresh Grafik & Sinyal", value=True, key="auto_refresh_chart")
        chart_refresh_sec = st.selectbox("Interval Grafik", [10, 15, 20, 30, 60], index=1,
                                          format_func=lambda s: f"{s}s", key="chart_refresh_sec",
                                          disabled=not auto_refresh_chart)

        st.divider()
        render_telegram_ui()

        st.divider()
        st.markdown("### 🔗 Symbol")

        try:
            all_symbols = get_symbols(exchange_name)
        except Exception as e:
            st.warning(f"Gagal load symbol dari exchange ({e}). Pakai daftar default.")
            all_symbols = POPULAR_SYMBOLS

        if all_symbols:
            resolved_default = resolve_symbol(st.session_state.selected_symbol, all_symbols)
            if resolved_default and resolved_default != st.session_state.selected_symbol:
                st.session_state.selected_symbol = resolved_default
            elif resolved_default is None:
                st.session_state.selected_symbol = resolve_symbol("BTC/USDT", all_symbols) or all_symbols[0]

        st.markdown(f"**Selected:** `{st.session_state.selected_symbol}`")

        st.markdown("**Popular:**")
        cols = st.columns(3)
        for i, sym in enumerate(POPULAR_SYMBOLS[:6]):
            resolved = resolve_symbol(sym, all_symbols)
            if resolved and cols[i % 3].button(sym, use_container_width=True, key=f"pop_{sym}"):
                st.session_state.selected_symbol = resolved
                st.rerun()

        search = st.text_input("🔍", placeholder="Search symbol...", key="search_symbol").strip().upper()

        if search:
            filtered = [s for s in all_symbols if search in s]
            if filtered:
                idx = 0
                if st.session_state.selected_symbol in filtered:
                    idx = filtered.index(st.session_state.selected_symbol)
                picked = st.selectbox(f"Results ({len(filtered)})", filtered, index=min(idx, len(filtered) - 1))
                if picked != st.session_state.selected_symbol:
                    st.session_state.selected_symbol = picked
                    st.rerun()
            else:
                st.warning("No symbols found")
        else:
            if all_symbols:
                idx = all_symbols.index(st.session_state.selected_symbol) if st.session_state.selected_symbol in all_symbols else 0
                picked = st.selectbox(f"All ({len(all_symbols)})", all_symbols, index=min(idx, len(all_symbols) - 1))
                if picked != st.session_state.selected_symbol:
                    st.session_state.selected_symbol = picked
                    st.rerun()

        st.divider()
        st.caption("💡 Harga live, Grafik/Sinyal, dan Wallet Trading auto-refresh sendiri (st.fragment). "
                   "Klik coin di Coin Scanner / Market Cap untuk langsung lompat ke Grafik & Analisa.")

    symbol = st.session_state.selected_symbol
    exchange_name = st.session_state.exchange_name
    timeframe = st.session_state.timeframe

    init_telegram_if_enabled()

    render_live_price_fragment(exchange_name, symbol, refresh_sec=live_price_refresh)
    st.divider()

    st.markdown(f"### 📊 {symbol} · {exchange_name} · {timeframe}")

    active_section = render_main_navigation()
    st.divider()

    if active_section == "chart":
        render_analysis_fragment(exchange_name, symbol, timeframe, limit, mtf_enabled,
                                  chart_refresh_sec, auto_refresh_chart)
    elif active_section == "sim":
        render_wallet_trading_ui(exchange_name, symbol, timeframe, mtf_enabled)
    elif active_section == "scanner":
        render_coin_scanner_ui(exchange_name, timeframe, mtf_enabled)
    elif active_section == "market":
        render_market_overview_ui()

if __name__ == "__main__":
    main()