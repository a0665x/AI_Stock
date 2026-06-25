from pathlib import Path

APP = Path("src/ai_stock/app.py")


def test_dashboard_has_action_board_and_clear_waiting_language():
    source = APP.read_text(encoding="utf-8")
    assert "_render_tradingview_action_board" in source
    assert "TradingView 式行動清單" in source
    assert "等待確認不是沒有模型或沒有回測" in source
    assert "最終方向" in source
    assert "下一步：打開交易計畫或圖表分析" in source
