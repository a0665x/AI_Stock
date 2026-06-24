from __future__ import annotations

from pathlib import Path

APP = Path("src/ai_stock/app.py")


def test_trade_vision_center_tab_is_wired_after_price_chart():
    source = APP.read_text(encoding="utf-8")

    assert "智能交易視覺中心" in source
    assert "Trade Vision Center" in source
    assert "build_trade_vision_chart" in source
    assert "detect_market_structure" in source
    assert "build_trade_plan_from_decision" in source
    assert "compute_trade_signal_score" in source
    assert "build_trade_narrative" in source

    tab_line = next(line for line in source.splitlines() if "st.tabs" in line and "價格圖表" in line)
    assert tab_line.index("價格圖表") < tab_line.index("智能交易視覺中心") < tab_line.index("回測")
