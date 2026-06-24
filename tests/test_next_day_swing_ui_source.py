from __future__ import annotations

from pathlib import Path

APP = Path("src/ai_stock/app.py").read_text()


def test_next_day_order_tab_contains_swing_technical_chart_wiring() -> None:
    assert "build_swing_order_technical_chart" in APP
    assert "selected_order_ticker" in APP
    assert "on_select=\"rerun\"" in APP
    assert "隔日掛單技術圖" in APP
    assert "UKF Momentum" in APP or "UKF 動能" in APP


def test_ukf_model_plan_documented() -> None:
    plan = Path("spec/task_understandings/2026-06-24_ukf_multisource_momentum_plan.md")
    assert plan.exists()
    text = plan.read_text()
    assert "UKF" in text
    assert "LSTM" in text
    assert "Transformer" in text
    assert "資料來源" in text
