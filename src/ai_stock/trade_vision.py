from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analytics import add_indicators


_SWINGS_COLUMNS = ["date", "price", "type", "strength"]
_STRUCTURE_COLUMNS = ["date", "price", "event_type", "reference_price", "description"]
_LEVEL_COLUMNS = ["level", "type", "touches", "last_touch_date", "strength"]
_ZONE_COLUMNS = ["zone_id", "zone_type", "start_date", "end_date", "y0", "y1", "strength", "label"]


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _empty_structure() -> dict[str, pd.DataFrame]:
    return {
        "swings": pd.DataFrame(columns=_SWINGS_COLUMNS),
        "structure_events": pd.DataFrame(columns=_STRUCTURE_COLUMNS),
        "support_resistance": pd.DataFrame(columns=_LEVEL_COLUMNS),
    }


def detect_market_structure(one: pd.DataFrame, swing_window: int = 3, min_break_pct: float = 0.003) -> dict[str, pd.DataFrame]:
    """Detect simple swing highs/lows plus BOS/ChoCH structure events.

    This is intentionally lightweight and deterministic. It is not a full SMC engine;
    it marks local swing points, then checks close breaks of the latest prior swing.
    """
    required = {"date", "high", "low", "close"}
    if one.empty or not required.issubset(one.columns):
        return _empty_structure()
    data = one.sort_values("date").reset_index(drop=True).copy()
    swing_window = max(int(swing_window), 1)
    if len(data) < swing_window * 2 + 3:
        return _empty_structure()

    swing_rows: list[dict[str, Any]] = []
    highs = data["high"].astype(float).to_numpy()
    lows = data["low"].astype(float).to_numpy()
    for idx in range(swing_window, len(data) - swing_window):
        local_highs = highs[idx - swing_window : idx + swing_window + 1]
        local_lows = lows[idx - swing_window : idx + swing_window + 1]
        date = data.at[idx, "date"]
        if highs[idx] == np.nanmax(local_highs) and np.sum(np.isclose(local_highs, highs[idx])) == 1:
            strength = (highs[idx] - np.nanmean(np.delete(local_highs, swing_window))) / max(abs(highs[idx]), 1e-9)
            swing_rows.append({"date": date, "price": float(highs[idx]), "type": "swing_high", "strength": float(max(strength, 0.0))})
        if lows[idx] == np.nanmin(local_lows) and np.sum(np.isclose(local_lows, lows[idx])) == 1:
            strength = (np.nanmean(np.delete(local_lows, swing_window)) - lows[idx]) / max(abs(lows[idx]), 1e-9)
            swing_rows.append({"date": date, "price": float(lows[idx]), "type": "swing_low", "strength": float(max(strength, 0.0))})

    swings = pd.DataFrame(swing_rows, columns=_SWINGS_COLUMNS)
    if swings.empty:
        return {
            "swings": swings,
            "structure_events": pd.DataFrame(columns=_STRUCTURE_COLUMNS),
            "support_resistance": pd.DataFrame(columns=_LEVEL_COLUMNS),
        }
    swings = swings.sort_values("date").reset_index(drop=True)

    events: list[dict[str, Any]] = []
    last_high: dict[str, Any] | None = None
    last_low: dict[str, Any] | None = None
    trend: str | None = None
    swing_idx = 0
    swings_sorted = swings.sort_values("date").reset_index(drop=True)
    for _, bar in data.iterrows():
        bar_date = bar["date"]
        close = float(bar["close"])
        while swing_idx < len(swings_sorted) and swings_sorted.at[swing_idx, "date"] < bar_date:
            swing = swings_sorted.iloc[swing_idx].to_dict()
            if swing["type"] == "swing_high":
                last_high = swing
            elif swing["type"] == "swing_low":
                last_low = swing
            swing_idx += 1
        if last_high is not None:
            ref = float(last_high["price"])
            if close > ref * (1 + min_break_pct):
                event_type = "BOS_UP" if trend in {None, "UP"} else "CHOCH_UP"
                events.append(
                    {
                        "date": bar_date,
                        "price": close,
                        "event_type": event_type,
                        "reference_price": ref,
                        "description": f"Close broke above prior swing high {ref:.2f}.",
                    }
                )
                trend = "UP"
                last_high = None
        if last_low is not None:
            ref = float(last_low["price"])
            if close < ref * (1 - min_break_pct):
                event_type = "BOS_DOWN" if trend in {None, "DOWN"} else "CHOCH_DOWN"
                events.append(
                    {
                        "date": bar_date,
                        "price": close,
                        "event_type": event_type,
                        "reference_price": ref,
                        "description": f"Close broke below prior swing low {ref:.2f}.",
                    }
                )
                trend = "DOWN"
                last_low = None

    levels = _cluster_support_resistance(swings, tolerance_pct=max(min_break_pct * 2, 0.006))
    return {
        "swings": swings,
        "structure_events": pd.DataFrame(events, columns=_STRUCTURE_COLUMNS),
        "support_resistance": levels,
    }


