from __future__ import annotations

import numpy as np
import pandas as pd

from ai_stock.training_data import build_training_dataset, compute_top_training_features


def _prices(days: int = 90) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    rows = []
    for ticker, phase in [("AAA", 0.0), ("BBB", 1.3)]:
        base = 100 + np.arange(days) * (0.15 if ticker == "AAA" else -0.05) + np.sin(np.arange(days) / 5 + phase) * 2
        for i, date in enumerate(dates):
            close = float(base[i])
            rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "open": close * 0.995,
                    "high": close * 1.02,
                    "low": close * 0.98,
                    "close": close,
                    "volume": 1_000_000 + i * 1000,
                }
            )
    return pd.DataFrame(rows)


def test_training_dataset_contains_price_indicators_signals_and_forward_target() -> None:
    data = build_training_dataset(_prices(), forward_days=3, include_smc=True)
    assert not data.empty
    required = {
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "rsi_14",
        "macd_hist",
        "bb_position_20",
        "stoch_k_14",
        "volume_ratio_20d",
        "ukf_momentum",
        "macd_cross_up",
        "kd_cross_down",
        "smc_fvg_bullish",
        "smc_order_block_bullish",
        "smc_liquidity_nearby",
        "forward_return_3d",
        "target_up_3d",
        "target_available_3d",
    }
    assert required.issubset(data.columns)
    feature_numeric = data.select_dtypes(include=[np.number]).drop(columns=["forward_return_3d", "target_up_3d", "target_close_3d"], errors="ignore")
    assert feature_numeric.isna().sum().sum() == 0
    assert data.groupby("ticker").tail(3)["target_available_3d"].eq(0).all()
    assert data.groupby("ticker").tail(3)["forward_return_3d"].isna().all()
    assert data.loc[data["target_available_3d"] == 1, "forward_return_3d"].notna().all()


def test_top_training_features_ranks_smc_and_indicator_columns() -> None:
    data = build_training_dataset(_prices(), forward_days=3, include_smc=True)
    ranked = compute_top_training_features(data, target_col="forward_return_3d", top_n=12)
    assert not ranked.empty
    assert {"feature", "pearson_corr", "spearman_corr", "abs_score", "non_null_ratio"}.issubset(ranked.columns)
    assert ranked["abs_score"].is_monotonic_decreasing
    assert all(not str(f).startswith("target_") for f in ranked["feature"])
