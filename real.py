# =============================================================================
# AIRISE BOT - CRYPTO FUTURES ANALYZER PRO
# =============================================================================

from __future__ import annotations
import requests
import json
import os
import re
import base64
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

# --- Login (lihat catatan keamanan di bagian render_login_page) ---
LOGIN_USERNAME: str = "Swijaya07"
LOGIN_PASSWORD: str = "000000"

EXCHANGES: Dict[str, Dict[str, Any]] = {
    "OKX": {"id": ["okx"], "options": {"defaultType": "swap"}},
    # Sejak ccxt v4, class Gate.io di-rename dari 'gateio' menjadi 'gate'.
    # Simpan beberapa kandidat nama supaya cocok di versi ccxt lama maupun baru.
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

# Daftar coin untuk fitur Coin Scanner (bisa diedit di sidebar Scanner juga).
SCANNER_DEFAULT_SYMBOLS: List[str] = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "TON/USDT",
    "DOT/USDT", "TRX/USDT", "MATIC/USDT", "LTC/USDT", "SHIB/USDT",
    "NEAR/USDT", "APT/USDT", "ARB/USDT", "OP/USDT", "SUI/USDT",
]

# --- "Coin Micin" mode: scan coin murah ($0-$5) dalam jumlah besar sekaligus ---
SCANNER_MAX_SYMBOLS: int = 150
MICIN_PRICE_MIN: float = 0.0
MICIN_PRICE_MAX: float = 5.0
MICIN_DEFAULT_COUNT: int = 100

# =============================================================================
# LOGO
# =============================================================================
# Logo AIRISE dipakai sebagai file gambar (PNG) yang di-embed sebagai base64,
# bukan digambar ulang manual, supaya hasilnya persis sama dengan file asli.
LOGO_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "airise_logo.png")

