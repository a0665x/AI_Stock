from pathlib import Path


APP = Path("src/ai_stock/app.py")


def test_next_day_order_heatmap_uses_styler_not_raw_html_table() -> None:
    source = APP.read_text()
    heatmap_start = source.index("def _render_next_day_order_heatmap")
    glossary_start = source.index("_INDICATOR_GLOSSARY")
    block = source[heatmap_start:glossary_start]
    assert "st.dataframe(styled" in block
    assert "display.style" in block
    assert "components.html" not in block
    assert "rows_html" not in block
    assert "<tbody" not in block


def test_indicator_glossary_contains_visual_icons_for_chart_legend_mapping() -> None:
    source = APP.read_text()
    block = source[source.index("_INDICATOR_GLOSSARY"):source.index("def _render_indicator_glossary")]
    for label in ["K線", "Bollinger", "RSI14", "MACD / MACD Hist", "SMC Order Block", "SMC Liquidity", "Swing High / Low", "BOS / ChoCH", "SFP"]:
        assert label in block
    for icon in ["🕯️", "〰️", "⚡", "▮▮", "▣", "●", "▲▼", "✚", "◆"]:
        assert icon in block
