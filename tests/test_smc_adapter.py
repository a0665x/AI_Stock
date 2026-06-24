from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd

from ai_stock.smc_adapter import build_smc_context, smartmoneyconcepts_available


def _prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    close = np.array([100, 101, 103, 102, 105, 108, 106, 104, 107, 111, 109, 112], dtype=float)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.6,
            "high": close + 1.4,
            "low": close - 1.5,
            "close": close,
            "volume": np.arange(12) * 1000 + 10000,
        }
    )


def test_smc_adapter_normalizes_smartmoneyconcepts_outputs(monkeypatch) -> None:
    fake_pkg = types.ModuleType("smartmoneyconcepts")
    fake_smc = types.SimpleNamespace()

    def fvg(df):
        return pd.DataFrame(
            {
                "FVG": [np.nan, 1.0, -1.0] + [np.nan] * (len(df) - 3),
                "Top": [np.nan, 104.0, 101.0] + [np.nan] * (len(df) - 3),
                "Bottom": [np.nan, 102.0, 99.5] + [np.nan] * (len(df) - 3),
                "MitigatedIndex": [np.nan, np.nan, 6.0] + [np.nan] * (len(df) - 3),
            }
        )

    def swing_highs_lows(df, swing_length=3):
        return pd.DataFrame(
            {
                "HighLow": [np.nan, 1.0, np.nan, -1.0] + [np.nan] * (len(df) - 4),
                "Level": [np.nan, 104.0, np.nan, 98.0] + [np.nan] * (len(df) - 4),
            }
        )

    def bos_choch(df, swings, close_break=True):
        return pd.DataFrame(
            {
                "BOS": [np.nan, np.nan, 1.0] + [np.nan] * (len(df) - 3),
                "CHOCH": [np.nan, np.nan, np.nan, -1.0] + [np.nan] * (len(df) - 4),
                "Level": [np.nan, np.nan, 104.0, 98.0] + [np.nan] * (len(df) - 4),
            }
        )

    def ob(df, swings):
        return pd.DataFrame(
            {
                "OB": [np.nan, 1.0, np.nan, -1.0] + [np.nan] * (len(df) - 4),
                "Top": [np.nan, 103.5, np.nan, 110.0] + [np.nan] * (len(df) - 4),
                "Bottom": [np.nan, 100.5, np.nan, 106.0] + [np.nan] * (len(df) - 4),
                "Percentage": [np.nan, 70.0, np.nan, 55.0] + [np.nan] * (len(df) - 4),
            }
        )

    def liquidity(df, swings):
        return pd.DataFrame(
            {
                "Liquidity": [np.nan, np.nan, 1.0, -1.0] + [np.nan] * (len(df) - 4),
                "Level": [np.nan, np.nan, 105.0, 97.5] + [np.nan] * (len(df) - 4),
                "End": [np.nan, np.nan, 5.0, 6.0] + [np.nan] * (len(df) - 4),
                "Swept": [np.nan, np.nan, np.nan, 8.0] + [np.nan] * (len(df) - 4),
            }
        )

    fake_smc.fvg = fvg
    fake_smc.swing_highs_lows = swing_highs_lows
    fake_smc.bos_choch = bos_choch
    fake_smc.ob = ob
    fake_smc.liquidity = liquidity
    fake_pkg.smc = fake_smc
    monkeypatch.setitem(sys.modules, "smartmoneyconcepts", fake_pkg)

    ctx = build_smc_context(_prices(), prefer_external=True)

    assert ctx["engine"] == "smartmoneyconcepts"
    assert not ctx["fvg_zones"].empty
    assert {"FVG_BULLISH", "FVG_BEARISH"}.issubset(set(ctx["fvg_zones"]["zone_type"]))
    assert "IFVG" in set(ctx["fvg_zones"]["status"])
    assert not ctx["order_blocks"].empty
    assert {"OB_BULLISH", "OB_BEARISH"}.issubset(set(ctx["order_blocks"]["zone_type"]))
    assert not ctx["liquidity"].empty
    assert not ctx["structure_events"].empty
    assert not ctx["swings"].empty


def test_smc_adapter_falls_back_when_smartmoneyconcepts_is_unavailable(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "smartmoneyconcepts", None)

    ctx = build_smc_context(_prices(), prefer_external=True)

    assert ctx["engine"] == "fallback"
    assert "fvg_zones" in ctx
    assert "order_blocks" in ctx
    assert "liquidity" in ctx
    assert ctx["order_blocks"].empty
    assert ctx["liquidity"].empty
    assert smartmoneyconcepts_available() is False
