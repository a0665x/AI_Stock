from __future__ import annotations

import pandas as pd

from ai_stock.order_planner import build_next_day_order_plan, estimate_touch_probability_label


def _prices(ticker: str = "AAPL") -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    rows = []
    close = 100.0
    for idx, date in enumerate(dates):
        close += 0.35
        rows.append(
            {
                "ticker": ticker,
                "date": date,
                "open": close - 0.4,
                "high": close + 1.5 + idx * 0.01,
                "low": close - 1.2,
                "close": close,
                "volume": 1_000_000 + idx * 1000,
            }
        )
    return pd.DataFrame(rows)


def test_estimate_touch_probability_label_uses_recent_intraday_range() -> None:
    assert estimate_touch_probability_label(distance_pct=0.4, median_range_pct=2.0, p80_range_pct=3.0) == "HIGH"
    assert estimate_touch_probability_label(distance_pct=1.1, median_range_pct=2.0, p80_range_pct=3.0) == "MEDIUM"
    assert estimate_touch_probability_label(distance_pct=2.8, median_range_pct=2.0, p80_range_pct=3.0) == "LOW_MEDIUM"
    assert estimate_touch_probability_label(distance_pct=5.0, median_range_pct=2.0, p80_range_pct=3.0) == "LOW_STRATEGY_LEVEL"


def test_build_next_day_order_plan_outputs_reachable_prices_and_order_type() -> None:
    prices = _prices()
    holdings = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "quantity": 10,
                "broker_current_price": 110.0,
                "cost_price": 95.0,
                "market_value": 1100.0,
            }
        ]
    )
    decision_report = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "action": "BUY_WATCH",
                "last_close": 110.5,
                "suggested_buy_price": 96.0,
                "suggested_sell_price": 125.0,
                "stop_loss_price": 90.0,
                "relationship_adjusted_return_pct": 3.5,
                "expected_return_pct": 2.0,
                "kelly_fraction": 0.12,
                "action_reason": "偏多但策略買價較遠。",
            }
        ]
    )

    plan = build_next_day_order_plan(prices, decision_report, holdings)

    assert len(plan) == 1
    row = plan.iloc[0]
    assert row["ticker"] == "AAPL"
    assert row["next_day_buy_low"] < row["current_price"]
    assert row["next_day_buy_high"] < row["current_price"]
    assert row["next_day_buy_low"] > row["strategy_buy_price"]
    assert row["next_day_sell_low"] > row["current_price"]
    assert row["tactical_stop_price"] < row["current_price"]
    assert row["hard_stop_price"] < row["current_price"]
    assert row["tactical_stop_price"] > row["hard_stop_price"]
    assert row["buy_touch_probability"] in {"HIGH", "MEDIUM", "LOW_MEDIUM", "LOW_STRATEGY_LEVEL"}
    assert row["suggested_order_type"] in {"BUY_LIMIT", "ADD_LIMIT", "BRACKET_PLAN", "PROTECTIVE_STOP", "PROTECT_PROFIT_STOP", "REBOUND_REDUCE_LIMIT", "NO_ORDER_WAIT", "TAKE_PROFIT_LIMIT", "REDUCE_OR_AVOID"}
    assert "研究輔助" in row["reason"]


def test_losing_position_with_positive_short_term_return_is_rebound_reduce_not_take_profit() -> None:
    prices = _prices("TSLR")
    holdings = pd.DataFrame(
        [
            {
                "ticker": "TSLR",
                "quantity": 30,
                "cost_price": 130.0,
                "broker_current_price": 110.0,
                "market_value": 3300.0,
            }
        ]
    )
    decision_report = pd.DataFrame(
        [
            {
                "ticker": "TSLR",
                "action": "HOLD_WAIT",
                "suggested_buy_price": 100.0,
                "suggested_sell_price": 150.0,
                "stop_loss_price": 90.0,
                "relationship_adjusted_return_pct": 1.2,
                "kelly_fraction": 0.0,
            }
        ]
    )

    plan = build_next_day_order_plan(prices, decision_report, holdings)

    assert plan.iloc[0]["suggested_order_type"] == "REBOUND_REDUCE_LIMIT"
    assert "不應稱為停利" in plan.iloc[0]["reason"]


def test_profitable_position_without_edge_uses_profit_protective_stop() -> None:
    prices = _prices("AAPL")
    holdings = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "quantity": 10,
                "cost_price": 80.0,
                "broker_current_price": 110.0,
                "market_value": 1100.0,
            }
        ]
    )
    decision_report = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "action": "HOLD_WAIT",
                "suggested_buy_price": 96.0,
                "suggested_sell_price": 125.0,
                "stop_loss_price": 90.0,
                "relationship_adjusted_return_pct": -0.5,
                "kelly_fraction": 0.0,
            }
        ]
    )

    plan = build_next_day_order_plan(prices, decision_report, holdings)

    assert plan.iloc[0]["suggested_order_type"] == "PROTECT_PROFIT_STOP"
    assert "保護獲利" in plan.iloc[0]["reason"]


def test_build_next_day_order_plan_handles_empty_inputs() -> None:
    plan = build_next_day_order_plan(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert plan.empty
    assert {"ticker", "suggested_order_type", "buy_touch_probability", "sell_touch_probability"}.issubset(plan.columns)