def _cluster_support_resistance(swings: pd.DataFrame, tolerance_pct: float = 0.006) -> pd.DataFrame:
    if swings.empty:
        return pd.DataFrame(columns=_LEVEL_COLUMNS)
    rows: list[dict[str, Any]] = []
    for level_type, swing_type in [("resistance", "swing_high"), ("support", "swing_low")]:
        subset = swings[swings["type"] == swing_type].sort_values("price").copy()
        if subset.empty:
            continue
        clusters: list[list[pd.Series]] = []
        for _, row in subset.iterrows():
            price = float(row["price"])
            placed = False
            for cluster in clusters:
                center = float(np.mean([float(item["price"]) for item in cluster]))
                if abs(price - center) / max(abs(center), 1e-9) <= tolerance_pct:
                    cluster.append(row)
                    placed = True
                    break
            if not placed:
                clusters.append([row])
        for cluster in clusters:
            level = float(np.mean([float(item["price"]) for item in cluster]))
            last_touch = max(item["date"] for item in cluster)
            strength = float(len(cluster) + np.nanmean([float(item.get("strength", 0)) for item in cluster]) * 100)
            rows.append({"level": level, "type": level_type, "touches": int(len(cluster)), "last_touch_date": last_touch, "strength": strength})
    if not rows:
        return pd.DataFrame(columns=_LEVEL_COLUMNS)
    return pd.DataFrame(rows, columns=_LEVEL_COLUMNS).sort_values(["strength", "last_touch_date"], ascending=[False, False]).reset_index(drop=True)


def build_trade_zones(one: pd.DataFrame, structure_result: dict[str, pd.DataFrame], lookback: int = 80) -> pd.DataFrame:
    """Build support/resistance, supply/demand, and premium/discount zones."""
    required = {"date", "high", "low", "close"}
    if one.empty or not required.issubset(one.columns):
        return pd.DataFrame(columns=_ZONE_COLUMNS)
    data = one.sort_values("date").tail(max(int(lookback), 5)).copy()
    start_date = data["date"].iloc[0]
    end_date = data["date"].iloc[-1]
    high = float(data["high"].max())
    low = float(data["low"].min())
    span = max(high - low, abs(high) * 0.002, 1e-9)
    pad = span * 0.025
    equilibrium = (high + low) / 2
    rows: list[dict[str, Any]] = [
        {"zone_id": "premium", "zone_type": "premium", "start_date": start_date, "end_date": end_date, "y0": equilibrium, "y1": high, "strength": 1.0, "label": "Premium"},
        {"zone_id": "discount", "zone_type": "discount", "start_date": start_date, "end_date": end_date, "y0": low, "y1": equilibrium, "strength": 1.0, "label": "Discount"},
        {"zone_id": "equilibrium", "zone_type": "equilibrium", "start_date": start_date, "end_date": end_date, "y0": equilibrium, "y1": equilibrium, "strength": 1.0, "label": "Equilibrium"},
    ]
    levels = structure_result.get("support_resistance", pd.DataFrame()) if structure_result else pd.DataFrame()
    if levels is not None and not levels.empty:
        for idx, level_row in levels.head(8).iterrows():
            level = float(level_row["level"])
            level_kind = str(level_row["type"])
            zone_type = "support" if level_kind == "support" else "resistance"
            rows.append(
                {
                    "zone_id": f"{zone_type}_{idx}",
                    "zone_type": zone_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "y0": level - pad,
                    "y1": level + pad,
                    "strength": float(level_row.get("strength", 1)),
                    "label": "Support Zone" if zone_type == "support" else "Resistance Zone",
                }
            )
            if idx < 4:
                rows.append(
                    {
                        "zone_id": f"{'demand' if zone_type == 'support' else 'supply'}_{idx}",
                        "zone_type": "demand" if zone_type == "support" else "supply",
                        "start_date": start_date,
                        "end_date": end_date,
                        "y0": level - pad * 1.8,
                        "y1": level + pad * 1.8,
                        "strength": float(level_row.get("strength", 1)) * 0.8,
                        "label": "Demand Zone" if zone_type == "support" else "Supply Zone",
                    }
                )
    return pd.DataFrame(rows, columns=_ZONE_COLUMNS)