@st.cache_data(show_spinner=False)
def _load_logo_base64(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

def render_logo_img(height_px: int = 64, extra_style: str = "") -> str:
    """Hasilkan tag <img> base64 dari logo AIRISE. Fallback ke emoji robot kalau file logo tidak ditemukan."""
    b64 = _load_logo_base64(LOGO_PATH)
    if not b64:
        return f'<span style="font-size:{height_px}px;">🤖</span>'
    return (f'<img src="data:image/png;base64,{b64}" '
            f'style="height:{height_px}px; width:auto; display:block; {extra_style}" alt="AIRISE logo" />')

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_price(price: Optional[float], symbol: str = "") -> str:
    """Format harga dengan desimal yang sesuai untuk setiap coin"""
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
    """Hitung persentase perubahan dengan aman (hindari ZeroDivisionError)."""
    if target is None or base is None or base == 0:
        return 0.0
    try:
        if np.isnan(target) or np.isnan(base):
            return 0.0
    except TypeError:
        return 0.0
    return (target / base - 1) * 100

def send_telegram_message(message: str, bot_token: str, chat_id: str) -> bool:
    """Send message to Telegram"""
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
    """Cari class exchange ccxt dari daftar kandidat nama (id) — dipakai karena
    beberapa exchange di ccxt pernah berganti nama antar versi library
    (mis. Gate.io: 'gateio' -> 'gate' sejak ccxt v4). Coba tiap kandidat
    berurutan, pakai yang pertama ada; kalau tidak ada satupun, lempar error
    yang jelas menyebutkan semua nama yang sudah dicoba (bukan cuma AttributeError
    generik dari getattr biasa)."""
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
    """Cocokkan symbol populer (mis. 'BTC/USDT') ke format spesifik exchange
    (mis. OKX/Gate.io swap sering pakai 'BTC/USDT:USDT')."""
    if target in all_symbols:
        return target
    base = target.split("/")[0]
    for s in all_symbols:
        if s.startswith(f"{base}/USDT"):
            return s
    return None

@st.cache_data(ttl=30, show_spinner=False)
def get_ohlcv(exchange_name: str, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    try:
        exchange = get_exchange(exchange_name)
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
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
    """Ambil ticker SEMUA symbol sekaligus dalam 1 request (exchange.fetch_tickers())."""
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
    """Ambil funding rate futures (bias market maker/positioning). Return None kalau
    exchange/symbol tidak mendukung endpoint ini (fail-safe, jangan sampai bikin error)."""
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
    """Konfirmasi sinyal timeframe utama terhadap timeframe LEBIH BESAR (mengisi
    fitur 'Enable MTF' yang sebelumnya cuma checkbox tanpa logika sama sekali).

    Aturan:
    - Ambil 1 timeframe lebih tinggi dari MTF_HIGHER, hitung sinyalnya juga.
    - Kalau arah HTF SAMA dengan arah sinyal utama -> skor ditambah bonus &
      status "Aligned" (lebih dipercaya).
    - Kalau arah HTF BERLAWANAN -> skor dikurangi/didinginkan, dan kalau
      sinyal awalnya BUY/SELL, di-downgrade jadi HOLD (menandakan konflik
      antar timeframe, jangan entry melawan tren besar).
    - Kalau HTF juga HOLD/data kurang -> tidak ada perubahan, cuma ditandai
      "Netral / tidak cukup data".
    """
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
            # Downgrade jadi HOLD kalau melawan tren timeframe lebih besar
            signal.direction = "HOLD"
            signal.is_actionable = False
            signal.confidence = "Rendah (konflik MTF)"

    return signal


def compute_pump_score(df: pd.DataFrame) -> Tuple[float, List[str]]:
    """Heuristik terpisah dari signal engine utama, khusus untuk menandai coin
    yang MULAI menunjukkan tanda-tanda awal 'pump' (lonjakan momentum jangka
    pendek) — sering dicari di coin micin ber-cap kecil/murah. Ini BUKAN
    prediksi, hanya kombinasi beberapa pola teknikal yang sering muncul di awal
    pergerakan naik cepat: lonjakan volume, RSI baru bangkit dari area rendah,
    histogram MACD berbalik naik, dan breakout dari BB midline.
    Return: (pump_score 0-10, list tag alasan singkat)"""
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
# PENJELASAN DETAIL UNTUK "REASONS" (mudah dipahami, non-teknis)
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
# LIVE SIMULATOR / LIVE TRADING ENGINE
# =============================================================================
# Dua mode:
#   - "SIM"  -> paper trading, tidak menyentuh akun exchange sama sekali.
#   - "LIVE" -> mengeksekusi order MARKET sungguhan ke akun futures kamu
#               memakai API key yang kamu masukkan sendiri di sesi ini.
#
# PENTING (baca sebelum pakai mode LIVE):
# - Bot memantau SL/TP dengan cara mengecek harga tiap tick lalu mengirim
#   market close order sendiri. Artinya kalau bot berhenti / koneksi putus,
#   posisi TIDAK otomatis terlindungi oleh exchange (beda dari native
#   stop-order). Untuk exchange yang didukung, bot mencoba memasang native
#   STOP_MARKET/TAKE_PROFIT_MARKET sebagai jaring pengaman tambahan
#   (best-effort, tidak menggantikan pemantauan bot).
# - API key/secret hanya disimpan di st.session_state (memori server selama
#   sesi berjalan), tidak ditulis ke disk atau dikirim ke pihak ketiga.
# - Selalu pakai API key dengan pembatasan IP & TANPA izin withdraw.

SIM_STATE_KEY: str = "live_sim"
LIVE_CREDS_KEY: str = "live_creds"
CONFIRM_PHRASE: str = "SAYA PAHAM RISIKONYA"

def _empty_sim_state(initial_capital: float, risk_per_trade: float, context: Tuple[str, str, str]) -> Dict[str, Any]:
    now = datetime.now()
    return {
        "context": context,
        "mode": "SIM",
        "running": False,
        "armed": False,
        "initial_capital": initial_capital,
        "capital": initial_capital,
        "risk_per_trade": risk_per_trade,
        "max_position_usdt": 100.0,
        "leverage": 5,
        "daily_loss_limit_pct": 5.0,
        "session_start_balance": initial_capital,
        "kill_switch_triggered": False,
        "position": None,
        "trades": [],
        "equity_curve": [{"time": now, "equity": initial_capital}],
        "last_signal": None,
        "last_update": None,
        "tick_count": 0,
        "log": [],
    }

def get_sim_state(exchange_name: str, symbol: str, timeframe: str,
                   initial_capital: float, risk_per_trade: float) -> Dict[str, Any]:
    context = (exchange_name, symbol, timeframe)
    sim = st.session_state.get(SIM_STATE_KEY)
    if sim is None or sim["context"] != context:
        sim = _empty_sim_state(initial_capital, risk_per_trade, context)
        st.session_state[SIM_STATE_KEY] = sim
    return sim

def reset_sim_state(exchange_name: str, symbol: str, timeframe: str,
                     initial_capital: float, risk_per_trade: float) -> None:
    st.session_state[SIM_STATE_KEY] = _empty_sim_state(initial_capital, risk_per_trade, (exchange_name, symbol, timeframe))

def _sim_log(sim: Dict[str, Any], msg: str) -> None:
    sim["log"].insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sim["log"] = sim["log"][:50]

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

def place_live_entry(client: Any, symbol: str, direction: str, usdt_notional: float,
                      leverage: int) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    try:
        ticker = client.fetch_ticker(symbol)
        price = ticker.get("last") or ticker.get("close")
        try_set_leverage(client, symbol, leverage)
        amount = _amount_for_notional(client, symbol, usdt_notional, price)
        if amount <= 0:
            return None, None, None, "Ukuran order terlalu kecil (cek Max Position USDT)."
        side = "buy" if direction == "LONG" else "sell"
        order = client.create_order(symbol, "market", side, amount)
        filled_price = order.get("average") or order.get("price") or price
        filled_amount = order.get("filled") or amount
        return float(filled_price), float(filled_amount), order.get("id"), None
    except Exception as e:
        return None, None, None, str(e)

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
                                 amount: float, sl: float, tp2: float) -> None:
    # Catatan: sebelumnya fitur ini hanya aktif untuk "Binance Futures" (order type
    # STOP_MARKET/TAKE_PROFIT_MARKET khas Binance). Karena Binance Futures sudah
    # dihilangkan dari daftar exchange (lihat EXCHANGES), fungsi ini untuk saat ini
    # selalu no-op (aman, tidak error) sampai native stop-order khusus OKX/Gate.io
    # ditambahkan. Bot tetap memantau SL/TP sendiri lewat simulate_live_step().
    return

def cancel_all_open_orders(client: Any, symbol: str) -> None:
    try:
        client.cancel_all_orders(symbol)
    except Exception:
        pass

def _close_trade_and_update_capital(sim: Dict[str, Any], pos: Dict[str, Any], exit_price: float,
                                     exit_reason: str, now: datetime) -> Dict[str, Any]:
    """FIX: sebelumnya capital di-update dengan `capital *= (1 + profit_pct/100)`,
    artinya SELURUH capital dianggap ikut bergerak sebesar %-perubahan harga —
    ini membuat slider 'Risk per Trade' dan 'Leverage' tidak berpengaruh sama
    sekali ke hasil simulasi (entry $100 atau $10000 hasilnya identik).
    Sekarang PnL dihitung dalam USDT riil = position_size (unit koin) x selisih
    harga, baru ditambahkan ke capital — jadi position sizing & leverage benar2
    memengaruhi hasil, sama seperti trading futures sungguhan."""
    if pos["direction"] == "LONG":
        pnl_usdt = pos["position_size"] * (exit_price - pos["entry_price"])
    else:
        pnl_usdt = pos["position_size"] * (pos["entry_price"] - exit_price)

    profit_pct = (safe_pct_change(exit_price, pos["entry_price"]) if pos["direction"] == "LONG"
                  else safe_pct_change(pos["entry_price"], exit_price))

    sim["capital"] += pnl_usdt
    trade = dict(pos)
    trade.update({
        "exit_time": now, "exit_price": exit_price,
        "profit_pct": profit_pct, "pnl_usdt": pnl_usdt, "exit_reason": exit_reason,
        "final_capital": sim["capital"]
    })
    sim["trades"].append(trade)
    sim["position"] = None
    return trade

def simulate_live_step(exchange_name: str, symbol: str, timeframe: str, limit: int = 300,
                        mtf_enabled: bool = True) -> Optional[str]:
    sim = st.session_state.get(SIM_STATE_KEY)
    if sim is None or not sim.get("running", False):
        return None

    if sim["mode"] == "LIVE" and not sim.get("armed", False):
        sim["running"] = False
        return "⚠️ Mode LIVE belum di-arm. Simulasi dihentikan."

    df = get_ohlcv(exchange_name, symbol, timeframe, limit)
    if df.empty or len(df) < 55:
        return "Data candle belum cukup."
    df = add_indicators(df)
    signal = analyze_single_timeframe(df)
    if mtf_enabled:
        signal = apply_mtf_confirmation(signal, exchange_name, symbol, timeframe, limit=min(limit, 250))

    live = get_live_data(exchange_name, symbol)
    price = live.get("price") or float(df.iloc[-1]["close"])
    now = datetime.now()

    sim["last_signal"] = signal
    sim["last_update"] = now
    sim["tick_count"] += 1

    is_live = sim["mode"] == "LIVE"
    client = None
    if is_live:
        creds = st.session_state.get(LIVE_CREDS_KEY, {})
        client = creds.get("client")
        if client is None:
            sim["running"] = False
            return "❌ Koneksi exchange live tidak ditemukan. Simulasi dihentikan."

    status_msg = None
    pos = sim["position"]

    if pos is not None:
        pos["current_price"] = price
        if pos["direction"] == "LONG":
            pos["unrealized_pnl"] = safe_pct_change(price, pos["entry_price"])
            pos["unrealized_pnl_usdt"] = pos["position_size"] * (price - pos["entry_price"])
        else:
            pos["unrealized_pnl"] = safe_pct_change(pos["entry_price"], price)
            pos["unrealized_pnl_usdt"] = pos["position_size"] * (pos["entry_price"] - price)

        exit_reason = None
        if pos["direction"] == "LONG":
            if price <= pos["sl"]:
                exit_reason = "SL Hit"
            elif price >= pos["tp2"]:
                exit_reason = "TP2 Hit"
            elif price >= pos["tp1"]:
                exit_reason = "TP1 Hit"
            elif signal.direction == "SELL" and signal.score < -2.5:
                exit_reason = "Reverse Signal"
        else:
            if price >= pos["sl"]:
                exit_reason = "SL Hit"
            elif price <= pos["tp2"]:
                exit_reason = "TP2 Hit"
            elif price <= pos["tp1"]:
                exit_reason = "TP1 Hit"
            elif signal.direction == "BUY" and signal.score > 2.5:
                exit_reason = "Reverse Signal"

        if exit_reason is not None:
            if is_live:
                fill_price, err = place_live_exit(client, symbol, pos["direction"], pos["position_size"])
                cancel_all_open_orders(client, symbol)
                if err:
                    _sim_log(sim, f"❌ Gagal close posisi live: {err}")
                    status_msg = f"❌ Gagal menutup posisi live: {err}"
                    exit_reason = None
                else:
                    exit_price = fill_price
            else:
                exit_price = {"SL Hit": pos["sl"], "TP2 Hit": pos["tp2"], "TP1 Hit": pos["tp1"]}.get(exit_reason, price)

            if exit_reason is not None:
                trade = _close_trade_and_update_capital(sim, pos, exit_price, exit_reason, now)
                pos = None
                status_msg = f"🔔 Posisi {trade['direction']} ditutup ({exit_reason}) {trade['profit_pct']:+.2f}% ({trade['pnl_usdt']:+.2f} USDT)"
                _sim_log(sim, status_msg)

    drawdown_pct = safe_pct_change(sim["capital"], sim["session_start_balance"])
    if is_live and pos is None and drawdown_pct <= -abs(sim["daily_loss_limit_pct"]) and not sim["kill_switch_triggered"]:
        sim["kill_switch_triggered"] = True
        sim["running"] = False
        sim["armed"] = False
        _sim_log(sim, f"🛑 KILL SWITCH aktif: drawdown {drawdown_pct:.2f}% >= limit {sim['daily_loss_limit_pct']}%. Trading live dihentikan.")
        return f"🛑 Kill switch aktif — trading live dihentikan otomatis (drawdown {drawdown_pct:.2f}%)."

    if pos is None and not sim["kill_switch_triggered"] and signal.direction in ("BUY", "SELL"):
        atr = float(df.iloc[-1].get("atr_14", np.nan))
        atr = atr if (atr and not np.isnan(atr) and atr > 0) else price * 0.01
        direction = "LONG" if signal.direction == "BUY" else "SHORT"
        if direction == "LONG":
            sl = price - 1.5 * atr
            tp1 = price + 1.5 * (price - sl)
            tp2 = price + 3.0 * (price - sl)
        else:
            sl = price + 1.5 * atr
            tp1 = price - 1.5 * (sl - price)
            tp2 = price - 3.0 * (sl - price)

        risk_amount = sim["capital"] * sim["risk_per_trade"]
        risk_dist = abs(price - sl)
        position_size = risk_amount / risk_dist if risk_dist > 0 else 0

        if is_live:
            notional = min(sim["max_position_usdt"], sim["capital"] * sim["risk_per_trade"] * sim["leverage"])
            filled_price, filled_amount, order_id, err = place_live_entry(client, symbol, direction, notional, sim["leverage"])
            if err:
                _sim_log(sim, f"❌ Gagal buka posisi live: {err}")
                status_msg = f"❌ Gagal membuka posisi live: {err}"
            else:
                entry_price = filled_price
                position_size = filled_amount
                try_place_native_protection(client, exchange_name, symbol, direction, filled_amount, sl, tp2)
                sim["position"] = {
                    "entry_time": now, "direction": direction,
                    "entry_price": entry_price, "sl": sl, "tp1": tp1, "tp2": tp2,
                    "position_size": position_size, "current_price": entry_price,
                    "unrealized_pnl": 0.0, "unrealized_pnl_usdt": 0.0, "order_id": order_id
                }
                status_msg = f"🚀 [LIVE] Posisi {direction} dibuka @ {format_price(entry_price, symbol)} ({format_number(filled_amount,6)} unit)"
                _sim_log(sim, status_msg)
        else:
            sim["position"] = {
                "entry_time": now, "direction": direction,
                "entry_price": price, "sl": sl, "tp1": tp1, "tp2": tp2,
                "position_size": position_size, "current_price": price,
                "unrealized_pnl": 0.0, "unrealized_pnl_usdt": 0.0
            }
            status_msg = f"🚀 Posisi {direction} dibuka @ {format_price(price, symbol)} (size {position_size:.6f} unit)"
            _sim_log(sim, status_msg)

    unrealized_usdt = sim["position"]["unrealized_pnl_usdt"] if sim["position"] else 0.0
    mtm_equity = sim["capital"] + unrealized_usdt
    sim["equity_curve"].append({"time": now, "equity": mtm_equity})
    if len(sim["equity_curve"]) > 500:
        sim["equity_curve"] = sim["equity_curve"][-500:]

    return status_msg

def emergency_close_live_position(exchange_name: str, symbol: str) -> str:
    sim = st.session_state.get(SIM_STATE_KEY)
    creds = st.session_state.get(LIVE_CREDS_KEY, {})
    client = creds.get("client")
    if sim is None or sim["position"] is None:
        return "Tidak ada posisi terbuka."
    if client is None:
        return "Tidak ada koneksi exchange live."
    pos = sim["position"]
    fill_price, err = place_live_exit(client, symbol, pos["direction"], pos["position_size"])
    cancel_all_open_orders(client, symbol)
    if err:
        return f"❌ Gagal emergency close: {err}"
    trade = _close_trade_and_update_capital(sim, pos, fill_price, "Emergency Stop", datetime.now())
    sim["running"] = False
    _sim_log(sim, f"🛑 Emergency close: {trade['profit_pct']:+.2f}% ({trade['pnl_usdt']:+.2f} USDT)")
    return f"✅ Posisi ditutup manual ({trade['profit_pct']:+.2f}%)."


# =============================================================================
# COIN SCANNER — REKOMENDASI MULTI-COIN (BUY / SELL / HOLD)
# =============================================================================
# Update: scanner sekarang memakai signal engine YANG SAMA dengan tab Analisa,
# termasuk konfirmasi MTF (kalau diaktifkan di sidebar) dan funding rate
# (bias positioning pasar futures) supaya hasil scan lebih konsisten dengan
# kondisi bursa/tren pasar saat itu, bukan cuma snapshot 1 timeframe.

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
    else:
        st.caption("Tidak ada coin dengan sinyal BUY aktif (score ≥ 3.0" + (", dan selaras MTF" if mtf_enabled else "") + ") saat ini.")

    st.markdown(f"#### 🔴 Rekomendasi SELL ({len(sell_df)})")
    if not sell_df.empty:
        st.dataframe(_style_table(sell_df), use_container_width=True, hide_index=True)
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


# Kompatibilitas: st.fragment stabil sejak Streamlit ~1.37, sebelumnya bernama
# st.experimental_fragment (>=1.33). Fallback ke rerender biasa kalau tidak ada.
_fragment_decorator = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)


