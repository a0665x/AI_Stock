from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .analytics import add_indicators
from .smc_adapter import build_smc_context
from .trade_vision import detect_market_structure

_PATTERN_COLUMNS = ["date", "pattern", "price", "direction", "strength"]
_UKF_COLUMNS = ["date", "raw_momentum", "ukf_momentum", "ukf_velocity", "noise_band_low", "noise_band_high", "state_label"]
_FVG_COLUMNS = ["zone_id", "date", "end_date", "zone_type", "status", "y0", "y1", "direction", "strength", "label"]
_SFP_COLUMNS = ["date", "price", "event_type", "reference_price", "direction", "strength", "description"]


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _empty_patterns() -> pd.DataFrame:
    return pd.DataFrame(columns=_PATTERN_COLUMNS)


def detect_swing_structure_signals(one: pd.DataFrame, swing_window: int = 3, min_break_pct: float = 0.003) -> dict[str, pd.DataFrame]:
    """Wrapper around the shared Trade Vision market-structure engine.

    The swing-order page uses the same swing high/low, BOS and ChoCH semantics as
    the professional Trade Vision tab so a next-day order can be checked against
    the broader structure without duplicating logic.
    """
    return detect_market_structure(one, swing_window=swing_window, min_break_pct=min_break_pct)


def detect_fvg_ifvg_zones(one: pd.DataFrame, min_gap_pct: float = 0.002) -> pd.DataFrame:
    """Detect simple Fair Value Gap (FVG) zones and invalidated inverse FVGs.

    Bullish FVG: current low is above the high from two bars ago. Bearish FVG:
    current high is below the low from two bars ago. A later close through the
    far side marks the zone as IFVG, meaning the original imbalance failed and
    may role-reverse into resistance/support.
    """
    required = {"date", "high", "low", "close"}
    if one.empty or not required.issubset(one.columns):
        return pd.DataFrame(columns=_FVG_COLUMNS)
    data = one.sort_values("date").reset_index(drop=True).copy()
    rows: list[dict[str, Any]] = []
    for idx in range(2, len(data)):
        prev2 = data.iloc[idx - 2]
        bar = data.iloc[idx]
        prev_high = _as_float(prev2.get("high"))
        prev_low = _as_float(prev2.get("low"))
        high = _as_float(bar.get("high"))
        low = _as_float(bar.get("low"))
        if not all(np.isfinite(v) for v in [prev_high, prev_low, high, low]):
            continue
        date = bar["date"]
        if low > prev_high * (1 + min_gap_pct):
            gap = low - prev_high
            rows.append(
                {
                    "zone_id": f"bull_fvg_{idx}",
                    "date": date,
                    "end_date": data["date"].iloc[-1],
                    "zone_type": "FVG_BULLISH",
                    "status": "FVG",
                    "y0": prev_high,
                    "y1": low,
                    "direction": "bullish",
                    "strength": gap / max(abs(prev_high), 1e-9),
                    "label": "FVG Bullish",
                }
            )
        if high < prev_low * (1 - min_gap_pct):
            gap = prev_low - high
            rows.append(
                {
                    "zone_id": f"bear_fvg_{idx}",
                    "date": date,
                    "end_date": data["date"].iloc[-1],
                    "zone_type": "FVG_BEARISH",
                    "status": "FVG",
                    "y0": high,
                    "y1": prev_low,
                    "direction": "bearish",
                    "strength": gap / max(abs(prev_low), 1e-9),
                    "label": "FVG Bearish",
                }
            )
    if not rows:
        return pd.DataFrame(columns=_FVG_COLUMNS)
    zones = pd.DataFrame(rows, columns=_FVG_COLUMNS)
    closes = pd.to_numeric(data["close"], errors="coerce")
    for zidx, zone in zones.iterrows():
        start_pos = int(data.index[data["date"] == zone["date"]][0]) if (data["date"] == zone["date"]).any() else 0
        future = closes.iloc[start_pos + 1 :]
        y0 = float(zone["y0"])
        y1 = float(zone["y1"])
        if zone["direction"] == "bullish" and (future < y0).any():
            zones.at[zidx, "status"] = "IFVG"
            zones.at[zidx, "label"] = "IFVG Bearish Role Flip"
        elif zone["direction"] == "bearish" and (future > y1).any():
            zones.at[zidx, "status"] = "IFVG"
            zones.at[zidx, "label"] = "IFVG Bullish Role Flip"
    return zones.sort_values("date").reset_index(drop=True)


