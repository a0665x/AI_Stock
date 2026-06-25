from __future__ import annotations

from pathlib import Path

APP_SOURCE = Path("src/ai_stock/app.py").read_text(encoding="utf-8")


def test_next_day_order_plan_integrates_strategy_workbench_results_in_ui() -> None:
    assert "integrate_strategy_recommendations_into_order_plan" in APP_SOURCE
    assert "order_strategy_workbench_result" in APP_SOURCE
    assert "STRATEGY_WORKBENCH" in Path("src/ai_stock/order_planner.py").read_text(encoding="utf-8")
    assert "最終買進區" in APP_SOURCE
    assert "最終賣出區" in APP_SOURCE
    assert "最終策略適配分數" in APP_SOURCE
    assert "若已跑過隔日策略工作台" in APP_SOURCE


def test_technical_chart_uses_final_strategy_ranges_when_available() -> None:
    assert "final_buy_low" in APP_SOURCE
    assert "final_sell_high" in APP_SOURCE
    assert "final_stop_loss" in APP_SOURCE
    assert "strategy_take_profit_price" in APP_SOURCE
