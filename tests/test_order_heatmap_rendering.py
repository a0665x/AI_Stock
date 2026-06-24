from pathlib import Path


def test_next_day_order_heatmap_uses_styler_not_raw_html_table():
    source = Path("src/ai_stock/app.py").read_text(encoding="utf-8")
    start = source.index("def _render_next_day_order_heatmap")
    end = source.index("_INDICATOR_GLOSSARY", start)
    block = source[start:end]

    assert "st.dataframe(styled" in block
    assert "display.style" in block
    assert "components.html" not in block
    assert "rows_html" not in block
    assert "heatmap_html" not in block


def test_indicator_glossary_includes_visual_icon_mapping():
    source = Path("src/ai_stock/app.py").read_text(encoding="utf-8")
    glossary_start = source.index("_INDICATOR_GLOSSARY")
    glossary_end = source.index("def _render_indicator_glossary", glossary_start)
    glossary = source[glossary_start:glossary_end]

    for label in ["K線", "Bollinger", "RSI14", "MACD / MACD Hist", "FVG / IFVG", "SMC Order Block", "SMC Liquidity", "BOS / ChoCH", "SFP"]:
        assert label in glossary

    # Each item is an icon/name/description tuple so users can visually match
    # glossary rows to chart markers and lines.
    assert '("🕯️", "K線"' in glossary
    assert '("▣", "SMC Order Block"' in glossary
