from __future__ import annotations

from pathlib import Path

APP = Path("src/ai_stock/app.py")


def test_trade_vision_center_is_wired_inside_chart_analysis_tab():
    source = APP.read_text(encoding="utf-8")

    assert "圖表分析" in source
    assert "智能交易視覺中心" in source
    assert "Trade Vision Center" in source
    assert "build_trade_vision_chart" in source
    assert "detect_market_structure" in source
    assert "build_trade_plan_from_decision" in source
    assert "compute_trade_signal_score" in source
    assert "build_trade_narrative" in source

    main_tab_line = next(line for line in source.splitlines() if "st.tabs" in line and "今日決策" in line)
    assert "圖表分析" in main_tab_line
    assert "價格圖表" not in main_tab_line
    assert "智能交易視覺中心" not in main_tab_line
    assert "tab_chart = tab_charts" in source
    assert "tab_trade_vision = tab_charts" in source
