from __future__ import annotations

import pandas as pd

from ai_stock.order_planner import (
    augment_order_plan_with_smc,
    build_smc_timeframe_signals,
)


def _trend_prices(ticker: str = "AAPL", direction: float = 1.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=90, freq="D")
    rows = []
    close = 100.0
    for idx, date in enumerate(dates):
        close += direction * (0.22 + (idx % 7) * 0.015)
        rows.append(
            {
                "ticker": ticker,
                "date": date,
                "open": close - direction * 0.18,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + idx * 1200,
            }
        )
    return pd.DataFrame(rows)


def test_build_smc_timeframe_signals_outputs_multitimeframe_scores() -> None:
    frames = {
        "15m": _trend_prices("AAPL", 1.0),
        "1h": _trend_prices("AAPL", 0.5),
        "1d": _trend_prices("AAPL", -0.2),
    }

    signals = build_smc_timeframe_signals(frames)

    assert set(signals["timeframe"]) == {"15m", "1h", "1d"}
    assert {"ticker", "smc_confidence_score", "smc_bias", "smc_summary", "engine"}.issubset(signals.columns)
    assert signals["smc_confidence_score"].between(0, 100).all()
    assert signals["smc_bias"].isin({"BULLISH", "BEARISH", "MIXED"}).all()


def test_augment_order_plan_with_smc_adds_confidence_and_urgency_scores() -> None:
    plan = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "suggested_order_type": "ADD_LIMIT",
                "buy_touch_probability": "HIGH",
                "sell_touch_probability": "LOW_MEDIUM",
                "tactical_stop_touch_probability": "LOW_MEDIUM",
                "next_day_buy_low": 99.0,
                "next_day_buy_high": 100.0,
                "next_day_sell_low": 104.0,
                "next_day_sell_high": 105.0,
            },
            {
                "ticker": "TSLA",
                "suggested_order_type": "REBOUND_REDUCE_LIMIT",
                "buy_touch_probability": "LOW_MEDIUM",
                "sell_touch_probability": "HIGH",
                "tactical_stop_touch_probability": "MEDIUM",
                "next_day_buy_low": 190.0,
                "next_day_buy_high": 195.0,
                "next_day_sell_low": 210.0,
                "next_day_sell_high": 215.0,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"ticker": "AAPL", "timeframe": "15m", "smc_confidence_score": 80.0, "smc_bias": "BULLISH", "smc_summary": "15m bullish"},
            {"ticker": "AAPL", "timeframe": "1h", "smc_confidence_score": 72.0, "smc_bias": "BULLISH", "smc_summary": "1h bullish"},
            {"ticker": "TSLA", "timeframe": "15m", "smc_confidence_score": 78.0, "smc_bias": "BEARISH", "smc_summary": "15m bearish"},
            {"ticker": "TSLA", "timeframe": "1d", "smc_confidence_score": 66.0, "smc_bias": "BEARISH", "smc_summary": "1d bearish"},
        ]
    )

    out = augment_order_plan_with_smc(plan, signals)

    assert {"smc_confidence_score", "smc_bias", "smc_timeframe_summary", "buy_urgency_score", "sell_urgency_score", "priority_score"}.issubset(out.columns)
    aapl = out[out["ticker"] == "AAPL"].iloc[0]
    tsla = out[out["ticker"] == "TSLA"].iloc[0]
    assert aapl["buy_urgency_score"] > aapl["sell_urgency_score"]
    assert tsla["sell_urgency_score"] > tsla["buy_urgency_score"]
    assert out["priority_score"].between(0, 100).all()