def render_live_price_fragment(exchange_name: str, symbol: str, refresh_sec: int = 5) -> None:
    """FIX UTAMA (harga live 'diam'/tidak bergerak): sebelumnya render_live_price_ui()
    dipanggil langsung di badan main(), yang HANYA dieksekusi ulang saat ada
    interaksi widget / st.rerun() penuh. Karena tidak ada interaksi, angka harga
    kelihatan 'freeze' walau cache-nya (ttl=10s) sebenarnya sudah kedaluwarsa.
    Sekarang dibungkus st.fragment(run_every=...) — sama seperti Live Simulator —
    supaya bagian ini reruns SENDIRI tiap beberapa detik tanpa reload halaman."""
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
    """Bungkus grafik + signal engine dalam fragment yang auto-refresh (opsional,
    default ON tiap 15-20 detik) supaya analisa & candle mengikuti harga terbaru
    tanpa user harus reload / klik apapun — sinkron dengan harga live di atas."""
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


def render_live_simulator_ui(exchange_name: str, symbol: str, timeframe: str, mtf_enabled: bool) -> None:
    st.markdown("### 🤖 Live Simulator / Live Trading Futures")

    mode_choice = st.radio(
        "Mode",
        ["Simulasi (Paper Trading)", "Live Trading (Uang Sungguhan)"],
        horizontal=True, key="sim_mode_choice"
    )
    mode = "LIVE" if mode_choice.startswith("Live") else "SIM"

    col1, col2, col3, col4 = st.columns(4, gap="small")
    with col1:
        initial_capital = st.number_input(
            "Modal Awal (USDT)" if mode == "LIVE" else "Initial Capital",
            value=10000.0, step=100.0 if mode == "LIVE" else 1000.0, min_value=1.0, key="sim_capital_input"
        )
    with col2:
        risk_per_trade = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0, 0.5, key="sim_risk_input") / 100
    with col3:
        refresh_sec = st.selectbox("Refresh Interval", [2, 3, 5, 10, 15], index=1, key="sim_refresh_sec",
                                    format_func=lambda s: f"{s}s")
    with col4:
        st.write("")
        st.write("")
        reset_btn = st.button("♻️ Reset Sesi", use_container_width=True)

    sim = get_sim_state(exchange_name, symbol, timeframe, initial_capital, risk_per_trade)

    if reset_btn:
        reset_sim_state(exchange_name, symbol, timeframe, initial_capital, risk_per_trade)
        st.session_state.pop(LIVE_CREDS_KEY, None)
        st.rerun()

    if sim["mode"] != mode:
        sim["mode"] = mode
        sim["running"] = False
        sim["armed"] = False

    if mode == "LIVE":
        _render_live_trading_setup(exchange_name, symbol, sim)
    else:
        st.info("🧪 Mode Simulasi — tidak ada order nyata yang dikirim ke exchange manapun.")

    c1, c2, c3 = st.columns([1, 1, 2], gap="small")
    with c1:
        start_disabled = (mode == "LIVE" and not sim.get("armed", False))
        if not sim["running"]:
            if st.button("▶️ Start", use_container_width=True, type="primary", disabled=start_disabled):
                sim["running"] = True
                sim["kill_switch_triggered"] = False
                st.rerun()
        else:
            if st.button("⏸️ Stop", use_container_width=True):
                sim["running"] = False
                st.rerun()
    with c2:
        if mode == "LIVE" and sim["position"] is not None:
            if st.button("🛑 Emergency Close", use_container_width=True):
                msg = emergency_close_live_position(exchange_name, symbol)
                st.toast(msg)
                st.rerun()
    with c3:
        if mode == "LIVE":
            status = "🔴 LIVE TRADING AKTIF" if sim["running"] else ("🟡 ARMED (belum jalan)" if sim["armed"] else "⚪ NOT ARMED")
        else:
            status = "🟢 SIMULASI JALAN" if sim["running"] else "⚪ STOPPED"
        st.markdown(f"**Status:** {status} · `{symbol}` · `{timeframe}` · `{exchange_name}`"
                    + (" · MTF ✅" if mtf_enabled else ""))

    if mode == "LIVE" and sim.get("kill_switch_triggered"):
        st.error(f"🛑 Kill switch aktif — drawdown harian sudah mencapai batas ({sim['daily_loss_limit_pct']}%). "
                 f"Trading live dihentikan otomatis. Tekan **Reset Sesi** untuk memulai ulang setelah evaluasi.")

    _render_live_simulator_fragment(exchange_name, symbol, timeframe, refresh_sec, mtf_enabled)


