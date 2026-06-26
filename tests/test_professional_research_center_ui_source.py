from pathlib import Path

APP = Path("src/ai_stock/app.py")


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def test_research_center_uses_professional_market_research_subtabs():
    src = _source()
    assert "research_overview_tab" in src
    assert "research_lab_tab" in src
    assert "research_factor_tab" in src
    assert "research_training_tab" in src
    assert "research_risk_tab" in src
    assert '["總覽", "策略實驗室", "因子排行", "訓練資料", "風險與關聯"]' in src
    assert 'st.tabs(["回測 / Smart Tuning", "因子研究", "SHAP 歸因", "股票關係", "訓練資料"])' not in src


def test_research_center_has_tradingview_backtest_platform_sections():
    src = _source()
    for phrase in [
        "Research Radar",
        "Strategy Tester",
        "Factor Explorer",
        "Training Data Studio",
        "Risk & Correlation Monitor",
        "研究中心怎麼使用？",
        "先看 Research Radar",
        "像 TradingView 的 Strategy Tester",
    ]:
        assert phrase in src


def test_research_center_explains_metrics_and_color_semantics():
    src = _source()
    for phrase in [
        "顏色語意",
        "綠色代表表現或關聯較強",
        "紅色代表風險、回撤或負向壓力較高",
        "AUC 接近 50% 代表接近隨機",
        "Profit Factor 大於 1 才代表獲利交易金額大於虧損交易金額",
        "最大回撤是策略曾經從高點跌下來的最大幅度",
    ]:
        assert phrase in src


def test_research_center_keeps_heavy_analysis_button_triggered():
    src = _source()
    for phrase in [
        "執行研究總覽快照",
        "執行 Smart Tuning Lite",
        "執行因子排行",
        "產生 Training Data",
    ]:
        assert phrase in src
