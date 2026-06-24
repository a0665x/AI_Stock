from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .smc_adapter import build_smc_context

_ORDER_COLUMNS = [
    "ticker",
    "quantity",
    "current_price",
    "action",
    "composite_score",
    "median_intraday_range_pct",
    "p80_intraday_range_pct",
    "next_day_buy_low",
    "next_day_buy_high",
    "next_day_sell_low",
    "next_day_sell_high",
    "tactical_stop_price",
    "hard_stop_price",
    "strategy_buy_price",
    "strategy_take_profit_price",
    "buy_touch_probability",
    "sell_touch_probability",
    "tactical_stop_touch_probability",
    "smc_confidence_score",
    "smc_bias",
    "smc_timeframe_summary",
    "buy_urgency_score",
    "sell_urgency_score",
    "priority_score",
    "suggested_order_type",
    "suggested_action",
    "reason",
]

_SMC_SIGNAL_COLUMNS = [
    "ticker",
    "timeframe",
    "engine",
    "smc_confidence_score",
    "smc_bias",
    "bullish_score",
    "bearish_score",
    "net_score",
    "smc_summary",
]


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def estimate_touch_probability_label(distance_pct: float, median_range_pct: float, p80_range_pct: float) -> str:
    """Classify whether a price level is likely reachable on the next trading day.

    Inputs are percentage distances, e.g. 1.2 means 1.2% away from current price.
    The thresholds intentionally use recent intraday range, not model targets.
    """
    distance = abs(_as_float(distance_pct, np.inf))
    median_range = max(abs(_as_float(median_range_pct, 0.0)), 1e-9)
    p80_range = max(abs(_as_float(p80_range_pct, median_range)), median_range)
    if distance <= median_range * 0.35:
        return "HIGH"
    if distance <= median_range * 0.65:
        return "MEDIUM"
    if distance <= p80_range:
        return "LOW_MEDIUM"
    return "LOW_STRATEGY_LEVEL"


