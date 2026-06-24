from __future__ import annotations

import numpy as np
import pandas as pd

from ai_stock.trade_vision import (
    build_mtf_matrix,
    build_trade_narrative,
    build_trade_plan_from_decision,
    build_trade_vision_chart,
    build_trade_zones,
    compute_trade_signal_score,
    detect_market_structure,
)


def _sample_prices(ticker: str = "TEST", periods: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=periods, freq="D")
    base = 100 + np.linspace(0, 18, periods) + np.sin(np.linspace(0, 10, periods)) * 4
    close = pd.Series(base)
    open_ = close.shift(1).fillna(close.iloc[0] * 0.99) + np.sin(np.linspace(0, 8, periods)) * 0.4
    high = pd.concat([open_, close], axis=1).max(axis=1) + 1.5 + np.cos(np.linspace(0, 8, periods)) * 0.4
    low = pd.concat([open_, close], axis=1).min(axis=1) - 1.5 - np.sin(np.linspace(0, 8, periods)) * 0.3
    volume = 1_000_000 + np.arange(periods) * 1500
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": open_.to_numpy(),
            "high": high.to_numpy(),
            "low": low.to_numpy(),
            "close": close.to_numpy(),
            "volume": volume,
        }
    )


def _decision_row(ticker: str = "TEST") -> pd.Series:
    return pd.Series(
        {
            "ticker": ticker,
            "action": "BUY_WATCH",
            "last_close": 118.0,
            "suggested_buy_price": 116.0,
            "suggested_sell_price": 125.0,
            "stop_loss_price": 112.0,
            "expected_return_pct": 2.5,
            "relationship_adjusted_return_pct": 3.1,
            "kelly_fraction": 0.08,
            "action_reason": "測試決策原因",
            "kelly_reason": "測試 Kelly 原因",
        }
    )


def test_detect_market_structure_outputs_swings_breaks_and_levels():
    prices = _sample_prices()

    result = detect_market_structure(prices, swing_window=2, min_break_pct=0.001)

    assert set(result) == {"swings", "structure_events", "support_resistance"}
    assert {"date", "price", "type", "strength"}.issubset(result["swings"].columns)
    assert set(result["swings"]["type"]).issubset({"swing_high", "swing_low"})
    assert {"date", "price", "event_type", "reference_price", "description"}.issubset(result["structure_events"].columns)
    assert set(result["structure_events"]["event_type"]).issubset({"BOS_UP", "BOS_DOWN", "CHOCH_UP", "CHOCH_DOWN"})
    assert {"level", "type", "touches", "last_touch_date", "strength"}.issubset(result["support_resistance"].columns)


def test_build_trade_zones_outputs_core_zone_types():
    prices = _sample_prices()
    structure = detect_market_structure(prices, swing_window=2, min_break_pct=0.001)

    zones = build_trade_zones(prices, structure, lookback=60)

    assert {"zone_id", "zone_type", "start_date", "end_date", "y0", "y1", "strength", "label"}.issubset(zones.columns)
    assert {"premium", "discount", "equilibrium"}.issubset(set(zones["zone_type"]))
    assert zones["y1"].ge(zones["y0"]).all()


def test_trade_plan_from_decision_computes_tp_rr_and_status():
    row = _decision_row()

    plan = build_trade_plan_from_decision(row, current_price=117.0)

    assert plan["ticker"] == "TEST"
    assert plan["entry_price"] == 116.0
    assert plan["stop_loss_price"] == 112.0
    assert plan["take_profit_1"] == 125.0
    assert plan["take_profit_2"] == 124.0
    assert plan["take_profit_3"] == 128.0
    assert plan["rr_ratio"] > 1
    assert plan["plan_status"] in {"WAITING", "ACTIVE", "TP1_HIT", "TP2_HIT", "TP3_HIT", "SL_TRIGGERED", "INVALIDATED"}
    assert "研究輔助" in plan["explanation"]


def test_mtf_matrix_and_signal_score_are_bounded():
    prices = pd.concat([_sample_prices("AAA"), _sample_prices("BBB")], ignore_index=True)
    one = prices[prices["ticker"] == "AAA"]
    structure = detect_market_structure(one)
    mtf = build_mtf_matrix(prices, "AAA")
    snapshot_row = pd.Series({"rsi_14": 62, "macd_hist": 1.2, "volume_ratio_20d": 1.3, "atr_pct_14": 0.03, "distance_sma20": 0.02, "distance_sma60": 0.08})

    score = compute_trade_signal_score(snapshot_row, _decision_row("AAA"), structure["structure_events"], mtf)

    assert {"timeframe", "trend_state", "momentum_score", "volume_score", "volatility_score", "signal_strength", "description"}.issubset(mtf.columns)
    assert set(mtf["timeframe"]).issuperset({"1D", "1W", "1M"})
    assert 0 <= score["composite_score"] <= 100
    assert score["status"] in {"STRONG_BUY_WATCH", "BUY_WATCH", "HOLD_WAIT", "RISK_ALERT", "SELL_OR_AVOID"}


def test_trade_narrative_and_chart_include_required_visual_layers():
    prices = _sample_prices()
    decision = _decision_row()
    structure = detect_market_structure(prices, swing_window=2, min_break_pct=0.001)
    zones = build_trade_zones(prices, structure, lookback=60)
    mtf = build_mtf_matrix(prices, "TEST")
    plan = build_trade_plan_from_decision(decision, current_price=float(prices["close"].iloc[-1]))
    score = compute_trade_signal_score(pd.Series({"rsi_14": 60, "macd_hist": 0.5, "volume_ratio_20d": 1.1}), decision, structure["structure_events"], mtf)

    narrative = build_trade_narrative("TEST", plan, score, mtf, structure["structure_events"], zones)
    fig = build_trade_vision_chart(
        prices,
        "TEST",
        decision_row=decision,
        structure=structure["structure_events"],
        zones=zones,
        signal_events=structure["swings"],
        show_volume=True,
        show_structure=True,
        show_zones=True,
        show_trade_plan=True,
    )

    assert 3 <= len(narrative) <= 6
    assert all(isinstance(item, str) and item for item in narrative)
    trace_names = {trace.name for trace in fig.data if getattr(trace, "name", None)}
    assert "Candlestick" in trace_names
    assert "SMA20" in trace_names
    assert "SMA60" in trace_names
    assert "Volume" in trace_names
    assert "Entry" in trace_names
    assert "Stop Loss" in trace_names
    assert "Take Profit" in trace_names
    assert any("BOS" in str(name) or "CHOCH" in str(name) for name in trace_names)
    assert fig.layout.shapes and len(fig.layout.shapes) >= 3
