from __future__ import annotations

import pandas as pd

from ai_stock.order_planner import integrate_strategy_recommendations_into_order_plan


def test_strategy_recommendations_override_final_order_ranges_and_priority() -> None:
    base_plan = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "current_price": 100.0,
                "next_day_buy_low": 98.0,
                "next_day_buy_high": 99.0,
                "next_day_sell_low": 101.0,
                "next_day_sell_high": 102.0,
                "tactical_stop_price": 96.0,
                "suggested_order_type": "PROTECTIVE_STOP",
                "buy_urgency_score": 10.0,
                "sell_urgency_score": 40.0,
                "priority_score": 40.0,
                "reason": "base reason",
            },
            {
                "ticker": "MSFT",
                "current_price": 200.0,
                "next_day_buy_low": 196.0,
                "next_day_buy_high": 198.0,
                "next_day_sell_low": 202.0,
                "next_day_sell_high": 204.0,
                "tactical_stop_price": 190.0,
                "suggested_order_type": "NO_ORDER_WAIT",
                "buy_urgency_score": 15.0,
                "sell_urgency_score": 12.0,
                "priority_score": 15.0,
                "reason": "base reason",
            },
        ]
    )
    strategy_orders = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "best_strategy": "smc",
                "best_strategy_label": "SMC 決策",
                "holding_days": 5,
                "risk_tolerance_pct": 10.0,
                "side": "BUY",
                "urgency_score": 88.0,
                "strategy_edge_score": 74.0,
                "buy_low": 97.2,
                "buy_high": 98.4,
                "sell_low": 103.0,
                "sell_high": 105.0,
                "stop_loss": 93.0,
                "take_profit": 103.0,
                "reason": "SMC strategy was historically stronger.",
            }
        ]
    )

    merged = integrate_strategy_recommendations_into_order_plan(base_plan, strategy_orders)

    aapl = merged[merged["ticker"] == "AAPL"].iloc[0]
    assert aapl["final_recommendation_source"] == "STRATEGY_WORKBENCH"
    assert aapl["final_side"] == "BUY"
    assert aapl["final_buy_low"] == 97.2
    assert aapl["final_buy_high"] == 98.4
    assert aapl["final_sell_low"] == 103.0
    assert aapl["final_sell_high"] == 105.0
    assert aapl["final_stop_loss"] == 93.0
    assert aapl["final_take_profit"] == 103.0
    assert aapl["final_strategy"] == "SMC 決策"
    assert aapl["final_strategy_edge_score"] == 74.0
    assert aapl["priority_score"] >= 88.0
    assert "SMC 決策" in aapl["final_reason"]

    msft = merged[merged["ticker"] == "MSFT"].iloc[0]
    assert msft["final_recommendation_source"] == "BASE_ORDER_PLAN"
    assert msft["final_buy_low"] == 196.0
    assert msft["final_sell_high"] == 204.0
    assert msft["final_strategy"] == ""
