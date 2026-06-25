from __future__ import annotations

import numpy as np
import pandas as pd

from ai_stock.order_strategy_workbench import build_order_strategy_workbench, build_strategy_visualization_payload


def _oscillating_prices(ticker: str = "TEST", n: int = 140) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    base = 100 + np.sin(np.arange(n) / 2.0) * 4 + np.linspace(0, 8, n)
    close = base + np.sin(np.arange(n)) * 1.2
    open_ = close + np.cos(np.arange(n)) * 0.8
    high = np.maximum(open_, close) + 1.3
    low = np.minimum(open_, close) - 1.3
    volume = np.linspace(1_000_000, 1_400_000, n)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_strategy_backtest_does_not_open_new_trade_on_prior_exit_date() -> None:
    prices = _oscillating_prices()
    next_day_plan = pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "current_price": float(prices["close"].iloc[-1]),
                "next_day_buy_low": 98.0,
                "next_day_buy_high": 99.0,
                "next_day_sell_low": 105.0,
                "next_day_sell_high": 106.0,
                "tactical_stop_price": 94.0,
                "buy_urgency_score": 55.0,
                "sell_urgency_score": 45.0,
            }
        ]
    )
    result = build_order_strategy_workbench(
        prices,
        next_day_plan,
        selected_tickers=["TEST"],
        strategies=["kd_macd"],
        holding_days=1,
        risk_tolerance_pct=10,
        backtest_range="1年",
    )
    trades = result["trades"]
    assert not trades.empty
    trade_dates = pd.to_datetime(pd.concat([trades["entry_date"], trades["exit_date"]]))
    assert trade_dates.duplicated().sum() == 0
    assert "direction" in trades.columns


def test_strategy_markers_respect_trade_direction() -> None:
    prices = _oscillating_prices()
    trades = pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "strategy": "kd_macd",
                "entry_date": prices["date"].iloc[20],
                "exit_date": prices["date"].iloc[25],
                "entry_price": 100.0,
                "exit_price": 95.0,
                "return_pct": 0.05,
                "stop_hit": False,
                "signal": "KD_MACD_BEARISH",
                "direction": -1,
            }
        ]
    )
    payload = build_strategy_visualization_payload(prices, trades, ticker="TEST", strategies=["kd_macd"], show_smc=False)
    markers = payload["trade_markers"]
    assert list(markers["side"]) == ["SELL", "BUY_TO_COVER"]