def detect_sfp_events(one: pd.DataFrame, swing_window: int = 3, tolerance_pct: float = 0.001) -> pd.DataFrame:
    """Detect Swing Failure Patterns: sweep a swing level but close back inside."""
    required = {"date", "high", "low", "close"}
    if one.empty or not required.issubset(one.columns):
        return pd.DataFrame(columns=_SFP_COLUMNS)
    data = one.sort_values("date").reset_index(drop=True).copy()
    structure = detect_swing_structure_signals(data, swing_window=swing_window, min_break_pct=max(tolerance_pct, 0.0001))
    swings = structure.get("swings", pd.DataFrame())
    if swings is None or swings.empty:
        return pd.DataFrame(columns=_SFP_COLUMNS)
    rows: list[dict[str, Any]] = []
    prior_highs: list[dict[str, Any]] = []
    prior_lows: list[dict[str, Any]] = []
    swing_idx = 0
    swings_sorted = swings.sort_values("date").reset_index(drop=True)
    for _, bar in data.iterrows():
        bar_date = bar["date"]
        while swing_idx < len(swings_sorted) and swings_sorted.at[swing_idx, "date"] < bar_date:
            item = swings_sorted.iloc[swing_idx].to_dict()
            if item["type"] == "swing_high":
                prior_highs.append(item)
            elif item["type"] == "swing_low":
                prior_lows.append(item)
            swing_idx += 1
        high = _as_float(bar.get("high"))
        low = _as_float(bar.get("low"))
        close = _as_float(bar.get("close"))
        if prior_highs:
            ref = float(prior_highs[-1]["price"])
            if high > ref * (1 + tolerance_pct) and close < ref:
                rows.append({"date": bar_date, "price": high, "event_type": "SFP_BEARISH", "reference_price": ref, "direction": "bearish", "strength": (high - ref) / max(abs(ref), 1e-9), "description": f"Swept swing high {ref:.2f} but closed below it."})
        if prior_lows:
            ref = float(prior_lows[-1]["price"])
            if low < ref * (1 - tolerance_pct) and close > ref:
                rows.append({"date": bar_date, "price": low, "event_type": "SFP_BULLISH", "reference_price": ref, "direction": "bullish", "strength": (ref - low) / max(abs(ref), 1e-9), "description": f"Swept swing low {ref:.2f} but closed above it."})
    if not rows:
        return pd.DataFrame(columns=_SFP_COLUMNS)
    return pd.DataFrame(rows, columns=_SFP_COLUMNS).sort_values("date").reset_index(drop=True)


