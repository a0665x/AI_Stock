from __future__ import annotations

import pandas as pd

from ai_stock.order_strategy_workbench import build_order_strategy_workbench, build_strategy_visualization_payload


def _prices(periods: int = 180) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=periods, freq="D")
    rows = []
    close = 100.0
    for idx, date in enumerate(dates):
        close = max(5.0, close + 0.08 + ((idx % 14) - 7) * 0.10)
        rows.append(
            {
                "ticker": "AAPL",
                "date": date,
                "open": close - 0.5,
                "high": close + 1.4 + (idx % 4) * 0.08,
                "low": close - 1.2 - (idx % 3) * 0.06,
                "close": close,
                "volume": 1_000_000 + idx * 3000,
            }
        )
    return pd.DataFrame(rows)


def _plan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "current_price": 112.0,
                "next_day_buy_low": 109.0,
                "next_day_buy_high": 110.5,
                "next_day_sell_low": 114.0,
                "next_day_sell_high": 116.0,
                "tactical_stop_price": 105.0,
                "hard_stop_price": 101.0,
                "suggested_order_type": "ADD_LIMIT",
                "smc_confidence_score": 72.0,
                "smc_bias": "BULLISH",
                "buy_urgency_score": 66.0,
                "sell_urgency_score": 18.0,
            }
        ]
    )


def test_strategy_visualization_payload_contains_price_signals_equity_and_drawdown() -> None:
    prices = _prices()
    result = build_order_strategy_workbench(
        prices,
        _plan(),
        selected_tickers=["AAPL"],
        strategies=["bollinger", "kd_macd"],
        holding_days=5,
        risk_tolerance_pct=10.0,
        backtest_range="半年",
    )

    payload = build_strategy_visualization_payload(
        prices,
        result["trades"],
        ticker="AAPL",
        strategies=["bollinger", "kd_macd", "COMPOSITE"],
        order_recommendations=result["order_recommendations"],
        show_smc=True,
    )

    assert {"figure", "equity_curve", "drawdown_curve", "trade_markers", "strategy_metrics"}.issubset(payload)
    fig = payload["figure"]
    trace_names = {getattr(trace, "name", "") for trace in fig.data}
    assert "K線" in trace_names
    assert "Bollinger Upper" in trace_names
    assert "RSI14" in trace_names
    assert "MACD Hist" in trace_names
    assert "Strategy Buy Entry" in trace_names
    assert "Strategy Sell / Short Entry" in trace_names
    assert "Equity Curve" in trace_names
    assert "Drawdown" in trace_names
    assert any("SMC" in str(name) for name in trace_names)
    assert not payload["equity_curve"].empty
    assert not payload["drawdown_curve"].empty
    assert set(payload["strategy_metrics"]["strategy"]).issubset({"bollinger", "kd_macd", "COMPOSITE"})
    assert payload["strategy_metrics"]["max_drawdown_pct"].le(0).all()


def test_strategy_visualization_payload_handles_empty_trades_without_crashing() -> None:
    payload = build_strategy_visualization_payload(
        _prices(60),
        pd.DataFrame(),
        ticker="AAPL",
        strategies=["bollinger"],
        order_recommendations=pd.DataFrame(),
        show_smc=False,
    )

    assert payload["figure"] is not None
    assert payload["trade_markers"].empty
    assert payload["strategy_metrics"].empty