def _render_live_trading_setup(exchange_name: str, symbol: str, sim: Dict[str, Any]) -> None:
    st.error(
        "⚠️ **MODE LIVE TRADING — UANG SUNGGUHAN.** Bot akan mengirim order MARKET langsung ke akun "
        f"{exchange_name} kamu berdasarkan sinyal otomatis. Gunakan API key dengan pembatasan IP dan "
        "**TANPA izin withdraw**. Kerugian bisa terjadi karena bug, slippage, koneksi putus, atau kondisi pasar ekstrem."
    )

    creds = st.session_state.setdefault(LIVE_CREDS_KEY, {"connected": False, "client": None, "balance": None})

    with st.expander("🔐 Koneksi Exchange & Risk Limit", expanded=not creds.get("connected", False)):
        c1, c2 = st.columns(2, gap="small")
        with c1:
            api_key = st.text_input("API Key", type="password", key="live_api_key")
        with c2:
            api_secret = st.text_input("API Secret", type="password", key="live_api_secret")

        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            sim["leverage"] = int(st.number_input("Leverage", value=int(sim.get("leverage", 5)), min_value=1, max_value=125, step=1))
        with c2:
            sim["max_position_usdt"] = float(st.number_input("Max Position per Trade (USDT)",
                                                               value=float(sim.get("max_position_usdt", 100.0)), min_value=5.0, step=5.0))
        with c3:
            sim["daily_loss_limit_pct"] = float(st.number_input("Daily Loss Limit (%)",
                                                                  value=float(sim.get("daily_loss_limit_pct", 5.0)), min_value=0.5, max_value=50.0, step=0.5))

        if st.button("🔌 Test Connection & Cek Saldo"):
            client, err = connect_live_exchange(exchange_name, api_key, api_secret)
            if err:
                st.error(f"❌ Gagal konek: {err}")
                creds["connected"] = False
                creds["client"] = None
            else:
                balance, berr = fetch_usdt_balance(client)
                if berr:
                    st.error(f"❌ Konek berhasil tapi gagal ambil saldo: {berr}")
                    creds["connected"] = False
                else:
                    creds["connected"] = True
                    creds["client"] = client
                    creds["balance"] = balance
                    st.success(f"✅ Terkoneksi. Saldo USDT tersedia: ${format_number(balance)}")

        if creds.get("connected"):
            st.caption(f"Status koneksi: 🟢 Terhubung · Saldo terakhir: ${format_number(creds.get('balance'))}")

        st.markdown("---")
        confirm_text = st.text_input(
            f"Ketik **{CONFIRM_PHRASE}** untuk mengaktifkan (arm) eksekusi order nyata:",
            key="live_confirm_phrase"
        )
        arm_ready = creds.get("connected", False) and confirm_text.strip().upper() == CONFIRM_PHRASE

        cc1, cc2 = st.columns(2, gap="small")
        with cc1:
            if not sim.get("armed", False):
                if st.button("🔓 Arm Live Trading", disabled=not arm_ready, use_container_width=True):
                    sim["armed"] = True
                    sim["session_start_balance"] = creds.get("balance") or sim["capital"]
                    sim["capital"] = sim["session_start_balance"]
                    sim["kill_switch_triggered"] = False
                    st.rerun()
            else:
                if st.button("🔒 Disarm", use_container_width=True):
                    sim["armed"] = False
                    sim["running"] = False
                    st.rerun()
        with cc2:
            if not creds.get("connected"):
                st.caption("Test koneksi dulu sebelum bisa arm.")
            elif not arm_ready:
                st.caption("Ketik frasa konfirmasi persis sama untuk mengaktifkan tombol Arm.")


