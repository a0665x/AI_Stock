from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ai_stock.portfolio import build_portfolio_order_plan, load_local_portfolio, load_portfolio_json, portfolio_tickers, summarize_portfolio


def test_load_portfolio_json_and_tickers(tmp_path: Path) -> None:
    payload = {
        "source": {"account": "demo"},
        "holdings": [
            {"name_zh": "蘋果", "ticker": "aapl", "quantity": 2, "current_price": 100, "cost_price": 80, "today_pnl": 3},
            {"name_zh": "特斯拉", "ticker": "TSLA", "market_value": 50, "quantity": 1, "current_price": 50, "cost_price": 60},
        ],
    }
    path = tmp_path / "my_stocks.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_portfolio_json(path)

    assert loaded.account_label == "demo"
    assert list(loaded.holdings["ticker"]) == ["AAPL", "TSLA"]
    assert loaded.holdings.loc[loaded.holdings["ticker"] == "AAPL", "market_value"].iloc[0] == 200
    assert portfolio_tickers(loaded.holdings) == ("AAPL", "TSLA")


def test_load_local_portfolio_supports_typo_compat_file(tmp_path: Path) -> None:
    (tmp_path / "my_sotcks.json").write_text(json.dumps({"holdings": [{"ticker": "NVDA", "quantity": 1}]}), encoding="utf-8")

    loaded = load_local_portfolio(tmp_path)

    assert loaded.source_path and loaded.source_path.endswith("my_sotcks.json")
    assert portfolio_tickers(loaded.holdings) == ("NVDA",)


def test_build_portfolio_order_plan_merges_decision_levels() -> None:
    holdings = pd.DataFrame(
        [
            {"ticker": "AAPL", "name_zh": "蘋果", "quantity": 10, "broker_current_price": 100, "cost_price": 80, "market_value": 1000, "today_pnl": -10},
            {"ticker": "TSLA", "name_zh": "特斯拉", "quantity": 2, "broker_current_price": 45, "cost_price": 60, "market_value": 90, "today_pnl": -5},
        ]
    )
    report = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "action": "HOLD_WAIT",
                "last_close": 101,
                "relationship_adjusted_return_pct": 0.4,
                "kelly_fraction": 0.0,
                "suggested_buy_price": 95,
                "suggested_sell_price": 115,
                "stop_loss_price": 90,
                "risk_unit_pct": 4,
                "max_drawdown_60d_pct": -8,
            },
            {
                "ticker": "TSLA",
                "action": "SELL_OR_AVOID",
                "last_close": 44,
                "relationship_adjusted_return_pct": -7.5,
                "kelly_fraction": 0.0,
                "suggested_buy_price": 40,
                "suggested_sell_price": 55,
                "stop_loss_price": 46,
                "risk_unit_pct": 9,
                "max_drawdown_60d_pct": -20,
            },
        ]
    )

    plan = build_portfolio_order_plan(holdings, report)

    assert {"stop_loss_order_price", "take_profit_order_price", "add_buy_limit_price", "suggested_order_action", "order_note"}.issubset(plan.columns)
    assert plan.loc[plan["ticker"] == "AAPL", "stop_loss_order_price"].iloc[0] == 90
    assert plan.loc[plan["ticker"] == "AAPL", "take_profit_order_price"].iloc[0] == 115
    assert plan.loc[plan["ticker"] == "TSLA", "suggested_order_action"].iloc[0] == "REDUCE_OR_EXIT"
    assert plan.loc[plan["ticker"] == "AAPL", "portfolio_weight_pct"].iloc[0] > 90


def test_summarize_portfolio_counts_alerts() -> None:
    holdings = pd.DataFrame([{"ticker": "AAPL", "market_value": 100, "today_pnl": -1}, {"ticker": "TSLA", "market_value": 50, "today_pnl": 2}])
    plan = pd.DataFrame([{"suggested_order_action": "STOP_LOSS_ALERT"}, {"suggested_order_action": "TAKE_PROFIT_ALERT"}])

    summary = summarize_portfolio(holdings, plan)

    assert summary["positions"] == 2
    assert summary["total_market_value"] == 150
    assert summary["stop_alerts"] == 1
    assert summary["take_profit_alerts"] == 1
