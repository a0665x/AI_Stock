from __future__ import annotations

from pathlib import Path


def test_next_day_strategy_workbench_has_strategy_visualization_controls() -> None:
    app = Path("src/ai_stock/app.py").read_text()

    assert "build_strategy_visualization_payload" in app
    assert "策略視覺化股票" in app
    assert "策略視覺化策略" in app
    assert "顯示 SMC 特徵" in app
    assert "Strategy Buy Signal" not in app  # figure internals stay in module, not app glue
    assert "策略買賣點與績效曲線" in app
    assert "策略績效摘要" in app
