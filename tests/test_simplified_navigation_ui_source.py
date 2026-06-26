from pathlib import Path

APP = Path("src/ai_stock/app.py")


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def test_main_navigation_is_simplified_to_five_professional_tabs():
    src = _source()
    assert "tab_dashboard, tab_orders, tab_charts, tab_strategy_lab, tab_research = st.tabs" in src
    assert '["今日決策", "交易計畫", "圖表分析", "策略驗證", "研究中心"]' in src
    assert 'st.tabs(["決策總覽", "持倉下單計畫", "隔日掛單計畫"' not in src
    assert "research_overview_tab" in src
    assert "research_lab_tab" in src
    assert "research_factor_tab" in src
    assert "research_training_tab" in src
    assert "research_risk_tab" in src


def test_each_simplified_tab_has_purpose_and_next_step_copy():
    src = _source()
    for phrase in [
        "本頁回答：今天應優先看哪幾檔？",
        "本頁回答：明天可以怎麼掛單？",
        "本頁回答：價格位置適合進場嗎？",
        "本頁回答：這個策略近期對這檔股票有效嗎？",
        "本頁回答：模型為什麼這樣判斷？",
    ]:
        assert phrase in src


def test_strategy_side_codes_are_mapped_to_human_action_labels():
    src = _source()
    assert "STRATEGY_SIDE_LABELS_ZH" in src
    assert '"BUY": "買進 / 加碼"' in src
    assert '"SELL": "賣出 / 減碼 / 保護"' in src
    assert '"WAIT": "等待確認"' in src
    assert "_display_strategy_side" in src
    assert "BUY 偏綠色" not in src
    assert "SELL 偏紅色" not in src
