from __future__ import annotations

from pathlib import Path


def test_strategy_workbench_ui_explains_chart_colors_page_purpose_and_preferences() -> None:
    app = Path("src/ai_stock/app.py").read_text()

    assert "個人交易偏好" in app
    assert "每天每股最多掛單次數" in app
    assert "預設每次掛單股數/張數" in app
    assert "不做當沖" in app
    assert "頁籤使用目的" in app
    assert "策略適配分數顏色" in app
    assert "綠色代表策略適配較高" in app
    assert "這不是 SHAP 正負相關" in app
    assert "每筆交易垂直虛線" in app
    assert "獲利/虧損區間線" in app