def _render_live_simulator_fragment(exchange_name: str, symbol: str, timeframe: str, refresh_sec: int,
                                     mtf_enabled: bool) -> None:
    if _fragment_decorator is None:
        _live_sim_body(exchange_name, symbol, timeframe, mtf_enabled)
        st.info("ℹ️ Update Streamlit ke versi terbaru untuk auto-refresh mulus tanpa reload halaman.")
        return

    @_fragment_decorator(run_every=refresh_sec)
    def _fragment_body():
        _live_sim_body(exchange_name, symbol, timeframe, mtf_enabled)

    _fragment_body()

# --------------------------------------------------------------------------
# COMPAT HELPER — cek dukungan parameter `key` di berbagai elemen Streamlit.
# Beberapa versi Streamlit (terutama yang lebih lama) belum mendukung
# parameter `key` di st.line_chart / st.area_chart / st.bar_chart / dsb.
# Daripada patch satu-satu tiap ketemu TypeError baru, dicek sekali di awal
# lalu dipakai di semua tempat yang butuh redraw paksa via key dinamis.
# --------------------------------------------------------------------------
import inspect as _inspect

def _supports_key_param(func: Any) -> bool:
    try:
        return "key" in _inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False

_LINE_CHART_SUPPORTS_KEY: bool = _supports_key_param(st.line_chart)


