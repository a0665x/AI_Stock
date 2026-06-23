from __future__ import annotations

import pandas as pd

from ai_stock.visual_insights import (
    build_market_heatmap_table,
    build_smart_tuning_lite,
    build_watchlist_sparklines,
)


def _prices() -> pd.DataFrame:
    rows = []
    for ticker, drift, amp in [("AAA", 0.35, 1.2), ("BBB", -0.12, 0.8), ("CCC", 0.08, 2.0)]:
        for i, date in enumerate(pd.date_range("2024-01-01", periods=180, freq="D")):
            wave = ((i % 9) - 4) * amp * 0.08
            close = 50 + i * drift + wave + (10 if ticker == "CCC" else 0)
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "open": close - 0.2,
                    "high": close + 0.8,
                    "low": close - 0.8,
                    "close": close,
                    "volume": 1000 + i * 4 + (500 if ticker == "CCC" else 0),
                }
            )
    return pd.DataFrame(rows)


def _decision() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ticker": "AAA", "action": "BUY_WATCH", "relationship_adjusted_return_pct": 3.5, "kelly_fraction": 0.08},
            {"ticker": "BBB", "action": "SELL_OR_AVOID", "relationship_adjusted_return_pct": -2.1, "kelly_fraction": 0.0},
            {"ticker": "CCC", "action": "HOLD_WAIT", "relationship_adjusted_return_pct": 0.4, "kelly_fraction": 0.0},
        ]
    )


def test_watchlist_sparklines_include_latest_change_and_recent_series():
    watchlist = build_watchlist_sparklines(_prices(), _decision(), lookback=20)

    assert set(watchlist["ticker"]) == {"AAA", "BBB", "CCC"}
    assert {"last_close", "change_1d_pct", "change_5d_pct", "sparkline", "action", "tone"}.issubset(watchlist.columns)
    assert all(isinstance(values, list) and len(values) <= 20 for values in watchlist["sparkline"])
    assert watchlist.loc[watchlist["ticker"] == "AAA", "tone"].iloc[0] == "bullish"


def test_market_heatmap_table_scores_each_ticker_for_treemap_display():
    heatmap = build_market_heatmap_table(_prices(), _decision())

    assert set(heatmap["ticker"]) == {"AAA", "BBB", "CCC"}
    assert {"size", "color_value", "return_1d_pct", "return_5d_pct", "signal_score", "label"}.issubset(heatmap.columns)
    assert (heatmap["size"] > 0).all()
    assert heatmap.loc[heatmap["ticker"] == "AAA", "signal_score"].iloc[0] > heatmap.loc[heatmap["ticker"] == "BBB", "signal_score"].iloc[0]


def test_smart_tuning_lite_compares_holding_days_stop_and_exit_rules():
    result = build_smart_tuning_lite(
        _prices(),
        horizons=(3, 5),
        exit_rules=("time", "stop_loss"),
        stop_loss_pcts=(0.03, 0.05),
        lookback=70,
        trailing_stop_pct=0.05,
    )

    assert not result.empty
    assert {"ticker", "holding_days", "exit_rule", "stop_loss_pct", "score", "rank", "win_rate", "max_drawdown", "cumulative_return", "profit_factor"}.issubset(result.columns)
    assert result["rank"].min() == 1
    best = result.sort_values("rank").iloc[0]
    assert best["score"] >= result["score"].median()