def build_trade_plan_from_decision(decision_row: pd.Series, current_price: float) -> dict[str, Any]:
    row = pd.Series(decision_row) if decision_row is not None else pd.Series(dtype=object)
    ticker = str(row.get("ticker", ""))
    action = str(row.get("action", "HOLD_WAIT") or "HOLD_WAIT")
    current = _as_float(current_price)
    entry = _as_float(row.get("suggested_buy_price", current), current)
    stop = _as_float(row.get("stop_loss_price", np.nan), np.nan)
    tp1 = _as_float(row.get("suggested_sell_price", np.nan), np.nan)
    if not np.isfinite(stop) or stop >= entry:
        stop = entry * 0.97 if np.isfinite(entry) else np.nan
    risk = abs(entry - stop) if np.isfinite(entry) and np.isfinite(stop) else np.nan
    if not np.isfinite(tp1) or tp1 <= entry:
        tp1 = entry + risk if np.isfinite(risk) else np.nan
    tp2 = entry + 2 * risk if np.isfinite(entry) and np.isfinite(risk) else np.nan
    tp3 = entry + 3 * risk if np.isfinite(entry) and np.isfinite(risk) else np.nan
    reward = tp1 - entry if np.isfinite(tp1) and np.isfinite(entry) else np.nan
    rr = reward / risk if np.isfinite(reward) and np.isfinite(risk) and risk > 0 else np.nan
    risk_pct = (risk / entry * 100) if np.isfinite(entry) and entry else np.nan
    reward_pct = (reward / entry * 100) if np.isfinite(entry) and entry else np.nan

    if np.isfinite(current) and np.isfinite(stop) and current <= stop:
        status = "SL_TRIGGERED"
    elif np.isfinite(current) and np.isfinite(tp3) and current >= tp3:
        status = "TP3_HIT"
    elif np.isfinite(current) and np.isfinite(tp2) and current >= tp2:
        status = "TP2_HIT"
    elif np.isfinite(current) and np.isfinite(tp1) and current >= tp1:
        status = "TP1_HIT"
    elif action in {"BUY_WATCH", "ADD_OR_HOLD"} and np.isfinite(current) and np.isfinite(entry) and current <= entry * 1.01:
        status = "ACTIVE"
    elif action in {"SELL_OR_AVOID", "REDUCE_OR_EXIT"}:
        status = "INVALIDATED"
    else:
        status = "WAITING"

    return {
        "ticker": ticker,
        "action": action,
        "current_price": current,
        "entry_price": entry,
        "stop_loss_price": stop,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "take_profit_3": tp3,
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
        "rr_ratio": rr,
        "kelly_fraction": _as_float(row.get("kelly_fraction", 0.0), 0.0),
        "plan_status": status,
        "explanation": "研究輔助，不自動下單；請自行確認券商即時報價、流動性與個人風險。",
        "action_reason": str(row.get("action_reason", "") or ""),
        "kelly_reason": str(row.get("kelly_reason", "") or ""),
    }


