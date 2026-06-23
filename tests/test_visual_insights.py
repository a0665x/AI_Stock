from __future__ import annotations

import pandas as pd

from ai_stock.visual_insights import (
    build_decision_price_chart,
    build_opportunity_radar,
    build_strategy_health_cards,
)


def test_opportunity_radar_summarizes_decision_and_backtest_context():
    decision = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "action": "BUY_WATCH",
                "relationship_adjusted_return_pct": 4.2,
                "expected_return_pct": 3.8,
                "kelly_fraction": 0.12,
                "suggested_buy_price": 98.0,
                "suggested_sell_price": 112.0,
                "stop_loss_price": 94.0,
                "action_reason": "偏多觀察：預估報酬高於門檻。",
            },
            {
                "ticker": "BBB",
                "action": "HOLD_WAIT",
                "relationship_adjusted_return_pct": 0.3,
                "expected_return_pct": 0.2,
                "kelly_fraction": 0.0,
                "suggested_buy_price": 40.0,
                "suggested_sell_price": 44.0,
                "stop_loss_price": 38.0,
                "action_reason": "等待確認：預估報酬仍在門檻內。",
            },
        ]
    )
    backtest = pd.DataFrame(
        [
            {"ticker": "AAA", "win_rate": 0.62, "cumulative_return": 0.18, "max_drawdown": -0.07, "profit_factor": 1.8, "trades": 21},
            {"ticker": "BBB", "win_rate": 0.44, "cumulative_return": -0.02, "max_drawdown": -0.15, "profit_factor": 0.8, "trades": 18},
        ]
    )

    radar = build_opportunity_radar(decision, backtest, top_n=2)

    assert list(radar["ticker"]) == ["AAA", "BBB"]
    assert radar.loc[0, "tone"] == "bullish"
    assert radar.loc[0, "win_rate_pct"] == 62.0
    assert radar.loc[0, "kelly_pct"] == 12.0
    assert "偏多觀察" in radar.loc[0, "reason"]


def test_strategy_health_cards_flag_sample_risk_drawdown_and_weak_profit_factor():
    backtest = pd.DataFrame(
        [
            {"ticker": "AAA", "trades": 4, "win_rate": 0.75, "cumulative_return": 0.04, "max_drawdown": -0.03, "profit_factor": 1.4},
            {"ticker": "BBB", "trades": 30, "win_rate": 0.42, "cumulative_return": -0.08, "max_drawdown": -0.22, "profit_factor": 0.7},
        ]
    )
    decision = pd.DataFrame(
        [
            {"ticker": "AAA", "kelly_fraction": 0.0, "action": "HOLD_WAIT"},
            {"ticker": "BBB", "kelly_fraction": 0.0, "action": "SELL_OR_AVOID"},
        ]
    )

    cards = build_strategy_health_cards(backtest, decision)

    messages = "\n".join(cards["message"].astype(str))
    assert "樣本數不足" in messages
    assert "最大回撤偏高" in messages
    assert "Profit Factor 低於 1" in messages
    assert set(cards["severity"]).issubset({"ok", "info", "warning", "danger"})


def test_decision_price_chart_adds_decision_lines_and_backtest_markers():
    prices = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=80, freq="D"),
            "ticker": ["AAA"] * 80,
            "open": [100 + i * 0.1 for i in range(80)],
            "high": [101 + i * 0.1 for i in range(80)],
            "low": [99 + i * 0.1 for i in range(80)],
            "close": [100 + i * 0.1 for i in range(80)],
            "volume": [1000 + i for i in range(80)],
        }
    )
    decision_row = pd.Series({"suggested_buy_price": 101.0, "suggested_sell_price": 112.0, "stop_loss_price": 95.0})
    trades = pd.DataFrame(
        [
            {"ticker": "AAA", "entry_date": pd.Timestamp("2024-02-01"), "entry_price": 103.0, "exit_date": pd.Timestamp("2024-02-06"), "exit_price": 106.0, "return_pct": 0.03},
            {"ticker": "AAA", "entry_date": pd.Timestamp("2024-03-01"), "entry_price": 105.0, "exit_date": pd.Timestamp("2024-03-05"), "exit_price": 99.0, "return_pct": -0.057},
        ]
    )

    fig = build_decision_price_chart(prices, "AAA", show_volume=True, decision_row=decision_row, backtest_trades=trades)

    names = [trace.name for trace in fig.data]
    assert "參考買進" in names
    assert "參考賣出" in names
    assert "參考停損" in names
    assert "回測進場 B" in names
    assert "回測出場 S" in names