def detect_candlestick_patterns(one: pd.DataFrame) -> pd.DataFrame:
    """Detect lightweight candle patterns useful for swing-order context.

    The goal is not a full TA-Lib clone; it provides stable labels for doji,
    engulfing, hammer, shooting-star and strong-body candles so the next-day
    order table has visual evidence next to suggested prices.
    """
    required = {"date", "open", "high", "low", "close"}
    if one.empty or not required.issubset(one.columns):
        return _empty_patterns()
    data = one.sort_values("date").reset_index(drop=True).copy()
    rows: list[dict[str, Any]] = []
    prev_open = prev_close = np.nan
    for _, row in data.iterrows():
        open_ = _as_float(row["open"])
        high = _as_float(row["high"])
        low = _as_float(row["low"])
        close = _as_float(row["close"])
        if not all(np.isfinite(v) for v in [open_, high, low, close]) or high <= low:
            prev_open, prev_close = open_, close
            continue
        body = abs(close - open_)
        span = high - low
        upper = high - max(open_, close)
        lower = min(open_, close) - low
        body_ratio = body / max(span, 1e-9)
        price = close
        date = row["date"]

        def add(pattern: str, direction: str, strength: float, marker_price: float = price) -> None:
            rows.append({"date": date, "pattern": pattern, "price": float(marker_price), "direction": direction, "strength": float(max(0.0, min(strength, 1.0)))})

        if body_ratio <= 0.08:
            add("DOJI", "neutral", 1 - body_ratio / 0.08)
        if lower >= body * 2.2 and upper <= max(body, span * 0.15) and close >= open_:
            add("HAMMER", "bullish", min(lower / max(span, 1e-9), 1.0), low)
        if upper >= body * 2.2 and lower <= max(body, span * 0.15) and close <= open_:
            add("SHOOTING_STAR", "bearish", min(upper / max(span, 1e-9), 1.0), high)
        if np.isfinite(prev_open) and np.isfinite(prev_close):
            prev_bear = prev_close < prev_open
            prev_bull = prev_close > prev_open
            curr_bull = close > open_
            curr_bear = close < open_
            if prev_bear and curr_bull and open_ <= prev_close and close >= prev_open:
                add("BULLISH_ENGULFING", "bullish", body_ratio)
            if prev_bull and curr_bear and open_ >= prev_close and close <= prev_open:
                add("BEARISH_ENGULFING", "bearish", body_ratio)
        if body_ratio >= 0.65:
            add("STRONG_BULL_BODY" if close > open_ else "STRONG_BEAR_BODY", "bullish" if close > open_ else "bearish", body_ratio)
        prev_open, prev_close = open_, close
    if not rows:
        return _empty_patterns()
    return pd.DataFrame(rows, columns=_PATTERN_COLUMNS).sort_values("date").reset_index(drop=True)


def compute_ukf_momentum_state(one: pd.DataFrame) -> pd.DataFrame:
    """Compute a lightweight UKF-style denoised momentum state.

    This intentionally avoids heavy dependencies. It combines RSI, MACD hist,
    Bollinger position, volume ratio and short returns into a bounded raw
    momentum score, then applies a scalar unscented-Kalman-inspired predict /
    update loop to smooth noisy day-to-day changes. It is a research indicator,
    not a trained neural forecast model.
    """
    if one.empty or not {"date", "open", "high", "low", "close", "volume"}.issubset(one.columns):
        return pd.DataFrame(columns=_UKF_COLUMNS)
    data = add_indicators(one.sort_values("date").copy())
    rsi = (pd.to_numeric(data.get("rsi_14"), errors="coerce").fillna(50) - 50) / 50
    macd = pd.to_numeric(data.get("macd_hist"), errors="coerce").fillna(0)
    macd_scaled = macd / (pd.to_numeric(data["close"], errors="coerce").replace(0, np.nan).abs().fillna(1) * 0.01)
    bb = (pd.to_numeric(data.get("bb_position_20"), errors="coerce").fillna(0.5) - 0.5) * 2
    vol = (pd.to_numeric(data.get("volume_ratio_20d"), errors="coerce").fillna(1) - 1).clip(-2, 2) / 2
    ret = pd.to_numeric(data.get("return_5d"), errors="coerce").fillna(0) * 12
    raw = np.tanh(0.34 * rsi + 0.24 * macd_scaled + 0.18 * bb + 0.12 * vol + 0.12 * ret) * 100

    x = float(raw.iloc[0]) if len(raw) else 0.0
    velocity = 0.0
    p = 35.0
    q = 2.2
    r = 18.0
    smoothed: list[float] = []
    velocities: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    prev_x = x
    for z in raw.to_numpy(dtype=float):
        if not np.isfinite(z):
            z = prev_x
        # Non-linear prediction: momentum tends to mean-revert near extremes.
        x_pred = float(np.tanh((x + velocity) / 100.0) * 100.0)
        p_pred = p + q + abs(velocity) * 0.08
        k = p_pred / (p_pred + r)
        x_new = x_pred + k * (z - x_pred)
        velocity = 0.65 * velocity + 0.35 * (x_new - prev_x)
        p = (1 - k) * p_pred
        band = 1.96 * np.sqrt(max(p, 1e-9))
        smoothed.append(float(np.clip(x_new, -100, 100)))
        velocities.append(float(velocity))
        lows.append(float(np.clip(x_new - band, -100, 100)))
        highs.append(float(np.clip(x_new + band, -100, 100)))
        prev_x = x_new
        x = x_new
    out = pd.DataFrame(
        {
            "date": data["date"].to_numpy(),
            "raw_momentum": raw.to_numpy(dtype=float),
            "ukf_momentum": smoothed,
            "ukf_velocity": velocities,
            "noise_band_low": lows,
            "noise_band_high": highs,
        }
    )
    out["state_label"] = np.select(
        [out["ukf_momentum"] >= 20, out["ukf_momentum"] <= -20],
        ["BULLISH_MOMENTUM", "BEARISH_MOMENTUM"],
        default="NEUTRAL_MOMENTUM",
    )
    return out[_UKF_COLUMNS]