def build_mtf_matrix(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if prices.empty or "ticker" not in prices.columns:
        return pd.DataFrame(columns=["timeframe", "trend_state", "momentum_score", "volume_score", "volatility_score", "signal_strength", "description"])
    one = prices[prices["ticker"].astype(str) == str(ticker)].sort_values("date").copy()
    if one.empty:
        return pd.DataFrame(columns=["timeframe", "trend_state", "momentum_score", "volume_score", "volatility_score", "signal_strength", "description"])
    one["date"] = pd.to_datetime(one["date"])
    specs = [("1D", one), ("1W", _resample_ohlcv(one, "W")), ("1M", _resample_ohlcv(one, "ME"))]
    rows: list[dict[str, Any]] = []
    for timeframe, frame in specs:
        if len(frame) < 3:
            continue
        ind = add_indicators(frame).sort_values("date")
        latest = ind.iloc[-1]
        close = _as_float(latest.get("close"))
        sma20 = _as_float(latest.get("sma_20"), close)
        sma60 = _as_float(latest.get("sma_60"), sma20)
        if close > sma20 >= sma60:
            trend_state = "BULL"
            trend_component = 80
        elif close < sma20 <= sma60:
            trend_state = "BEAR"
            trend_component = 25
        else:
            trend_state = "NEUTRAL"
            trend_component = 50
        rsi = _as_float(latest.get("rsi_14"), 50)
        macd_hist = _as_float(latest.get("macd_hist"), 0)
        roc = _as_float(latest.get("return_20d"), 0) * 100
        momentum = np.clip(50 + (rsi - 50) * 0.6 + np.tanh(macd_hist / max(abs(close) * 0.01, 1e-9)) * 15 + np.clip(roc, -10, 10), 0, 100)
        vol_ratio = _as_float(latest.get("volume_ratio_20d"), 1.0)
        volume_score = np.clip(50 + (vol_ratio - 1) * 35, 0, 100)
        atr_pct = _as_float(latest.get("atr_pct_14"), 0.03)
        bb_width = (_as_float(latest.get("bb_upper_20"), close) - _as_float(latest.get("bb_lower_20"), close)) / close if close else np.nan
        volatility_score = np.clip(70 - abs(atr_pct - 0.03) * 450 - max(bb_width - 0.12, 0) * 100, 0, 100)
        strength = float(np.clip(trend_component * 0.35 + momentum * 0.3 + volume_score * 0.15 + volatility_score * 0.2, 0, 100))
        rows.append(
            {
                "timeframe": timeframe,
                "trend_state": trend_state,
                "momentum_score": float(momentum),
                "volume_score": float(volume_score),
                "volatility_score": float(volatility_score),
                "signal_strength": strength,
                "description": f"{timeframe}: {trend_state}, momentum {momentum:.0f}, strength {strength:.0f}.",
            }
        )
    return pd.DataFrame(rows)


def _resample_ohlcv(one: pd.DataFrame, rule: str) -> pd.DataFrame:
    if one.empty:
        return one.copy()
    work = one.copy()
    work["date"] = pd.to_datetime(work["date"])
    resampled = (
        work.set_index("date")
        .resample(rule)
        .agg({"ticker": "last", "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    return resampled


def compute_trade_signal_score(snapshot_row: pd.Series, decision_row: pd.Series | None, structure_events: pd.DataFrame, mtf_matrix: pd.DataFrame) -> dict[str, Any]:
    snap = pd.Series(snapshot_row) if snapshot_row is not None else pd.Series(dtype=object)
    decision = pd.Series(decision_row) if decision_row is not None else pd.Series(dtype=object)
    trend_score = float(np.clip(mtf_matrix["signal_strength"].mean() if not mtf_matrix.empty and "signal_strength" in mtf_matrix else 50, 0, 100))
    rsi = _as_float(snap.get("rsi_14"), 50)
    macd = _as_float(snap.get("macd_hist"), 0)
    momentum_score = float(np.clip(50 + (rsi - 50) * 0.7 + np.tanh(macd) * 15, 0, 100))
    volume_score = float(np.clip(50 + (_as_float(snap.get("volume_ratio_20d"), 1) - 1) * 35, 0, 100))
    recent_events = structure_events.tail(5) if structure_events is not None and not structure_events.empty else pd.DataFrame()
    structure_score = 50.0
    if not recent_events.empty:
        last_event = str(recent_events.iloc[-1].get("event_type", ""))
        if last_event in {"BOS_UP", "CHOCH_UP"}:
            structure_score = 72.0
        elif last_event in {"BOS_DOWN", "CHOCH_DOWN"}:
            structure_score = 28.0
    risk_unit = abs(_as_float(decision.get("risk_unit_pct"), _as_float(snap.get("atr_pct_14"), 0.03) * 100))
    kelly = _as_float(decision.get("kelly_fraction"), 0)
    risk_score = float(np.clip(80 - risk_unit * 6 + kelly * 80, 0, 100))
    portfolio_score = 50.0
    if _as_float(decision.get("relationship_adjusted_return_pct"), _as_float(decision.get("expected_return_pct"), 0)) > 0:
        portfolio_score += 10
    if str(decision.get("action", "")) == "SELL_OR_AVOID":
        portfolio_score -= 25
    portfolio_score = float(np.clip(portfolio_score, 0, 100))
    composite = float(
        np.clip(
            trend_score * 0.25
            + momentum_score * 0.20
            + volume_score * 0.15
            + structure_score * 0.20
            + risk_score * 0.10
            + portfolio_score * 0.10,
            0,
            100,
        )
    )
    if composite >= 72:
        status = "STRONG_BUY_WATCH"
    elif composite >= 60:
        status = "BUY_WATCH"
    elif composite <= 35 or str(decision.get("action", "")) == "SELL_OR_AVOID":
        status = "SELL_OR_AVOID"
    elif risk_score < 35:
        status = "RISK_ALERT"
    else:
        status = "HOLD_WAIT"
    return {
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "volume_score": volume_score,
        "structure_score": structure_score,
        "risk_score": risk_score,
        "portfolio_score": portfolio_score,
        "composite_score": composite,
        "status": status,
    }


def build_trade_narrative(
    ticker: str,
    trade_plan: dict[str, Any],
    score: dict[str, Any],
    mtf_matrix: pd.DataFrame,
    structure_events: pd.DataFrame,
    zones: pd.DataFrame,
) -> list[str]:
    lines: list[str] = []
    if not mtf_matrix.empty:
        bull = int((mtf_matrix["trend_state"] == "BULL").sum())
        bear = int((mtf_matrix["trend_state"] == "BEAR").sum())
        if bull > bear:
            lines.append(f"{ticker} 多時間框架趨勢偏多，但仍需等價格接近計畫區域確認。")
        elif bear > bull:
            lines.append(f"{ticker} 多時間框架偏弱，追價風險較高，應優先檢查停損與曝險。")
        else:
            lines.append(f"{ticker} 多時間框架尚未同步，適合等待更明確的方向訊號。")
    if structure_events is not None and not structure_events.empty:
        last_event = str(structure_events.iloc[-1].get("event_type", ""))
        if last_event.endswith("UP"):
            lines.append(f"最近出現 {last_event}，代表短線市場結構轉強或延續上攻。")
        elif last_event.endswith("DOWN"):
            lines.append(f"最近出現 {last_event}，代表短線結構轉弱，需避免忽略下行風險。")
    rr = _as_float(trade_plan.get("rr_ratio"), np.nan)
    if np.isfinite(rr):
        if rr >= 2:
            lines.append(f"Entry / SL / TP1 的風險報酬比約 {rr:.2f}，交易計畫具備可觀察的風險報酬條件。")
        else:
            lines.append(f"Entry / SL / TP1 的風險報酬比約 {rr:.2f}，若無額外確認訊號，不宜過度加碼。")
    composite = _as_float(score.get("composite_score"), 50)
    status = str(score.get("status", "HOLD_WAIT"))
    lines.append(f"綜合訊號分數為 {composite:.0f}/100，狀態為 {status}；這是研究輔助，不代表自動下單。")
    if zones is not None and not zones.empty:
        lines.append("圖上支撐 / 壓力與 Premium / Discount 區域可用來檢查追價、回踩與停損位置是否合理。")
    action_reason = str(trade_plan.get("action_reason", "") or "")
    if action_reason:
        lines.append(action_reason[:160])
    return lines[:6]


def build_trade_vision_chart(
    one: pd.DataFrame,
    ticker: str,
    decision_row: pd.Series | None = None,
    structure: pd.DataFrame | None = None,
    zones: pd.DataFrame | None = None,
    signal_events: pd.DataFrame | None = None,
    show_volume: bool = True,
    show_structure: bool = True,
    show_zones: bool = True,
    show_trade_plan: bool = True,
) -> go.Figure:
    fig = go.Figure()
    if one.empty:
        return fig
    data = one.sort_values("date").copy()
    ind = add_indicators(data)
    fig.add_trace(
        go.Candlestick(
            x=data["date"],
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            name="Candlestick",
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
            hovertemplate="%{x}<br>O=%{open:.2f}<br>H=%{high:.2f}<br>L=%{low:.2f}<br>C=%{close:.2f}<extra></extra>",
        )
    )
    fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_20"], name="SMA20", line={"color": "#2563eb", "width": 1.7}, hovertemplate="SMA20=%{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_60"], name="SMA60", line={"color": "#f97316", "width": 1.7}, hovertemplate="SMA60=%{y:.2f}<extra></extra>"))
    last_close = float(data["close"].iloc[-1])
    _add_line_trace(fig, data["date"], last_close, "Current Price", "#0f172a", "dot")

    if show_zones and zones is not None and not zones.empty:
        _add_zone_shapes(fig, zones)
    if show_trade_plan and decision_row is not None:
        plan = build_trade_plan_from_decision(pd.Series(decision_row), last_close)
        _add_trade_plan_shapes(fig, data["date"], plan)
        _add_line_trace(fig, data["date"], plan["entry_price"], "Entry", "#16a34a", "dash")
        _add_line_trace(fig, data["date"], plan["stop_loss_price"], "Stop Loss", "#dc2626", "dash")
        _add_line_trace(fig, data["date"], plan["take_profit_1"], "Take Profit", "#2563eb", "dash")
        _add_action_label(fig, data, pd.Series(decision_row), plan)
    if show_structure:
        if signal_events is not None and not signal_events.empty:
            _add_swings(fig, signal_events)
        if structure is not None and not structure.empty:
            _add_structure_events(fig, structure)
    if show_volume and "volume" in data.columns:
        fig.add_trace(
            go.Bar(
                x=data["date"],
                y=data["volume"],
                name="Volume",
                marker_color="rgba(100,116,139,0.23)",
                yaxis="y2",
                hovertemplate="Volume=%{y:,.0f}<extra></extra>",
            )
        )
        fig.update_layout(yaxis2={"overlaying": "y", "side": "right", "showgrid": False, "title": "Volume", "position": 1.0})
    fig.update_layout(
        title=f"{ticker} Advanced Trading Chart",
        height=680,
        margin={"l": 10, "r": 10, "t": 48, "b": 10},
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        template="plotly_white",
    )
    return fig


def _add_line_trace(fig: go.Figure, x: pd.Series, y: float, name: str, color: str, dash: str) -> None:
    if x.empty or not np.isfinite(y):
        return
    fig.add_trace(
        go.Scatter(
            x=[x.min(), x.max()],
            y=[y, y],
            mode="lines",
            name=name,
            line={"color": color, "dash": dash, "width": 2},
            hovertemplate=f"{name}: %{{y:.2f}}<extra></extra>",
        )
    )


def _add_zone_shapes(fig: go.Figure, zones: pd.DataFrame) -> None:
    color_by_type = {
        "resistance": "rgba(220,38,38,0.13)",
        "supply": "rgba(239,68,68,0.10)",
        "support": "rgba(20,184,166,0.13)",
        "demand": "rgba(16,185,129,0.10)",
        "premium": "rgba(248,113,113,0.05)",
        "discount": "rgba(45,212,191,0.05)",
        "equilibrium": "rgba(15,23,42,0.0)",
    }
    line_by_type = {
        "equilibrium": {"color": "rgba(15,23,42,0.55)", "dash": "dash", "width": 1},
    }
    for _, row in zones.iterrows():
        zone_type = str(row.get("zone_type", ""))
        x0, x1 = row.get("start_date"), row.get("end_date")
        y0, y1 = _as_float(row.get("y0")), _as_float(row.get("y1"))
        if not np.isfinite(y0) or not np.isfinite(y1):
            continue
        if zone_type == "equilibrium":
            fig.add_shape(type="line", x0=x0, x1=x1, y0=y0, y1=y0, line=line_by_type["equilibrium"])
        else:
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=min(y0, y1), y1=max(y0, y1), line={"width": 0}, fillcolor=color_by_type.get(zone_type, "rgba(148,163,184,0.08)"), layer="below")


def _add_trade_plan_shapes(fig: go.Figure, x: pd.Series, plan: dict[str, Any]) -> None:
    if x.empty:
        return
    entry = _as_float(plan.get("entry_price"))
    stop = _as_float(plan.get("stop_loss_price"))
    tp = _as_float(plan.get("take_profit_1"))
    if not all(np.isfinite(v) for v in [entry, stop, tp]):
        return
    x0, x1 = x.min(), x.max()
    fig.add_shape(type="rect", x0=x0, x1=x1, y0=min(entry, tp), y1=max(entry, tp), fillcolor="rgba(22,163,74,0.08)", line={"width": 0}, layer="below")
    fig.add_shape(type="rect", x0=x0, x1=x1, y0=min(entry, stop), y1=max(entry, stop), fillcolor="rgba(220,38,38,0.08)", line={"width": 0}, layer="below")


def _add_action_label(fig: go.Figure, data: pd.DataFrame, row: pd.Series, plan: dict[str, Any]) -> None:
    action = str(row.get("action", "HOLD_WAIT"))
    label = {"BUY_WATCH": "BUY", "HOLD_WAIT": "HOLD", "SELL_OR_AVOID": "AVOID", "ADD_OR_HOLD": "BUY"}.get(action, action)
    color = {"BUY": "#16a34a", "HOLD": "#eab308", "AVOID": "#dc2626"}.get(label, "#64748b")
    fig.add_trace(
        go.Scatter(
            x=[data["date"].iloc[-1]],
            y=[data["close"].iloc[-1]],
            mode="markers+text",
            name=f"Signal {label}",
            text=[label],
            textposition="top center",
            marker={"size": 13, "color": color, "symbol": "circle", "line": {"color": "white", "width": 1}},
            hovertemplate=f"{label}<br>Plan={plan.get('plan_status')}<extra></extra>",
        )
    )


def _add_swings(fig: go.Figure, swings: pd.DataFrame) -> None:
    for swing_type, symbol, color, name in [("swing_high", "triangle-down", "#dc2626", "Swing High"), ("swing_low", "triangle-up", "#16a34a", "Swing Low")]:
        work = swings[swings["type"] == swing_type]
        if work.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=work["date"],
                y=work["price"],
                mode="markers",
                name=name,
                marker={"symbol": symbol, "size": 9, "color": color, "line": {"color": "white", "width": 1}},
                customdata=work[["strength"]],
                hovertemplate=f"{name}<br>%{{x}}<br>price=%{{y:.2f}}<br>strength=%{{customdata[0]:.3f}}<extra></extra>",
            )
        )


def _add_structure_events(fig: go.Figure, events: pd.DataFrame) -> None:
    if events.empty:
        return
    colors = ["#16a34a" if str(v).endswith("UP") else "#dc2626" for v in events["event_type"]]
    fig.add_trace(
        go.Scatter(
            x=events["date"],
            y=events["price"],
            mode="markers+text",
            name="BOS / ChoCH",
            text=events["event_type"],
            textposition="top center",
            marker={"symbol": "diamond", "size": 10, "color": colors, "line": {"color": "white", "width": 1}},
            customdata=events[["reference_price", "description"]],
            hovertemplate="%{text}<br>%{x}<br>price=%{y:.2f}<br>ref=%{customdata[0]:.2f}<br>%{customdata[1]}<extra></extra>",
        )
    )
