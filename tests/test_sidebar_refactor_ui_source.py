from pathlib import Path

APP = Path("src/ai_stock/app.py")


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def _sidebar_block() -> str:
    text = _source()
    start = text.index("with st.sidebar:")
    end = text.index("st.title(", start)
    return text[start:end]


def test_sidebar_keeps_only_global_settings_and_personal_preferences():
    sidebar = _sidebar_block()
    assert "資料來源" in sidebar
    assert "股票代號" in sidebar
    assert "歷史區間" in sidebar
    assert "K線週期" in sidebar
    assert "決策天數" in sidebar
    assert "個人交易偏好" in sidebar
    assert "上傳 CSV" in sidebar
    assert "重新抓資料 / 更新分析" in sidebar

    page_specific_labels = [
        "##### 因子研究",
        "因子輸入天數",
        "比較預測天數 horizon",
        "漲跌分類門檻%",
        "因子模型",
        "回測訓練視窗",
        "啟用持有天數 / 出場規則比較",
        "比較持有天數",
        "比較出場規則",
        "移動停損幅度",
        "##### Smart Tuning Lite",
        "Smart Tuning 持有天數",
        "Smart Tuning 風險寬度%",
        "回測只吃偏多觀察訊號",
        "K 線圖顯示成交量",
    ]
    for label in page_specific_labels:
        assert label not in sidebar


def test_page_specific_controls_live_inside_relevant_tabs():
    text = _source()
    backtest_section = text[text.index("with tab_backtest:") : text.index("with tab_factor:")]
    factor_section = text[text.index("with tab_factor:") : text.index("with tab_attribution:")]
    chart_section = text[text.index("with tab_chart:") : text.index("with tab_trade_vision:")]

    for label in [
        "回測訓練視窗",
        "啟用持有天數 / 出場規則比較",
        "比較持有天數",
        "比較出場規則",
        "移動停損幅度",
        "Smart Tuning 持有天數",
        "Smart Tuning 風險寬度%",
        "回測只吃偏多觀察訊號",
    ]:
        assert label in backtest_section

    for label in ["因子輸入天數", "比較預測幾天後", "漲跌分類門檻%", "因子模型"]:
        assert label in factor_section

    assert "K 線圖顯示成交量" in chart_section
