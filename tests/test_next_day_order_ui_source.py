from __future__ import annotations

from pathlib import Path

APP = Path("src/ai_stock/app.py").read_text(encoding="utf-8")


def test_app_wires_next_day_order_planner_tab() -> None:
    assert "build_next_day_order_plan" in APP
    assert "隔日掛單計畫" in APP
    assert "Next-Day Order Planner" in APP or "next_day_order" in APP
    assert "next_day_order_plan" in APP


def test_app_surfaces_next_day_reachability_columns() -> None:
    for text in ["隔日買進區", "隔日賣出區", "戰術停損", "硬停損", "成交機率", "建議單型"]:
        assert text in APP
