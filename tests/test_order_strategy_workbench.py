from __future__ import annotations

import pandas as pd

from ai_stock.order_strategy_workbench import (
    ORDER_STRATEGIES,
    build_order_strategy_workbench,
    filter_backtest_window,
)


def _prices(tickers=("AAPL", "TSLA"), periods: int = 180) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=periods, freq="D")
    rows = []
    for ticker in tickers:
        close = 100.0 if ticker == "AAPL" else 180.0
        for idx, date in enumerate(dates):
            wave = ((idx % 18) - 9) * 0.12
            drift = 0.18 if ticker == "AAPL" else -0.04
            close = max(5.0, close + drift + wave)
            rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "open": close - 0.4,
                    "high": close + 1.8 + (idx % 5) * 0.05,
                    "low": close - 1.6 - (idx % 4) * 0.04,
                    "close": close,
                    "volume": 1_000_000 + idx * 2500 + (50_000 if ticker == "TSLA" else 0),
                }
            )
    return pd.DataFrame(rows)


def test_filter_backtest_window_supports_named_ranges() -> None:
    prices = _prices(periods=260)

    one_month = filter_backtest_window(prices, "1個月")
    one_year = filter_backtest_window(prices, "1年")

    assert 20 <= one_month["date"].nunique() <= 35
    assert one_year["date"].nunique() == prices["date"].nunique()


def test_order_strategy_workbench_outputs_strategy_metrics_and_order_levels() -> None:
    prices = _prices()
    plan = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "current_price": 130.0,
                "next_day_buy_low": 127.0,
                "next_day_buy_high": 128.5,
                "next_day_sell_low": 132.0,
                "next_day_sell_high": 134.0,
                "tactical_stop_price": 123.0,
                "hard_stop_price": 118.0,
                "suggested_order_type": "ADD_LIMIT",
                "smc_confidence_score": 72.0,
                "smc_bias": "BULLISH",
                "buy_urgency_score": 66.0,
                "sell_urgency_score": 18.0,
            },
            {
                "ticker": "TSLA",
                "current_price": 170.0,
                "next_day_buy_low": 164.0,
                "next_day_buy_high": 166.0,
                "next_day_sell_low": 173.0,
                "next_day_sell_high": 177.0,
                "tactical_stop_price": 162.0,
                "hard_stop_price": 155.0,
                "suggested_order_type": "PROTECTIVE_STOP",
                "smc_confidence_score": 69.0,
                "smc_bias": "BEARISH",
                "buy_urgency_score": 12.0,
                "sell_urgency_score": 71.0,
            },
        ]
    )

    result = build_order_strategy_workbench(
        prices,
        plan,
        selected_tickers=["AAPL"],
        strategies=["bollinger", "smc", "ukf", "kd_macd", "shap_factor"],
        holding_days=5,
        risk_tolerance_pct=10.0,
        backtest_range="3個月",
    )

    assert {"summary", "trades", "order_recommendations", "strategy_scores"}.issubset(result)
    summary = result["summary"]
    orders = result["order_recommendations"]
    assert not summary.empty
    assert set(summary["ticker"]) == {"AAPL"}
    assert set(summary["strategy"]).issubset(set(ORDER_STRATEGIES))
    assert {"win_rate", "trade_count", "avg_return_pct", "strategy_edge_score"}.issubset(summary.columns)
    assert summary["strategy_edge_score"].between(0, 100).all()
    assert not orders.empty
    assert {"buy_low", "buy_high", "sell_low", "sell_high", "stop_loss", "urgency_score", "side", "best_strategy"}.issubset(orders.columns)
    assert orders["urgency_score"].between(0, 100).all()


def test_order_strategy_workbench_can_run_all_tickers_and_disable_strategies() -> None:
    prices = _prices()
    plan = pd.DataFrame(
        [
            {"ticker": "AAPL", "current_price": 130.0, "next_day_buy_low": 127.0, "next_day_buy_high": 128.5, "next_day_sell_low": 132.0, "next_day_sell_high": 134.0, "tactical_stop_price": 123.0, "suggested_order_type": "ADD_LIMIT"},
            {"ticker": "TSLA", "current_price": 170.0, "next_day_buy_low": 164.0, "next_day_buy_high": 166.0, "next_day_sell_low": 173.0, "next_day_sell_high": 177.0, "tactical_stop_price": 162.0, "suggested_order_type": "PROTECTIVE_STOP"},
        ]
    )

    result = build_order_strategy_workbench(
        prices,
        plan,
        selected_tickers="ALL",
        strategies=["bollinger", "kd_macd"],
        holding_days=10,
        risk_tolerance_pct=8.0,
        backtest_range="半年",
    )

    summary = result["summary"]
    assert set(summary["ticker"]) == {"AAPL", "TSLA"}
    assert set(summary["strategy"]) == {"bollinger", "kd_macd"}
    assert result["order_recommendations"]["risk_tolerance_pct"].eq(8.0).all()
