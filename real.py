def create_chart(df: pd.DataFrame, symbol: str, signal: Optional[Signal] = None) -> go.Figure:
    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"secondary_y": True}]],
        subplot_titles=(f"{symbol} — Price + Indicator Live",)
    )

    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="Price", increasing_line_color="#26a69a", decreasing_line_color="#ef5350"
    ), row=1, col=1, secondary_y=False)

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
                line=dict(width=1.4, color=color, dash="solid" if col != "ema_200" else "dash")
            ), row=1, col=1, secondary_y=False)

    if all(c in df.columns for c in ["bb_upper", "bb_lower"]):
        fig.add_trace(go.Scatter(x=df["date"], y=df["bb_upper"], mode="lines", name="BB Upper",
                                line=dict(width=1, color="rgba(150,150,150,0.6)")), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df["date"], y=df["bb_lower"], mode="lines", name="BB Lower",
                                line=dict(width=1, color="rgba(150,150,150,0.6)"),
                                fill="tonexty", fillcolor="rgba(150,150,150,0.08)"), row=1, col=1, secondary_y=False)

    if signal and signal.direction != "HOLD":
        signal_color = "green" if signal.direction == "BUY" else "red"
        fig.add_trace(go.Scatter(
            x=[df["date"].iloc[-1]], y=[signal.entry],
            mode="markers+text", name=f"Signal: {signal.direction}",
            marker=dict(size=15, color=signal_color, symbol="star"),
            text=[signal.direction], textposition="top center", textfont=dict(size=12, color="white")
        ), row=1, col=1, secondary_y=False)
        fig.add_hline(y=signal.sl, line_dash="dash", line_color="red", annotation_text=f"SL {signal.sl:.2f}")
        fig.add_hline(y=signal.tp1, line_dash="dash", line_color="green", annotation_text=f"TP1 {signal.tp1:.2f}")
        fig.add_hline(y=signal.tp2, line_dash="dash", line_color="#00c853", annotation_text=f"TP2 {signal.tp2:.2f}")

    if "macd_hist" in df.columns:
        colors = np.where(df["macd_hist"] >= 0, "#26a69a", "#ef5350")
        fig.add_trace(go.Bar(x=df["date"], y=df["macd_hist"], name="MACD Hist", marker_color=colors,
                            opacity=0.7), row=1, col=1, secondary_y=True)
    if "macd" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["macd"], mode="lines", name="MACD",
                                line=dict(width=1.4, color="#2962ff")), row=1, col=1, secondary_y=True)
    if "macd_signal" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["macd_signal"], mode="lines", name="Signal MACD",
                                line=dict(width=1.2, color="#ff6d00")), row=1, col=1, secondary_y=True)
    if "rsi_14" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["rsi_14"], mode="lines", name="RSI 14",
                                line=dict(width=1.5, color="#7e57c2")), row=1, col=1, secondary_y=True)
    if "stoch_k" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["stoch_k"], mode="lines", name="Stoch K",
                                line=dict(width=1.2, color="#ff6f00")), row=1, col=1, secondary_y=True)
    if "stoch_d" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["stoch_d"], mode="lines", name="Stoch D",
                                line=dict(width=1.2, color="#ffab00")), row=1, col=1, secondary_y=True)
    if "volume" in df.columns and "close" in df.columns:
        vol_colors = np.where(df["close"] > df["open"], "#26a69a", "#ef5350")
        fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="Volume", marker_color=vol_colors,
                            opacity=0.35), row=1, col=1, secondary_y=True)
    if "volume_ma" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["volume_ma"], mode="lines", name="Vol MA 20",
                                line=dict(width=1.2, color="#ff6d00", dash="dash")), row=1, col=1, secondary_y=True)

    fig.add_hline(y=0, line_dash="solid", line_color="rgba(128,128,128,0.3)")
    fig.add_hline(y=70, line_dash="dash", line_color="red")
    fig.add_hline(y=30, line_dash="dash", line_color="green")

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,22,30,0.55)",
        font=dict(color="#d8e3ee"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=8)),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(rangeslider=dict(visible=False)),
        yaxis=dict(title="Price / EMA / Bollinger"),
        yaxis2=dict(title="MACD / RSI / Stoch / Volume", overlaying="y", side="right")
    )

    return fig