def _line_chart_compat(data: Any, *, key: Optional[str] = None, **kwargs: Any) -> None:
    """Wrapper aman untuk st.line_chart yang tetap jalan di versi Streamlit
    lama (belum ada parameter `key`) maupun baru (sudah ada `key`).

    FIX: sebelumnya st.line_chart(..., key=...) dipanggil langsung, yang
    menyebabkan `TypeError: VegaChartsMixin.line_chart() got an unexpected
    keyword argument 'key'` di versi Streamlit yang belum mendukung
    parameter tsb. Sekarang dicek dulu via _LINE_CHART_SUPPORTS_KEY (hasil
    inspect.signature, dihitung sekali saat modul di-import) — kalau versi
    yang terpasang mendukung, key diteruskan supaya chart tetap dipaksa
    redraw penuh saat berada di dalam st.fragment(run_every=...) (chart
    tidak "nyangkut" menampilkan data lama persis saat sebuah posisi baru
    ditutup). Kalau tidak didukung, key otomatis di-drop dan chart tetap
    tampil normal (hanya kehilangan jaminan force-redraw itu, bukan error)."""
    if key is not None and _LINE_CHART_SUPPORTS_KEY:
        st.line_chart(data, key=key, **kwargs)
    else:
        st.line_chart(data, **kwargs)


