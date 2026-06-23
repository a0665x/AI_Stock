from __future__ import annotations

from pathlib import Path


def test_phase2_streamlit_ui_exposes_watchlist_heatmap_and_smart_tuning():
    app = Path("src/ai_stock/app.py").read_text()

    assert "build_watchlist_sparklines" in app
    assert "build_market_heatmap_table" in app
    assert "build_smart_tuning_lite" in app
    assert "Watchlist" in app or "觀察清單" in app
    assert "市場熱力圖" in app
    assert "Smart Tuning Lite" in app
    assert "執行 Smart Tuning Lite" in app