def _add_hline(fig: go.Figure, y: float, label: str, color: str, row: int = 1, dash: str = "dash") -> None:
    if np.isfinite(y):
        fig.add_hline(y=y, line_color=color, line_dash=dash, line_width=1.2, annotation_text=label, annotation_position="right", row=row, col=1)


def _add_named_level_trace(fig: go.Figure, dates: pd.Series, y: float, label: str, color: str, row: int = 1, dash: str = "dash") -> None:
    if np.isfinite(y) and len(dates) > 0:
        fig.add_trace(
            go.Scatter(
                x=[dates.iloc[0], dates.iloc[-1]],
                y=[y, y],
                mode="lines",
                name=label,
                line={"color": color, "dash": dash, "width": 1.2},
                hovertemplate=f"{label}=%{{y:.2f}}<extra></extra>",
            ),
            row=row,
            col=1,
        )


def _add_signal_rect(fig: go.Figure, *, x0: Any, x1: Any, y0: float, y1: float, name: str, fillcolor: str) -> None:
    if not all(np.isfinite(v) for v in [y0, y1]):
        return
    fig.add_shape(
        type="rect",
        x0=x0,
        x1=x1,
        y0=min(y0, y1),
        y1=max(y0, y1),
        xref="x",
        yref="y",
        fillcolor=fillcolor,
        line={"width": 0},
        layer="below",
        name=name,
    )


