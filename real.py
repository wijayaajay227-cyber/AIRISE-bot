"""Compatibility entry point for the AIRISE Streamlit application.

The full application lives in ``airise_bot.py``. Keep this module as an alias
so ``app.py`` can configure and extend the same module object without duplicating
or shadowing the application implementation.
"""

import sys

import airise_bot as _app


def create_chart(df, symbol, signal=None):
    """Render price and the existing indicators together in one live chart."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])
    dates = df["date"]

    fig.add_trace(
        go.Candlestick(
            x=dates, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="Price", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        ), row=1, col=1, secondary_y=False,
    )

    ema_colors = {
        "ema_9": ("EMA 9", "#f5c542"),
        "ema_21": ("EMA 21", "#42a5f5"),
        "ema_50": ("EMA 50", "#ab47bc"),
        "ema_200": ("EMA 200", "#ff6d00"),
    }
    for column, (label, color) in ema_colors.items():
        if column in df.columns and not df[column].isna().all():
            fig.add_trace(
                go.Scatter(x=dates, y=df[column], mode="lines", name=label,
                           line=dict(color=color, width=1.4)),
                row=1, col=1, secondary_y=False,
            )

    if {"bb_upper", "bb_mid", "bb_lower"}.issubset(df.columns):
        fig.add_trace(go.Scatter(x=dates, y=df["bb_upper"], name="BB Upper", mode="lines",
                                 line=dict(color="rgba(160,170,180,0.65)", width=1)), row=1, col=1,
                      secondary_y=False)
        fig.add_trace(go.Scatter(x=dates, y=df["bb_mid"], name="BB Mid", mode="lines",
                                 line=dict(color="rgba(160,170,180,0.45)", width=1, dash="dot")),
                      row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=dates, y=df["bb_lower"], name="BB Lower", mode="lines",
                                 line=dict(color="rgba(160,170,180,0.65)", width=1),
                                 fill="tonexty", fillcolor="rgba(160,170,180,0.07)"),
                      row=1, col=1, secondary_y=False)

    if signal is not None:
        if signal.direction != "HOLD":
            color = "#26a69a" if signal.direction == "BUY" else "#ef5350"
            fig.add_trace(go.Scatter(
                x=[dates.iloc[-1]], y=[signal.entry], mode="markers+text",
                name=f"Signal: {signal.direction}", marker=dict(size=14, color=color, symbol="star"),
                text=[signal.direction], textposition="top center",
                textfont=dict(size=11, color="white"),
            ), row=1, col=1, secondary_y=False)
        for value, label, color in (
            (signal.sl, "SL", "#ef5350"),
            (signal.tp1, "TP1", "#26a69a"),
            (signal.tp2, "TP2", "#00c853"),
        ):
            if value and np.isfinite(value):
                fig.add_hline(y=value, line_dash="dash", line_color=color,
                              annotation_text=f"{label} {value:.4f}", row=1, col=1)

    # MACD has its own overlaid scale so it does not distort the price axis.
    if "macd_hist" in df.columns:
        hist_colors = np.where(df["macd_hist"] >= 0, "#26a69a", "#ef5350")
        fig.add_trace(go.Bar(x=dates, y=df["macd_hist"], name="MACD Hist",
                             marker_color=hist_colors, opacity=0.55, yaxis="y3"))
    for column, label, color, width in (
        ("macd", "MACD", "#2962ff", 1.4),
        ("macd_signal", "MACD Signal", "#ff6d00", 1.2),
    ):
        if column in df.columns:
            fig.add_trace(go.Scatter(x=dates, y=df[column], mode="lines", name=label,
                                     line=dict(color=color, width=width), yaxis="y3"))

    # RSI and Stochastic share their natural 0-100 scale.
    for column, label, color, width in (
        ("rsi_14", "RSI 14", "#7e57c2", 1.6),
        ("stoch_k", "Stoch K", "#ff6f00", 1.2),
        ("stoch_d", "Stoch D", "#ffab00", 1.2),
    ):
        if column in df.columns:
            fig.add_trace(go.Scatter(x=dates, y=df[column], mode="lines", name=label,
                                     line=dict(color=color, width=width), yaxis="y2"))

    # Put volume in the lower portion of the same plotting area using its own scale.
    if "volume" in df.columns:
        volume_colors = np.where(df["close"] >= df["open"], "#26a69a", "#ef5350")
        fig.add_trace(go.Bar(x=dates, y=df["volume"], name="Volume",
                             marker_color=volume_colors, opacity=0.20, yaxis="y4"))
    if "volume_ma" in df.columns:
        fig.add_trace(go.Scatter(x=dates, y=df["volume_ma"], mode="lines", name="Volume MA 20",
                                 line=dict(color="#ffb74d", width=1, dash="dot"), yaxis="y4"))

    fig.add_hline(y=0, line_dash="dot", line_color="rgba(180,190,200,0.3)", row=1, col=1,
                  secondary_y=True)
    fig.add_shape(type="line", xref="paper", x0=0, x1=1, yref="y2", y0=70, y1=70,
                  line=dict(color="rgba(239,83,80,0.65)", dash="dash", width=1))
    fig.add_shape(type="line", xref="paper", x0=0, x1=1, yref="y2", y0=30, y1=30,
                  line=dict(color="rgba(38,166,154,0.65)", dash="dash", width=1))

    volume_max = float(df["volume"].max()) if "volume" in df.columns and len(df) else 0.0
    volume_max = max(volume_max, 1.0)
    fig.update_layout(
        title=dict(text=f"{symbol} — Price & Indicators", x=0.01),
        height=720, hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,22,30,0.72)",
        font=dict(color="#d8e3ee"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=9)),
        margin=dict(l=12, r=80, t=55, b=12),
        xaxis=dict(rangeslider=dict(visible=False), showgrid=False, domain=[0.08, 0.88]),
        yaxis=dict(title="Price", showgrid=True, gridcolor="rgba(150,160,170,0.12)"),
        yaxis2=dict(title="RSI / Stoch", overlaying="y", side="right", anchor="free",
                    position=0.89, range=[0, 100], showgrid=False, zeroline=False),
        yaxis3=dict(title="MACD", overlaying="y", side="right", anchor="free",
                    position=0.95, showgrid=False, zeroline=False, showticklabels=False),
        yaxis4=dict(overlaying="y", side="left", anchor="free", position=0.08,
                    range=[0, volume_max * 5], showgrid=False, zeroline=False,
                    showticklabels=False),
        barmode="overlay",
    )
    return fig


# Alias the module object so app.py and support_resistance.py configure the same
# implementation used by its functions and Streamlit callbacks.
_app.create_chart = create_chart
sys.modules[__name__] = _app
