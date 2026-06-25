from __future__ import annotations

import pandas as pd

from ai_stock.order_strategy_workbench import build_strategy_visualization_payload


def _prices(n: int = 80) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    rows = []
    close = 100.0
    for idx, date in enumerate(dates):
        close += 0.15 + ((idx % 9) - 4) * 0.08
        rows.append(
            {
                "ticker": "TEST",
                "date": date,
                "open": close - 0.4,
                "high": close + 1.2,
                "low": close - 1.1,
                "close": close,
                "volume": 1_000_000 + idx * 1000,
            }
        )
    return pd.DataFrame(rows)


def test_strategy_visualization_draws_vertical_trade_lines_and_pnl_connectors() -> None:
    prices = _prices()
    trades = pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "strategy": "bollinger",
                "entry_date": prices["date"].iloc[20],
                "exit_date": prices["date"].iloc[25],
                "entry_price": 100.0,
                "exit_price": 106.0,
                "return_pct": 0.06,
                "stop_hit": False,
                "signal": "BOLLINGER_DISCOUNT_BOUNCE",
                "direction": 1,
            },
            {
                "ticker": "TEST",
                "strategy": "bollinger",
                "entry_date": prices["date"].iloc[34],
                "exit_date": prices["date"].iloc[40],
                "entry_price": 108.0,
                "exit_price": 103.0,
                "return_pct": -0.0463,
                "stop_hit": True,
                "signal": "BOLLINGER_DISCOUNT_BOUNCE",
                "direction": 1,
            },
        ]
    )

    payload = build_strategy_visualization_payload(
        prices,
        trades,
        ticker="TEST",
        strategies=["bollinger"],
        show_smc=False,
    )

    fig = payload["figure"]
    shape_names = [shape.to_plotly_json().get("name", "") for shape in fig.layout.shapes]
    assert any("Trade Entry" in str(name) for name in shape_names)
    assert any("Trade Exit" in str(name) for name in shape_names)

    trace_names = {getattr(trace, "name", "") for trace in fig.data}
    assert "Trade PnL Win" in trace_names
    assert "Trade PnL Loss" in trace_names
    annotations = [getattr(annotation, "text", "") for annotation in fig.layout.annotations]
    assert any("+6.00%" in str(text) for text in annotations)
    assert any("-4.63%" in str(text) for text in annotations)