def summarize_swing_order_technical_context(one: pd.DataFrame, order_row: pd.Series | dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize the latest technical state shown by the swing-order chart."""
    if one.empty or not {"date", "open", "high", "low", "close", "volume"}.issubset(one.columns):
        return {"ticker": str(pd.Series(order_row if order_row is not None else {}).get("ticker", "")), "technical_readiness": "MIXED"}
    data = add_indicators(one.sort_values("date").copy())
    ukf = compute_ukf_momentum_state(data)
    latest = data.iloc[-1]
    latest_ukf = ukf.iloc[-1] if not ukf.empty else pd.Series(dtype=object)
    rsi = _as_float(latest.get("rsi_14"), 50.0)
    macd_hist = _as_float(latest.get("macd_hist"), 0.0)
    bb_position = _as_float(latest.get("bb_position_20"), 0.5)
    volume_ratio = _as_float(latest.get("volume_ratio_20d"), 1.0)
    ukf_momentum = _as_float(latest_ukf.get("ukf_momentum"), 0.0)
    bullish_votes = int(rsi >= 52) + int(macd_hist > 0) + int(bb_position >= 0.45) + int(ukf_momentum >= 20)
    bearish_votes = int(rsi <= 45) + int(macd_hist < 0) + int(bb_position <= 0.30) + int(ukf_momentum <= -20)
    readiness = "BULLISH" if bullish_votes >= 3 else "BEARISH" if bearish_votes >= 3 else "MIXED"
    order = pd.Series(order_row if order_row is not None else {}, dtype=object)
    return {
        "ticker": str(latest.get("ticker", order.get("ticker", ""))),
        "date": latest.get("date"),
        "close": _as_float(latest.get("close")),
        "rsi_14": rsi,
        "macd_hist": macd_hist,
        "bb_position_20": bb_position,
        "volume_ratio_20d": volume_ratio,
        "ukf_momentum_score": ukf_momentum,
        "ukf_trend_state": str(latest_ukf.get("state_label", "NEUTRAL_MOMENTUM")),
        "technical_readiness": readiness,
    }


def build_swing_order_technical_chart(
    one: pd.DataFrame,
    ticker: str,
    order_row: pd.Series | dict[str, Any] | None = None,
    decision_row: pd.Series | dict[str, Any] | None = None,
    *,
    lookback: int | None = 120,
    show_volume: bool = True,
    show_bollinger: bool = True,
    show_patterns: bool = True,
    show_ukf: bool = True,
) -> go.Figure:
    """Build a multi-panel swing-trading chart for next-day order planning."""
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.46, 0.13, 0.13, 0.14, 0.14],
        specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]],
    )
    required = {"date", "open", "high", "low", "close", "volume"}
    if one.empty or not required.issubset(one.columns):
        fig.update_layout(height=900, title=f"{ticker} Swing Trading Technical View")
        return fig
    data = add_indicators(one.sort_values("date").copy())
    if lookback and lookback > 0:
        data = data.tail(int(lookback)).copy()
    order = pd.Series(order_row if order_row is not None else {}, dtype=object)
    decision = pd.Series(decision_row if decision_row is not None else {}, dtype=object)

    fig.add_trace(
        go.Candlestick(
            x=data["date"],
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            name="K線",
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
            hovertemplate="%{x}<br>O=%{open:.2f}<br>H=%{high:.2f}<br>L=%{low:.2f}<br>C=%{close:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    for col, label, color in [("sma_20", "SMA20", "#2563eb"), ("sma_60", "SMA60", "#f59e0b")]:
        if col in data:
            fig.add_trace(go.Scatter(x=data["date"], y=data[col], mode="lines", name=label, line={"color": color, "width": 1.4}), row=1, col=1)
    if show_bollinger and {"bb_upper_20", "bb_lower_20"}.issubset(data.columns):
        fig.add_trace(go.Scatter(x=data["date"], y=data["bb_upper_20"], mode="lines", name="Bollinger Upper", line={"color": "#94a3b8", "dash": "dot"}), row=1, col=1)
        fig.add_trace(go.Scatter(x=data["date"], y=data["bb_lower_20"], mode="lines", name="Bollinger Lower", line={"color": "#94a3b8", "dash": "dot"}, fill="tonexty", fillcolor="rgba(148,163,184,0.09)"), row=1, col=1)

    last_close = _as_float(data["close"].iloc[-1])
    _add_hline(fig, last_close, "Current", "#0f172a", row=1, dash="solid")
    for key, label, color in [
        ("next_day_buy_high", "Buy Zone", "#22c55e"),
        ("next_day_buy_low", "Buy Zone Low", "#22c55e"),
        ("next_day_sell_low", "Sell Zone", "#f97316"),
        ("next_day_sell_high", "Sell Zone High", "#f97316"),
        ("tactical_stop_price", "戰術停損", "#dc2626"),
        ("hard_stop_price", "硬停損", "#991b1b"),
        ("strategy_buy_price", "策略買進", "#16a34a"),
        ("strategy_take_profit_price", "策略停利", "#2563eb"),
    ]:
        y = _as_float(order.get(key), np.nan)
        _add_named_level_trace(fig, data["date"], y, label, color, row=1, dash="dash" if "Zone" not in label else "dot")

    # Risk/reward and reachable buy/sell zones.
    x0, x1 = data["date"].iloc[0], data["date"].iloc[-1]
    buy_low = _as_float(order.get("next_day_buy_low"), np.nan)
    buy_high = _as_float(order.get("next_day_buy_high"), np.nan)
    sell_low = _as_float(order.get("next_day_sell_low"), np.nan)
    sell_high = _as_float(order.get("next_day_sell_high"), np.nan)
    if np.isfinite(buy_low) and np.isfinite(buy_high):
        fig.add_hrect(y0=min(buy_low, buy_high), y1=max(buy_low, buy_high), x0=x0, x1=x1, fillcolor="rgba(34,197,94,0.12)", line_width=0, row=1, col=1)
    if np.isfinite(sell_low) and np.isfinite(sell_high):
        fig.add_hrect(y0=min(sell_low, sell_high), y1=max(sell_low, sell_high), x0=x0, x1=x1, fillcolor="rgba(249,115,22,0.12)", line_width=0, row=1, col=1)

    # Smart-money / swing-trading overlays. Prefer optional smartmoneyconcepts
    # outputs when installed; fall back to the internal rule engine otherwise.
    smc_context = build_smc_context(data, swing_window=3, min_break_pct=0.003, prefer_external=True)
    structure = detect_swing_structure_signals(data, swing_window=3, min_break_pct=0.003)
    swings = smc_context.get("swings", pd.DataFrame())
    if swings.empty:
        swings = structure.get("swings", pd.DataFrame())
    events = smc_context.get("structure_events", pd.DataFrame())
    if events.empty:
        events = structure.get("structure_events", pd.DataFrame())
    fvg_zones = smc_context.get("fvg_zones", pd.DataFrame())
    if fvg_zones.empty:
        fvg_zones = detect_fvg_ifvg_zones(data)
    order_blocks = smc_context.get("order_blocks", pd.DataFrame())
    liquidity = smc_context.get("liquidity", pd.DataFrame())
    sfp_events = detect_sfp_events(data, swing_window=3)
    if not fvg_zones.empty:
        for _, zone in fvg_zones.tail(10).iterrows():
            fill = "rgba(34,197,94,0.10)" if zone["direction"] == "bullish" else "rgba(239,68,68,0.10)"
            if zone["status"] == "IFVG":
                fill = "rgba(124,58,237,0.13)"
            _add_signal_rect(fig, x0=zone["date"], x1=x1, y0=float(zone["y0"]), y1=float(zone["y1"]), name=str(zone["label"]), fillcolor=fill)
        latest_zones = fvg_zones.tail(10).copy()
        latest_zones["mid"] = (pd.to_numeric(latest_zones["y0"], errors="coerce") + pd.to_numeric(latest_zones["y1"], errors="coerce")) / 2
        fvg_x = latest_zones["date"]
        fvg_y = latest_zones["mid"]
        fvg_text = latest_zones["status"]
        fvg_color = np.where(latest_zones["status"] == "IFVG", "#7c3aed", "#0ea5e9")
    else:
        fvg_x = []
        fvg_y = []
        fvg_text = []
        fvg_color = "#0ea5e9"
    fig.add_trace(
        go.Scatter(
            x=fvg_x,
            y=fvg_y,
            mode="markers+text",
            name="FVG / IFVG",
            text=fvg_text,
            textposition="middle right",
            marker={"symbol": "square", "size": 8, "color": fvg_color},
            hovertemplate="%{x}<br>%{text}<br>zone=%{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    if not order_blocks.empty:
        latest_ob = order_blocks.tail(10).copy()
        for _, zone in latest_ob.iterrows():
            fill = "rgba(20,184,166,0.13)" if zone.get("direction") == "bullish" else "rgba(244,63,94,0.13)"
            _add_signal_rect(fig, x0=zone["date"], x1=x1, y0=float(zone["y0"]), y1=float(zone["y1"]), name=str(zone.get("label", "SMC OB")), fillcolor=fill)
        latest_ob["mid"] = (pd.to_numeric(latest_ob["y0"], errors="coerce") + pd.to_numeric(latest_ob["y1"], errors="coerce")) / 2
        ob_colors = latest_ob["direction"].map({"bullish": "#14b8a6", "bearish": "#f43f5e"}).fillna("#64748b")
        fig.add_trace(
            go.Scatter(
                x=latest_ob["date"],
                y=latest_ob["mid"],
                mode="markers+text",
                name="SMC Order Block",
                text=latest_ob["zone_type"],
                textposition="middle left",
                marker={"symbol": "diamond-wide", "size": 10, "color": ob_colors},
                hovertemplate="%{x}<br>%{text}<br>OB=%{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    else:
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", name="SMC Order Block", marker={"symbol": "diamond-wide", "size": 10, "color": "#14b8a6"}), row=1, col=1)
    if not liquidity.empty:
        latest_liq = liquidity.tail(14).copy()
        liq_colors = latest_liq["status"].map({"swept": "#7c3aed", "resting": "#06b6d4"}).fillna("#06b6d4")
        for _, item in latest_liq.iterrows():
            _add_named_level_trace(fig, data["date"], _as_float(item.get("level")), str(item.get("label", "SMC Liquidity")), "#06b6d4" if item.get("status") != "swept" else "#7c3aed", row=1, dash="dot")
        fig.add_trace(
            go.Scatter(
                x=latest_liq["date"],
                y=latest_liq["level"],
                mode="markers+text",
                name="SMC Liquidity",
                text=latest_liq["status"],
                textposition="top right",
                marker={"symbol": "line-ew", "size": 12, "color": liq_colors},
                hovertemplate="%{x}<br>%{text}<br>liquidity=%{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    else:
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", name="SMC Liquidity", marker={"symbol": "line-ew", "size": 12, "color": "#06b6d4"}), row=1, col=1)
    if not swings.empty:
        recent_swings = swings.tail(40)
        swing_highs = recent_swings[recent_swings["type"] == "swing_high"]
        swing_lows = recent_swings[recent_swings["type"] == "swing_low"]
        if not swing_highs.empty:
            fig.add_trace(go.Scatter(x=swing_highs["date"], y=swing_highs["price"], mode="markers", name="Swing High", marker={"symbol": "triangle-down", "size": 9, "color": "#ef4444"}, hovertemplate="%{x}<br>Swing High=%{y:.2f}<extra></extra>"), row=1, col=1)
        if not swing_lows.empty:
            fig.add_trace(go.Scatter(x=swing_lows["date"], y=swing_lows["price"], mode="markers", name="Swing Low", marker={"symbol": "triangle-up", "size": 9, "color": "#22c55e"}, hovertemplate="%{x}<br>Swing Low=%{y:.2f}<extra></extra>"), row=1, col=1)
    if not events.empty:
        latest_events = events.tail(20).copy()
        event_colors = latest_events["event_type"].map({"BOS_UP": "#16a34a", "CHOCH_UP": "#22c55e", "BOS_DOWN": "#dc2626", "CHOCH_DOWN": "#f97316"}).fillna("#64748b")
        fig.add_trace(
            go.Scatter(
                x=latest_events["date"],
                y=latest_events["price"],
                mode="markers+text",
                name="BOS / ChoCH",
                text=latest_events["event_type"],
                textposition="top center",
                marker={"symbol": "diamond", "size": 10, "color": event_colors},
                hovertemplate="%{x}<br>%{text}<br>price=%{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    if not sfp_events.empty:
        latest_sfp = sfp_events.tail(16).copy()
        sfp_colors = latest_sfp["direction"].map({"bullish": "#22c55e", "bearish": "#dc2626"}).fillna("#7c3aed")
        fig.add_trace(
            go.Scatter(
                x=latest_sfp["date"],
                y=latest_sfp["price"],
                mode="markers+text",
                name="SFP",
                text=latest_sfp["event_type"],
                textposition="bottom center",
                marker={"symbol": "x", "size": 11, "color": sfp_colors, "line": {"width": 2}},
                hovertemplate="%{x}<br>%{text}<br>ref=%{customdata:.2f}<br>price=%{y:.2f}<extra></extra>",
                customdata=latest_sfp["reference_price"],
            ),
            row=1,
            col=1,
        )

    if show_patterns:
        patterns = detect_candlestick_patterns(data).tail(24)
        if not patterns.empty:
            marker_symbol = patterns["direction"].map({"bullish": "triangle-up", "bearish": "triangle-down", "neutral": "circle"}).fillna("diamond")
            marker_color = patterns["direction"].map({"bullish": "#16a34a", "bearish": "#dc2626", "neutral": "#64748b"}).fillna("#7c3aed")
            fig.add_trace(
                go.Scatter(
                    x=patterns["date"],
                    y=patterns["price"],
                    mode="markers+text",
                    name="K線型態",
                    text=patterns["pattern"],
                    textposition="top center",
                    marker={"symbol": marker_symbol, "color": marker_color, "size": 9},
                    hovertemplate="%{x}<br>%{text}<br>price=%{y:.2f}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    if show_volume:
        colors = np.where(pd.to_numeric(data["close"], errors="coerce") >= pd.to_numeric(data["open"], errors="coerce"), "rgba(22,163,74,0.45)", "rgba(220,38,38,0.45)")
        fig.add_trace(go.Bar(x=data["date"], y=data["volume"], name="成交量", marker_color=colors, hovertemplate="%{x}<br>Volume=%{y:,.0f}<extra></extra>"), row=2, col=1)
        if "volume_ratio_20d" in data:
            fig.add_trace(go.Scatter(x=data["date"], y=data["volume_ratio_20d"], name="Volume Ratio", line={"color": "#7c3aed", "width": 1.2}, yaxis="y2"), row=2, col=1)

    fig.add_trace(go.Scatter(x=data["date"], y=data["rsi_14"], name="RSI14", line={"color": "#2563eb", "width": 1.5}), row=3, col=1)
    fig.add_hline(y=70, row=3, col=1, line_color="#dc2626", line_dash="dot", line_width=1)
    fig.add_hline(y=30, row=3, col=1, line_color="#16a34a", line_dash="dot", line_width=1)

    fig.add_trace(go.Scatter(x=data["date"], y=data["macd"], name="MACD", line={"color": "#2563eb", "width": 1.2}), row=4, col=1)
    fig.add_trace(go.Scatter(x=data["date"], y=data["macd_signal"], name="MACD Signal", line={"color": "#f97316", "width": 1.2}), row=4, col=1)
    hist_colors = np.where(pd.to_numeric(data["macd_hist"], errors="coerce") >= 0, "rgba(22,163,74,0.5)", "rgba(220,38,38,0.5)")
    fig.add_trace(go.Bar(x=data["date"], y=data["macd_hist"], name="MACD Hist", marker_color=hist_colors), row=4, col=1)

    if show_ukf:
        ukf = compute_ukf_momentum_state(data)
        fig.add_trace(go.Scatter(x=ukf["date"], y=ukf["raw_momentum"], name="Raw Momentum", line={"color": "rgba(148,163,184,0.65)", "width": 1}), row=5, col=1)
        fig.add_trace(go.Scatter(x=ukf["date"], y=ukf["noise_band_high"], name="UKF Noise High", line={"color": "rgba(124,58,237,0.2)", "width": 0.5}, showlegend=False), row=5, col=1)
        fig.add_trace(go.Scatter(x=ukf["date"], y=ukf["noise_band_low"], name="UKF Noise Band", fill="tonexty", fillcolor="rgba(124,58,237,0.12)", line={"color": "rgba(124,58,237,0.2)", "width": 0.5}), row=5, col=1)
        fig.add_trace(go.Scatter(x=ukf["date"], y=ukf["ukf_momentum"], name="UKF Momentum", line={"color": "#7c3aed", "width": 2.2}, hovertemplate="%{x}<br>UKF momentum=%{y:.1f}<extra></extra>"), row=5, col=1)
        fig.add_hline(y=20, row=5, col=1, line_color="#16a34a", line_dash="dot", line_width=1)
        fig.add_hline(y=-20, row=5, col=1, line_color="#dc2626", line_dash="dot", line_width=1)
        fig.add_hline(y=0, row=5, col=1, line_color="#64748b", line_dash="dot", line_width=1)

    action = str(decision.get("action", order.get("action", "HOLD_WAIT")) or "HOLD_WAIT")
    fig.add_annotation(x=data["date"].iloc[-1], y=last_close, text=f"{ticker}｜{action}", showarrow=True, arrowhead=2, ax=-60, ay=-40, bgcolor="rgba(15,23,42,0.8)", font={"color": "white"}, row=1, col=1)
    fig.update_layout(
        height=980,
        title=f"{ticker} Next-Day Swing Trading Technical View",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 10, "r": 10, "t": 65, "b": 20},
    )
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot", spikecolor="#64748b", spikethickness=1)
    fig.update_yaxes(showspikes=True, spikesnap="cursor", spikedash="dot", spikecolor="#64748b", spikethickness=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
    fig.update_yaxes(title_text="MACD", row=4, col=1)
    fig.update_yaxes(title_text="UKF", row=5, col=1, range=[-105, 105])
    return fig
