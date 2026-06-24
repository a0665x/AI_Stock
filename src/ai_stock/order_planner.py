from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

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
    "suggested_order_type",
    "suggested_action",
    "reason",
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


def _order_type(action: str, quantity: float, kelly: float, adjusted_return: float, buy_probability: str, sell_probability: str) -> tuple[str, str]:
    has_position = np.isfinite(quantity) and quantity > 0
    if action == "SELL_OR_AVOID":
        return "REDUCE_OR_AVOID", "模型與風險報酬偏弱；已有持倉時優先檢查減碼或保護停損。"
    if has_position and adjusted_return > 0 and sell_probability in {"HIGH", "MEDIUM"}:
        return "TAKE_PROFIT_LIMIT", "已有持倉且隔日賣出區較可觸及，可用分批停利限價單觀察。"
    if action == "BUY_WATCH" and kelly > 0 and buy_probability in {"HIGH", "MEDIUM", "LOW_MEDIUM"}:
        return ("ADD_LIMIT" if has_position else "BUY_LIMIT"), "偏多且隔日回踩區具有可觸及性，可用限價單小倉位觀察。"
    if has_position:
        return "PROTECTIVE_STOP", "訊號尚未足以加碼；先用戰術停損與硬停損保護持倉。"
    return "NO_ORDER_WAIT", "沒有持倉且優勢不足；等待價格進入更好的回踩區或訊號轉強。"


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
        order_type, base_reason = _order_type(action, quantity, kelly, adjusted, buy_prob, sell_prob)
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
    order_rank = {"REDUCE_OR_AVOID": 0, "PROTECTIVE_STOP": 1, "TAKE_PROFIT_LIMIT": 2, "ADD_LIMIT": 3, "BUY_LIMIT": 4, "NO_ORDER_WAIT": 5}
    out = pd.DataFrame(rows)
    out["_rank"] = out["suggested_order_type"].map(order_rank).fillna(9)
    return out.sort_values(["_rank", "ticker"]).drop(columns=["_rank"]).reset_index(drop=True)
