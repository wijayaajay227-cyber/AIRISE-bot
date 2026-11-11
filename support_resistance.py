"""Support/resistance zones derived from recent pivot highs and lows.

These levels are descriptive chart context, not guaranteed reversal points or
trading advice. The detector groups nearby swing points into ATR-scaled zones
and reports the most relevant zones around the latest price.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


PIVOT_WINDOW = 3
LOOKBACK = 240
MAX_ZONES_PER_SIDE = 3


def find_support_resistance(df: pd.DataFrame, max_zones: int = MAX_ZONES_PER_SIDE) -> Dict[str, Any]:
    """Return nearby support/resistance zones and pivot-touch counts.

    A pivot is only accepted after both sides of its local window are present.
    This avoids treating the still-forming edge of the chart as a confirmed
    swing point. Adjacent pivots are clustered using ATR-scaled tolerance.
    """
    empty = {"price": None, "supports": [], "resistances": [], "atr": None}
    required = {"high", "low", "close"}
    if df is None or df.empty or not required.issubset(df.columns) or len(df) < 2 * PIVOT_WINDOW + 1:
        return empty

    data = df.tail(LOOKBACK).copy()
    highs = pd.to_numeric(data["high"], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(data["low"], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(data["close"], errors="coerce").to_numpy(dtype=float)
    valid_close = closes[np.isfinite(closes)]
    if not len(valid_close):
        return empty
    current = float(valid_close[-1])

    if "atr_14" in data.columns:
        atr_values = pd.to_numeric(data["atr_14"], errors="coerce").to_numpy(dtype=float)
        atr_values = atr_values[np.isfinite(atr_values) & (atr_values > 0)]
        atr = float(atr_values[-1]) if len(atr_values) else None
    else:
        atr = None
    if not atr:
        tr = np.maximum(highs - lows,
                        np.maximum(np.abs(highs - np.roll(closes, 1)), np.abs(lows - np.roll(closes, 1))))
        tr[0] = highs[0] - lows[0]
        valid_tr = tr[np.isfinite(tr) & (tr > 0)]
        atr = float(np.mean(valid_tr[-14:])) if len(valid_tr) else current * 0.005

    tolerance = max(atr * 0.35, current * 0.0005)
    pivots: List[tuple[float, str, int]] = []
    n = len(data)
    for i in range(PIVOT_WINDOW, n - PIVOT_WINDOW):
        local_highs = highs[i - PIVOT_WINDOW:i + PIVOT_WINDOW + 1]
        local_lows = lows[i - PIVOT_WINDOW:i + PIVOT_WINDOW + 1]
        if np.isfinite(highs[i]) and highs[i] == np.nanmax(local_highs) and np.count_nonzero(local_highs == highs[i]) == 1:
            pivots.append((float(highs[i]), "resistance", i))
        if np.isfinite(lows[i]) and lows[i] == np.nanmin(local_lows) and np.count_nonzero(local_lows == lows[i]) == 1:
            pivots.append((float(lows[i]), "support", i))

    def cluster(kind: str) -> List[Dict[str, Any]]:
        points = sorted((p, idx) for p, side, idx in pivots if side == kind)
        groups: List[List[tuple[float, int]]] = []
        for point in points:
            if not groups or abs(point[0] - float(np.mean([x[0] for x in groups[-1]]))) > tolerance:
                groups.append([point])
            else:
                groups[-1].append(point)

        zones = []
        for group in groups:
            level = float(np.mean([p for p, _ in group]))
            if kind == "support" and level >= current:
                continue
            if kind == "resistance" and level <= current:
                continue
            # Prefer repeated pivots and levels nearer to current price.
            distance_atr = abs(current - level) / max(atr, 1e-12)
            strength = len(group)
            zones.append({
                "level": level,
                "touches": strength,
                "distance_atr": float(distance_atr),
                "score": strength / (1.0 + distance_atr),
            })
        zones.sort(key=lambda z: (-z["score"], z["distance_atr"]))
        return zones[:max_zones]

    return {
        "price": current,
        "supports": cluster("support"),
        "resistances": cluster("resistance"),
        "atr": atr,
    }


def install(real_module: Any) -> None:
    """Add S/R context and chart overlays to the existing AIRISE app."""
    if getattr(real_module, "_sr_installed", False):
        return

    original_chart = real_module.create_chart
    original_body = real_module._render_analysis_body

    def create_chart_with_zones(df: pd.DataFrame, symbol: str, signal: Optional[Any] = None):
        fig = original_chart(df, symbol, signal)
        zones = find_support_resistance(df)
        for index, zone in enumerate(zones["supports"]):
            fig.add_hline(
                y=zone["level"], row=1, col=1, line_dash="dot", line_color="#26a69a",
                annotation_text=f"Support {index + 1} · {zone['touches']}x",
                annotation_position="bottom right",
            )
        for index, zone in enumerate(zones["resistances"]):
            fig.add_hline(
                y=zone["level"], row=1, col=1, line_dash="dot", line_color="#ef5350",
                annotation_text=f"Resistance {index + 1} · {zone['touches']}x",
                annotation_position="top right",
            )
        return fig

    def render_analysis_with_zones(exchange_name: str, symbol: str, timeframe: str,
                                   limit: int, mtf_enabled: bool) -> None:
        original_body(exchange_name, symbol, timeframe, limit, mtf_enabled)
        try:
            candles = real_module.get_ohlcv(exchange_name, symbol, timeframe, limit)
            if candles.empty:
                return
            if "atr_14" not in candles.columns:
                candles = real_module.add_indicators(candles)
            zones = find_support_resistance(candles)
            if zones["price"] is None:
                return

            st = real_module.st
            st.markdown("#### 🧱 Support & Resistance (pivot zones)")
            st.caption(
                "Zona dihitung dari swing high/low terkonfirmasi pada candle terbaru dan dikelompokkan "
                "dengan toleransi berbasis ATR. Jumlah sentuhan adalah hitungan pivot, bukan jaminan "
                "harga akan berbalik. Gunakan sebagai konteks bersama tren dan volume."
            )
            support_col, resistance_col = st.columns(2)
            with support_col:
                st.markdown("**🟢 Support terdekat**")
                if zones["supports"]:
                    for zone in sorted(zones["supports"], key=lambda z: z["distance_atr"]):
                        st.write(
                            f"${real_module.format_price(zone['level'], symbol)} · "
                            f"{zone['touches']} pivot · {zone['distance_atr']:.2f} ATR"
                        )
                else:
                    st.write("Belum ada pivot support terkonfirmasi di bawah harga.")
            with resistance_col:
                st.markdown("**🔴 Resistance terdekat**")
                if zones["resistances"]:
                    for zone in sorted(zones["resistances"], key=lambda z: z["distance_atr"]):
                        st.write(
                            f"${real_module.format_price(zone['level'], symbol)} · "
                            f"{zone['touches']} pivot · {zone['distance_atr']:.2f} ATR"
                        )
                else:
                    st.write("Belum ada pivot resistance terkonfirmasi di atas harga.")
        except Exception as exc:
            real_module.st.caption(f"Support/resistance tidak dapat dihitung saat ini: {exc}")

    real_module.create_chart = create_chart_with_zones
    real_module._render_analysis_body = render_analysis_with_zones
    real_module._sr_installed = True
