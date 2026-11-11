"""Compatibility entry point for the AIRISE Streamlit application.

The full application lives in ``airise_bot.py``. Keep this module as an alias
so ``app.py`` can configure and extend the same module object without duplicating
or shadowing the application implementation.
"""

import sys

import airise_bot as _app


def create_chart(df, symbol, signal=None):
    """Render the live chart with price action and key indicators on one canvas."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=1,
        cols=1,
        specs=[[{"secondary_y": True}]],
    )
    dates = df["date"]

    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
            increasing_fillcolor="#22c55e",
            decreasing_fillcolor="#ef4444",
            opacity=0.92,
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

    ema_colors = {
        "ema_9": ("EMA 9", "#f5c542"),
        "ema_21": ("EMA 21", "#60a5fa"),
        "ema_50": ("EMA 50", "#a78bfa"),
        "ema_200": ("EMA 200", "#fb923c"),
    }
    for column, (label, color) in ema_colors.items():
        if column in df.columns and not df[column].isna().all():
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=df[column],
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=1.5, dash="solid" if column != "ema_200" else "dash"),
                ),
                row=1,
                col=1,
                secondary_y=False,
            )

    if {"bb_upper", "bb_mid", "bb_lower"}.issubset(df.columns):
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["bb_upper"],
                mode="lines",
                name="BB Upper",
                line=dict(color="rgba(148,163,184,0.8)", width=1.0),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["bb_mid"],
                mode="lines",
                name="BB Mid",
                line=dict(color="rgba(148,163,184,0.45)", width=1.0, dash="dot"),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["bb_lower"],
                mode="lines",
                name="BB Lower",
                line=dict(color="rgba(148,163,184,0.8)", width=1.0),
                fill="tonexty",
                fillcolor="rgba(148,163,184,0.08)",
            ),
            row=1,
            col=1,
            secondary_y=False,
        )

    if signal is not None:
        if signal.direction != "HOLD":
            color = "#22c55e" if signal.direction == "BUY" else "#ef4444"
            fig.add_trace(
                go.Scatter(
                    x=[dates.iloc[-1]],
                    y=[signal.entry],
                    mode="markers+text",
                    name=f"Signal: {signal.direction}",
                    marker=dict(size=12, color=color, symbol="star"),
                    text=[signal.direction],
                    textposition="top center",
                    textfont=dict(size=11, color="white"),
                ),
                row=1,
                col=1,
                secondary_y=False,
            )
        for value, label, color in (
            (signal.sl, "SL", "#ef4444"),
            (signal.tp1, "TP1", "#22c55e"),
            (signal.tp2, "TP2", "#10b981"),
        ):
            if value is not None and np.isfinite(value):
                fig.add_hline(
                    y=value,
                    line_dash="dash",
                    line_color=color,
                    annotation_text=f"{label} {value:.4f}",
                    annotation_font=dict(size=9, color=color),
                )

    if "macd_hist" in df.columns:
        hist_colors = np.where(df["macd_hist"] >= 0, "#22c55e", "#ef4444")
        fig.add_trace(
            go.Bar(
                x=dates,
                y=df["macd_hist"],
                name="MACD Hist",
                marker_color=hist_colors,
                opacity=0.7,
                yaxis="y3",
            )
        )
    for column, label, color, width in (
        ("macd", "MACD", "#60a5fa", 1.5),
        ("macd_signal", "MACD Signal", "#f59e0b", 1.2),
    ):
        if column in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=df[column],
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=width),
                    yaxis="y3",
                )
            )

    for column, label, color, width in (
        ("rsi_14", "RSI 14", "#a78bfa", 1.6),
        ("stoch_k", "Stoch K", "#f59e0b", 1.2),
        ("stoch_d", "Stoch D", "#fbbf24", 1.2),
    ):
        if column in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=df[column],
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=width),
                    yaxis="y2",
                )
            )

    if "volume" in df.columns:
        volume_colors = np.where(df["close"] >= df["open"], "#22c55e", "#ef4444")
        fig.add_trace(
            go.Bar(
                x=dates,
                y=df["volume"],
                name="Volume",
                marker_color=volume_colors,
                opacity=0.22,
                yaxis="y4",
            )
        )
    if "volume_ma" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df["volume_ma"],
                mode="lines",
                name="Volume MA 20",
                line=dict(color="#f59e0b", width=1.0, dash="dot"),
                yaxis="y4",
            )
        )

    fig.add_hline(y=0, line_dash="dot", line_color="rgba(148,163,184,0.25)", yaxis="y3")
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y2",
        y0=70,
        y1=70,
        line=dict(color="rgba(239,68,68,0.75)", dash="dash", width=1),
    )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y2",
        y0=30,
        y1=30,
        line=dict(color="rgba(34,197,94,0.75)", dash="dash", width=1),
    )

    volume_max = float(df["volume"].max()) if "volume" in df.columns and len(df) else 0.0
    volume_max = max(volume_max, 1.0)

    fig.update_layout(
        title=dict(text=f"{symbol} — Price & Indicators", x=0.01),
        height=720,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.85)",
        font=dict(color="#e2e8f0"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.07,
            xanchor="left",
            x=0,
            font=dict(size=9),
        ),
        margin=dict(l=12, r=22, t=40, b=12),
        xaxis=dict(rangeslider=dict(visible=False), showgrid=False, zeroline=False),
        yaxis=dict(title="Price", showgrid=True, gridcolor="rgba(148,163,184,0.12)", zeroline=False),
        yaxis2=dict(
            title="RSI / Stoch",
            overlaying="y",
            side="right",
            anchor="free",
            position=0.96,
            range=[0, 100],
            showgrid=False,
            zeroline=False,
        ),
        yaxis3=dict(
            title="MACD",
            overlaying="y",
            side="right",
            anchor="free",
            position=0.91,
            showgrid=False,
            zeroline=False,
        ),
        yaxis4=dict(
            overlaying="y",
            side="left",
            anchor="free",
            position=0.01,
            range=[0, volume_max * 3],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
        ),
        barmode="overlay",
    )

    return fig


# Alias the module object so app.py and support_resistance.py configure the same
# implementation used by its functions and Streamlit callbacks.
_app.create_chart = create_chart
sys.modules[__name__] = _app
