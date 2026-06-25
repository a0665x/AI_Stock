from __future__ import annotations

from pathlib import Path


APP = Path("src/ai_stock/app.py")


def test_next_day_strategy_workbench_tab_and_controls_exist() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "隔日策略工作台" in source
    assert "build_order_strategy_workbench" in source
    assert "要驗證哪些股票" in source
    assert "可承受停損幅度%" in source
    assert "預計持有天數" in source
    assert "選擇策略" in source
    assert "用多久歷史驗證" in source
    assert "啟動隔日策略回測" in source
    assert "策略勝率 / 股性適配表" in source
    assert "最佳掛單區間" in source


def test_next_day_strategy_workbench_uses_button_not_eager_global_compute() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "st.session_state.order_strategy_workbench_result" in source
    assert "run_order_strategy_workbench" in source
    assert "build_order_strategy_workbench(" in source
    # Expensive strategy grid must live behind the page button, not in the top-level
    # always-on data-preparation block.
    before_tabs = source.split("st.tabs", maxsplit=1)[0]
    assert "build_order_strategy_workbench(" not in before_tabs