def _price_history_stats(one: pd.DataFrame, lookback: int = 20) -> dict[str, float]:
    if one.empty or not {"high", "low", "close"}.issubset(one.columns):
        return {"current_price": np.nan, "median_intraday_range_pct": np.nan, "p80_intraday_range_pct": np.nan, "previous_low": np.nan, "previous_high": np.nan}
    data = one.sort_values("date").tail(max(int(lookback), 2)).copy()
    close = pd.to_numeric(data["close"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    ranges = ((high - low) / close.replace(0, np.nan) * 100).replace([np.inf, -np.inf], np.nan).dropna()
    current = float(close.dropna().iloc[-1]) if not close.dropna().empty else np.nan
    return {
        "current_price": current,
        "median_intraday_range_pct": float(ranges.median()) if not ranges.empty else 2.0,
        "p80_intraday_range_pct": float(ranges.quantile(0.8)) if not ranges.empty else 3.0,
        "previous_low": float(low.dropna().iloc[-2]) if len(low.dropna()) >= 2 else np.nan,
        "previous_high": float(high.dropna().iloc[-2]) if len(high.dropna()) >= 2 else np.nan,
    }


def _order_type(
    action: str,
    quantity: float,
    kelly: float,
    adjusted_return: float,
    buy_probability: str,
    sell_probability: str,
    unrealized_pnl_pct: float = np.nan,
) -> tuple[str, str]:
    has_position = np.isfinite(quantity) and quantity > 0
    profitable = np.isfinite(unrealized_pnl_pct) and unrealized_pnl_pct > 0
    materially_losing = np.isfinite(unrealized_pnl_pct) and unrealized_pnl_pct < -3
    reachable_sell = sell_probability in {"HIGH", "MEDIUM"}

    if action == "SELL_OR_AVOID":
        return "REDUCE_OR_AVOID", "模型與風險報酬偏弱；已有持倉時優先檢查減碼或保護停損。"
    if has_position and adjusted_return > 0 and reachable_sell:
        if materially_losing:
            return "REBOUND_REDUCE_LIMIT", "持倉仍虧損但短線反彈區較可觸及；若要降低風險，應視為反彈減碼限價，不應稱為停利。"
        return "TAKE_PROFIT_LIMIT", "已有持倉且隔日賣出區較可觸及，可用分批停利限價單觀察。"
    if action == "BUY_WATCH" and kelly > 0 and buy_probability in {"HIGH", "MEDIUM", "LOW_MEDIUM"}:
        return ("ADD_LIMIT" if has_position else "BUY_LIMIT"), "偏多且隔日回踩區具有可觸及性，可用限價單小倉位觀察。"
    if has_position:
        if profitable:
            return "PROTECT_PROFIT_STOP", "已有獲利但加碼優勢不足；用戰術停損保護獲利，避免把獲利部位重新暴露成高風險。"
        return "PROTECTIVE_STOP", "訊號尚未足以加碼；先用戰術停損與硬停損保護持倉。"
    return "NO_ORDER_WAIT", "沒有持倉且優勢不足；等待價格進入更好的回踩區或訊號轉強。"


def _latest_recent_count(frame: pd.DataFrame, date_col: str = "date", lookback: int = 18) -> pd.DataFrame:
    if frame is None or frame.empty or date_col not in frame.columns:
        return pd.DataFrame()
    return frame.sort_values(date_col).tail(max(int(lookback), 1)).copy()


def _score_smc_context(ctx: dict[str, Any]) -> tuple[float, float, str]:
    bullish = 0.0
    bearish = 0.0
    notes: list[str] = []

    events = _latest_recent_count(ctx.get("structure_events", pd.DataFrame()), lookback=10)
    for _, event in events.iterrows():
        event_type = str(event.get("event_type", "")).upper()
        if event_type in {"BOS_UP", "CHOCH_UP"}:
            bullish += 16 if event_type == "BOS_UP" else 12
            notes.append(event_type)
        elif event_type in {"BOS_DOWN", "CHOCH_DOWN"}:
            bearish += 16 if event_type == "BOS_DOWN" else 12
            notes.append(event_type)

    fvg = _latest_recent_count(ctx.get("fvg_zones", pd.DataFrame()), lookback=8)
    for _, zone in fvg.iterrows():
        direction = str(zone.get("direction", "")).lower()
        status = str(zone.get("status", "FVG")).upper()
        weight = 8 if status == "FVG" else 5
        if direction == "bullish":
            bullish += weight
            notes.append(status + "↑")
        elif direction == "bearish":
            bearish += weight
            notes.append(status + "↓")

    order_blocks = _latest_recent_count(ctx.get("order_blocks", pd.DataFrame()), lookback=8)
    for _, block in order_blocks.iterrows():
        direction = str(block.get("direction", "")).lower()
        strength = max(_as_float(block.get("strength"), 0.5), 0.2)
        weight = min(14.0, 8.0 + strength * 6.0)
        if direction == "bullish":
            bullish += weight
            notes.append("OB↑")
        elif direction == "bearish":
            bearish += weight
            notes.append("OB↓")

    liquidity = _latest_recent_count(ctx.get("liquidity", pd.DataFrame()), lookback=8)
    for _, liq in liquidity.iterrows():
        direction = str(liq.get("direction", "")).lower()
        status = str(liq.get("status", "resting")).lower()
        swept = status == "swept"
        weight = 8.0 if swept else 4.0
        # Buy-side liquidity overhead is usually sell-pressure/take-profit context;
        # sell-side liquidity below price is usually buy-dip/sweep context.
        if direction == "sell_side":
            bullish += weight
            notes.append("SSL swept" if swept else "SSL")
        elif direction == "buy_side":
            bearish += weight
            notes.append("BSL swept" if swept else "BSL")

    swings = _latest_recent_count(ctx.get("swings", pd.DataFrame()), lookback=6)
    if not swings.empty:
        last_type = str(swings.iloc[-1].get("type", "")).lower()
        if last_type == "swing_low":
            bullish += 4
            notes.append("last swing low")
        elif last_type == "swing_high":
            bearish += 4
            notes.append("last swing high")

    bullish = float(min(bullish, 100.0))
    bearish = float(min(bearish, 100.0))
    summary = ", ".join(dict.fromkeys(notes[:8])) if notes else "SMC 訊號不足"
    return bullish, bearish, summary


def build_smc_timeframe_signals(price_frames: dict[str, pd.DataFrame], *, prefer_external: bool = True) -> pd.DataFrame:
    """Build per-ticker 15m/1h/1d SMC scores from OHLCV frames.

    ``price_frames`` maps timeframe labels (for example ``15m``, ``1h``, ``1d``)
    to canonical OHLCV DataFrames. The function is deterministic and never fetches
    data; callers decide whether intraday frames come from yfinance, CSV, or a
    future broker data source.
    """
    rows: list[dict[str, Any]] = []
    for timeframe, frame in price_frames.items():
        if frame is None or frame.empty or "ticker" not in frame.columns:
            continue
        for ticker, one in frame.groupby(frame["ticker"].astype(str).str.upper()):
            one = one.sort_values("date").tail(240).copy()
            if len(one) < 20:
                continue
            ctx = build_smc_context(one, swing_window=3, min_break_pct=0.003, prefer_external=prefer_external)
            bullish, bearish, summary = _score_smc_context(ctx)
            net = bullish - bearish
            confidence = float(np.clip(50 + abs(net) * 0.5 + max(bullish, bearish) * 0.25, 0, 100))
            if net >= 12:
                bias = "BULLISH"
            elif net <= -12:
                bias = "BEARISH"
            else:
                bias = "MIXED"
            rows.append(
                {
                    "ticker": str(ticker),
                    "timeframe": str(timeframe),
                    "engine": str(ctx.get("engine", "fallback")),
                    "smc_confidence_score": confidence,
                    "smc_bias": bias,
                    "bullish_score": bullish,
                    "bearish_score": bearish,
                    "net_score": float(net),
                    "smc_summary": summary,
                }
            )
    return pd.DataFrame(rows, columns=_SMC_SIGNAL_COLUMNS) if rows else pd.DataFrame(columns=_SMC_SIGNAL_COLUMNS)


def _probability_score(label: str) -> float:
    return {"HIGH": 100.0, "MEDIUM": 72.0, "LOW_MEDIUM": 45.0, "LOW_STRATEGY_LEVEL": 18.0}.get(str(label), 25.0)


def augment_order_plan_with_smc(plan: pd.DataFrame, smc_signals: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add SMC multi-timeframe confidence and buy/sell urgency scores to a plan."""
    if plan.empty:
        return plan.reindex(columns=_ORDER_COLUMNS)
    out = plan.copy()
    signals = smc_signals.copy() if smc_signals is not None and not smc_signals.empty else pd.DataFrame(columns=_SMC_SIGNAL_COLUMNS)
    weights = {"15m": 0.25, "30m": 0.25, "1h": 0.30, "60m": 0.30, "1d": 0.45, "1wk": 0.15}
    for idx, row in out.iterrows():
        ticker = str(row.get("ticker", "")).upper()
        subset = signals[signals["ticker"].astype(str).str.upper() == ticker] if "ticker" in signals.columns else pd.DataFrame()
        if subset.empty:
            smc_conf = 50.0
            bias = "MIXED"
            summary = "SMC 多週期資料不足；僅使用價格波動規劃掛單。"
            net = 0.0
        else:
            weighted_net = 0.0
            weighted_conf = 0.0
            total_w = 0.0
            parts: list[str] = []
            for _, sig in subset.iterrows():
                tf = str(sig.get("timeframe", ""))
                w = weights.get(tf, 0.2)
                weighted_net += _as_float(sig.get("net_score"), 0.0) * w
                weighted_conf += _as_float(sig.get("smc_confidence_score"), 50.0) * w
                total_w += w
                parts.append(f"{tf}:{sig.get('smc_bias', 'MIXED')} {sig.get('smc_confidence_score', 50):.0f}")
            net = weighted_net / max(total_w, 1e-9)
            smc_conf = float(np.clip(weighted_conf / max(total_w, 1e-9), 0, 100))
            bias = "BULLISH" if net >= 12 else "BEARISH" if net <= -12 else "MIXED"
            summary = " / ".join(parts[:4])
        buy_prob = _probability_score(str(row.get("buy_touch_probability", "")))
        sell_prob = _probability_score(str(row.get("sell_touch_probability", "")))
        stop_prob = _probability_score(str(row.get("tactical_stop_touch_probability", "")))
        order_type = str(row.get("suggested_order_type", ""))
        buy_intent = 1.0 if order_type in {"BUY_LIMIT", "ADD_LIMIT"} else 0.35 if order_type == "NO_ORDER_WAIT" else 0.15
        sell_intent = 1.0 if order_type in {"TAKE_PROFIT_LIMIT", "REBOUND_REDUCE_LIMIT", "REDUCE_OR_AVOID"} else 0.75 if order_type in {"PROTECTIVE_STOP", "PROTECT_PROFIT_STOP"} else 0.2
        bullish_alignment = 1.0 if bias == "BULLISH" else 0.55 if bias == "MIXED" else 0.15
        bearish_alignment = 1.0 if bias == "BEARISH" else 0.55 if bias == "MIXED" else 0.15
        buy_urgency = float(np.clip((buy_prob * 0.45 + smc_conf * 0.35 + max(net, 0) * 0.20) * buy_intent * bullish_alignment, 0, 100))
        sell_urgency = float(np.clip(((sell_prob * 0.40 + stop_prob * 0.20 + smc_conf * 0.25 + max(-net, 0) * 0.15) * sell_intent * bearish_alignment), 0, 100))
        if order_type in {"TAKE_PROFIT_LIMIT", "REBOUND_REDUCE_LIMIT"} and sell_prob >= 72:
            sell_urgency = max(sell_urgency, min(100.0, sell_prob * 0.7 + smc_conf * 0.2))
        if order_type in {"BUY_LIMIT", "ADD_LIMIT"} and buy_prob >= 72:
            buy_urgency = max(buy_urgency, min(100.0, buy_prob * 0.7 + smc_conf * 0.2))
        out.at[idx, "smc_confidence_score"] = smc_conf
        out.at[idx, "smc_bias"] = bias
        out.at[idx, "smc_timeframe_summary"] = summary
        out.at[idx, "buy_urgency_score"] = buy_urgency
        out.at[idx, "sell_urgency_score"] = sell_urgency
        out.at[idx, "priority_score"] = max(buy_urgency, sell_urgency)
    return out.reindex(columns=[c for c in _ORDER_COLUMNS if c in out.columns])


def build_next_day_order_plan(
    prices: pd.DataFrame,
    decision_report: pd.DataFrame,
    holdings: pd.DataFrame | None = None,
    *,
    lookback: int = 20,
) -> pd.DataFrame:
    """Create a next-day order plan with reachable limit/stop levels.

    The result is research guidance only. It does not place broker orders.  The
    levels are deliberately closer to the latest close than the strategic
    suggested_buy/sell/stop levels, because the goal is next-day order planning.
    """
    if prices.empty or "ticker" not in prices.columns:
        return pd.DataFrame(columns=_ORDER_COLUMNS)
    holdings = holdings.copy() if holdings is not None and not holdings.empty else pd.DataFrame(columns=["ticker"])
    report = decision_report.copy() if decision_report is not None and not decision_report.empty else pd.DataFrame(columns=["ticker"])

    tickers = sorted(set(prices["ticker"].dropna().astype(str).str.upper()))
    if not holdings.empty and "ticker" in holdings.columns:
        tickers = [ticker for ticker in tickers if ticker in set(holdings["ticker"].dropna().astype(str).str.upper())] or tickers

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        one = prices[prices["ticker"].astype(str).str.upper() == ticker]
        stats = _price_history_stats(one, lookback=lookback)
        current = stats["current_price"]
        if not np.isfinite(current) or current <= 0:
            continue
        decision = report[report["ticker"].astype(str).str.upper() == ticker].tail(1) if "ticker" in report.columns else pd.DataFrame()
        drow = decision.iloc[0] if not decision.empty else pd.Series(dtype=object)
        holding = holdings[holdings["ticker"].astype(str).str.upper() == ticker].tail(1) if not holdings.empty and "ticker" in holdings.columns else pd.DataFrame()
        hrow = holding.iloc[0] if not holding.empty else pd.Series(dtype=object)

        median_range = max(_as_float(stats["median_intraday_range_pct"], 2.0), 0.5)
        p80_range = max(_as_float(stats["p80_intraday_range_pct"], median_range * 1.35), median_range)
        buy_high = current * (1 - median_range * 0.35 / 100)
        buy_low = current * (1 - median_range * 0.65 / 100)
        sell_low = current * (1 + median_range * 0.35 / 100)
        sell_high = current * (1 + median_range * 0.65 / 100)
        previous_low = _as_float(stats["previous_low"], np.nan)
        tactical_by_range = current * (1 - median_range * 0.70 / 100)
        valid_previous_low = previous_low if np.isfinite(previous_low) and previous_low < current else np.nan
        tactical_stop = max(valid_previous_low, tactical_by_range) if np.isfinite(valid_previous_low) else tactical_by_range

        strategy_buy = _as_float(drow.get("suggested_buy_price"), buy_low)
        strategy_sell = _as_float(drow.get("suggested_sell_price"), sell_high)
        hard_stop = _as_float(drow.get("stop_loss_price"), current * (1 - p80_range / 100))
        if np.isfinite(hard_stop) and hard_stop >= current:
            hard_stop = current * (1 - max(median_range, 0.5) / 100)
        if np.isfinite(strategy_buy):
            buy_low = max(buy_low, min(strategy_buy, buy_high)) if strategy_buy < current else buy_low
        if np.isfinite(strategy_sell):
            sell_high = min(sell_high, max(strategy_sell, sell_low)) if strategy_sell > current else sell_high
        if np.isfinite(hard_stop):
            tactical_stop = max(tactical_stop, hard_stop)

        buy_distance = abs((current - buy_high) / current * 100)
        sell_distance = abs((sell_low - current) / current * 100)
        stop_distance = abs((current - tactical_stop) / current * 100)
        buy_prob = estimate_touch_probability_label(buy_distance, median_range, p80_range)
        sell_prob = estimate_touch_probability_label(sell_distance, median_range, p80_range)
        stop_prob = estimate_touch_probability_label(stop_distance, median_range, p80_range)
        action = str(drow.get("action", "HOLD_WAIT") or "HOLD_WAIT")
        kelly = _as_float(drow.get("kelly_fraction"), 0.0)
        adjusted = _as_float(drow.get("relationship_adjusted_return_pct"), _as_float(drow.get("expected_return_pct"), 0.0))
        quantity = _as_float(hrow.get("quantity"), 0.0)
        cost_price = _as_float(hrow.get("cost_price"), np.nan)
        unrealized_pnl_pct = (current / cost_price - 1) * 100 if np.isfinite(cost_price) and cost_price > 0 else np.nan
        order_type, base_reason = _order_type(action, quantity, kelly, adjusted, buy_prob, sell_prob, unrealized_pnl_pct)
        rows.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "current_price": current,
                "action": action,
                "composite_score": _as_float(drow.get("composite_score"), np.nan),
                "median_intraday_range_pct": median_range,
                "p80_intraday_range_pct": p80_range,
                "next_day_buy_low": float(min(buy_low, buy_high)),
                "next_day_buy_high": float(max(buy_low, buy_high)),
                "next_day_sell_low": float(min(sell_low, sell_high)),
                "next_day_sell_high": float(max(sell_low, sell_high)),
                "tactical_stop_price": float(tactical_stop),
                "hard_stop_price": float(hard_stop),
                "strategy_buy_price": float(strategy_buy),
                "strategy_take_profit_price": float(strategy_sell),
                "buy_touch_probability": buy_prob,
                "sell_touch_probability": sell_prob,
                "tactical_stop_touch_probability": stop_prob,
                "suggested_order_type": order_type,
                "suggested_action": base_reason,
                "reason": f"{base_reason} 隔日價位使用最近 {lookback} 日日內波動估算；研究輔助，不自動下單。",
            }
        )
    if not rows:
        return pd.DataFrame(columns=_ORDER_COLUMNS)
    order_rank = {
        "REDUCE_OR_AVOID": 0,
        "REBOUND_REDUCE_LIMIT": 1,
        "PROTECTIVE_STOP": 2,
        "PROTECT_PROFIT_STOP": 3,
        "TAKE_PROFIT_LIMIT": 4,
        "ADD_LIMIT": 5,
        "BUY_LIMIT": 6,
        "NO_ORDER_WAIT": 7,
    }
    out = pd.DataFrame(rows)
    out = augment_order_plan_with_smc(out, None)
    out["_rank"] = out["suggested_order_type"].map(order_rank).fillna(9)
    return out.sort_values(["_rank", "priority_score", "ticker"], ascending=[True, False, True]).drop(columns=["_rank"]).reset_index(drop=True)