def _live_sim_body(exchange_name: str, symbol: str, timeframe: str, mtf_enabled: bool) -> None:
    sim = st.session_state.get(SIM_STATE_KEY)
    if sim is None:
        return

    status_msg = simulate_live_step(exchange_name, symbol, timeframe, mtf_enabled=mtf_enabled) if sim["running"] else None
    sim = st.session_state.get(SIM_STATE_KEY)

    if status_msg:
        st.toast(status_msg)

    is_live = sim["mode"] == "LIVE"
    unrealized_usdt = sim["position"]["unrealized_pnl_usdt"] if sim["position"] else 0.0
    mtm_equity = sim["capital"] + unrealized_usdt
    total_return = safe_pct_change(mtm_equity, sim["initial_capital"])
    # FIX: pakai .get("profit_pct") bukan t["profit_pct"] — kalau ada trade lama di
    # session_state yang formatnya beda (mis. dari versi sebelumnya) ini tidak error,
    # cuma dianggap bukan win, jadi Win Rate tetap kehitung dan tidak silently blank.
    trades_snapshot = list(sim["trades"])
    wins = sum(1 for t in trades_snapshot if (t.get("profit_pct") or 0) > 0)
    total_trades = len(trades_snapshot)
    win_rate = (wins / total_trades * 100) if total_trades else 0.0

    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    c1.metric("Equity (MTM)" if not is_live else "Balance Estimasi (MTM)", f"${format_number(mtm_equity)}", format_percentage(total_return))
    c2.metric("Total Trades", total_trades)
    c3.metric("Win Rate", f"{win_rate:.1f}%" if total_trades else "-")
    c4.metric("Ticks Processed", sim["tick_count"])
    last_upd = sim["last_update"].strftime("%H:%M:%S") if sim["last_update"] else "-"
    c5.metric("Last Update", last_upd)

    pos = sim["position"]
    if pos:
        st.markdown("---")
        st.markdown("#### 📌 Posisi Terbuka" + (" (LIVE)" if is_live else ""))
        pnl_color = "green" if pos["unrealized_pnl"] > 0 else "red" if pos["unrealized_pnl"] < 0 else "white"
        cols = st.columns(6, gap="small")
        cols[0].markdown(f"**Arah:** {'🟢' if pos['direction'] == 'LONG' else '🔴'} **{pos['direction']}**")
        cols[1].markdown(f"**Entry:** ${format_price(pos['entry_price'], symbol)}")
        cols[2].markdown(f"**Current:** ${format_price(pos['current_price'], symbol)}")
        cols[3].markdown(f"**SL:** ${format_price(pos['sl'], symbol)}")
        cols[4].markdown(f"**TP1/TP2:** ${format_price(pos['tp1'], symbol)} / ${format_price(pos['tp2'], symbol)}")
        cols[5].markdown(
            f"**PnL:** <span style='color:{pnl_color}'>{pos['unrealized_pnl']:+.2f}% "
            f"({pos.get('unrealized_pnl_usdt', 0):+.2f} USDT)</span>", unsafe_allow_html=True
        )
    elif sim["running"]:
        st.info("⏳ Flat — menunggu sinyal BUY/SELL untuk membuka posisi...")

    if sim["equity_curve"] and len(sim["equity_curve"]) > 1:
        st.markdown("#### Equity Curve (Live)")
        eq_df = pd.DataFrame(sim["equity_curve"]).set_index("time")
        # FIX UTAMA (TypeError: line_chart() got an unexpected keyword argument 'key'):
        # sebelumnya st.line_chart(..., key=...) dipanggil langsung dan meledak di
        # versi Streamlit yang belum mendukung parameter `key` pada elemen chart.
        # Sekarang lewat _line_chart_compat() yang otomatis mendeteksi dukungan
        # parameter tsb (lihat komentar di definisinya) — key tetap dipakai kalau
        # didukung (supaya chart tidak "nyangkut" data lama di dalam fragment
        # auto-refresh), dan otomatis di-skip kalau tidak didukung (tanpa error).
        _line_chart_compat(eq_df["equity"], key=f"equity_chart_{len(sim['equity_curve'])}")

    # FIX UTAMA (Win Rate & Riwayat Trade "tidak muncul" saat trade baru selesai):
    # sebelumnya label expander memuat total_trades langsung
    # (f"Riwayat Trade ({total_trades})"). Karena Streamlit memakai label sebagai
    # identitas widget saat tidak ada `key` eksplisit, begitu total_trades berubah
    # (trade baru saja close), Streamlit menganggap ini elemen BARU dan
    # mem-passing expanded=False dari awal lagi — di dalam fragment auto-refresh
    # ini membuat expander & tabel di dalamnya sempat tidak tampil/reset tepat di
    # tick yang sama saat posisi ditutup. Sekarang key dibuat stabil (tidak
    # bergantung pada total_trades) supaya identitas widget konsisten, dan
    # jumlah trade cukup ditampilkan lewat st.caption di dalamnya.
    try:
        trade_history_expander = st.expander("📜 Riwayat Trade", expanded=False, key="riwayat_trade_expander")
    except TypeError:
        # Streamlit versi lama belum punya parameter `key` di st.expander
        trade_history_expander = st.expander("📜 Riwayat Trade", expanded=False)

    with trade_history_expander:
        st.caption(f"Total trade selesai: **{total_trades}**")
        if trades_snapshot:
            trades_df = pd.DataFrame(trades_snapshot)
            keep_cols = ['entry_time', 'direction', 'entry_price', 'exit_price', 'profit_pct', 'pnl_usdt', 'exit_reason']
            keep_cols = [c for c in keep_cols if c in trades_df.columns]
            display_df = trades_df[keep_cols].copy()
            display_df['entry_time'] = pd.to_datetime(display_df['entry_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            display_df['direction'] = display_df['direction'].apply(lambda x: '🟢 LONG' if x == 'LONG' else '🔴 SHORT')
            display_df['entry_price'] = display_df['entry_price'].apply(lambda x: f"${format_price(x, symbol)}")
            display_df['exit_price'] = display_df['exit_price'].apply(lambda x: f"${format_price(x, symbol)}" if pd.notna(x) else "-")
            display_df['profit_pct'] = display_df['profit_pct'].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
            if 'pnl_usdt' in display_df.columns:
                display_df['pnl_usdt'] = display_df['pnl_usdt'].apply(lambda x: f"{x:+.2f}" if pd.notna(x) else "-")
            # key dinamis (jumlah trade) supaya tabel dipaksa redraw penuh begitu
            # ada trade baru, bukan memakai cache render sebelumnya.
            st.dataframe(display_df.iloc[::-1], use_container_width=True, height=280,
                         key=f"trades_table_{total_trades}")
        else:
            st.info("Belum ada trade yang selesai.")

    if is_live and sim.get("log"):
        with st.expander("📜 Log Eksekusi", expanded=False):
            for line in sim["log"]:
                st.text(line)

    if not sim["running"] and sim["tick_count"] == 0:
        hint = "Arm dulu di panel Koneksi Exchange, lalu tekan **Start**." if is_live else "Tekan **Start** untuk mulai memantau sinyal secara real-time."
        st.caption(hint)


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
            "tab Analisa, Live Simulator, dan Coin Scanner).")
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
/* ------------------------------------------------------------------ */
/* SCROLL SMOOTH DI HP: momentum-scroll iOS + smooth-scroll utk semua  */
/* container yang bisa discroll (halaman utama, sidebar, dataframe,    */
/* text area, dsb). GPU-accelerated supaya tidak patah-patah di mobile.*/
/* ------------------------------------------------------------------ */
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
/* --- Toggle sidebar (tombol Menu kustom, tampil jelas di mobile) --- */
.airise-menu-btn button {{
    background: linear-gradient(90deg, #2979ff, #00e5ff) !important;
    color: #08131c !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
}}
/* --- Metric cards: angka diperkecil & dirapikan dalam grid/kolom --- */
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
</style>
"""
    st.markdown(css, unsafe_allow_html=True)

def render_sidebar_toggle_button() -> None:
    """Tombol eksplisit untuk buka/tutup sidebar — memudahkan di HP karena
    panah collapse bawaan Streamlit kadang kecil/susah ditekan di layar sentuh.
    Status disimpan di session_state dan sidebar disembunyikan lewat CSS."""
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
        f'<p class="airise-tagline">{BOT_TAGLINE} · 7 Indikator + MTF nyata + Backtesting + Live Price + Coin Scanner</p>'
        f'</div></div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

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
        live_price_refresh = st.selectbox("Interval Harga Live", [3, 5, 10], index=1,
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
        st.caption("💡 Harga live, Grafik/Sinyal, dan Live Simulator sekarang auto-refresh sendiri "
                   "(masing-masing pakai st.fragment) — tidak perlu reload halaman penuh lagi.")

    symbol = st.session_state.selected_symbol
    exchange_name = st.session_state.exchange_name
    timeframe = st.session_state.timeframe

    init_telegram_if_enabled()

    # --- FIX: harga live sekarang dibungkus fragment auto-refresh sendiri ---
    render_live_price_fragment(exchange_name, symbol, refresh_sec=live_price_refresh)
    st.divider()

    st.markdown(f"### 📊 {symbol} · {exchange_name} · {timeframe}")

    tab_chart, tab_sim, tab_scanner = st.tabs(
        ["📊 Grafik & Analisa Sinyal", "🤖 Live Simulator", "📡 Coin Scanner"]
    )

    with tab_chart:
        render_analysis_fragment(exchange_name, symbol, timeframe, limit, mtf_enabled,
                                  chart_refresh_sec, auto_refresh_chart)

    with tab_sim:
        render_live_simulator_ui(exchange_name, symbol, timeframe, mtf_enabled)

    with tab_scanner:
        render_coin_scanner_ui(exchange_name, timeframe, mtf_enabled)

if __name__ == "__main__":
    main()