from __future__ import annotations

from pathlib import Path


def test_next_day_order_tab_has_extended_technical_visuals() -> None:
    app = Path("src/ai_stock/app.py").read_text(encoding="utf-8")

    assert "build_swing_order_technical_chart" in app
    assert "summarize_swing_order_technical_context" in app
    assert "隔日掛單技術圖" in app
    assert "on_select=\"rerun\"" in app
    assert "selected_order_ticker" in app
    assert "UKF 動能" in app
    assert "布林位置" in app
    assert "MACD Hist" in app
