from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SelectionConfig:
    spread_risk: float = 3.0
    kelly_safety: float = 2.5
    buy_threshold: float = 1.0
    sell_threshold: float = -1.0
    near_chase: float = 3.0
    far_chase: float = 2.0
    top_k: int = 20


def _tick_round(price: float) -> float:
    if np.isnan(price):
        return np.nan
    if price > 1000.0:
        return round(price / 5.0) * 5.0
    if price > 500.0:
        return round(price / 1.0) * 1.0
    if price > 100.0:
        return round(price / 0.5) * 0.5
    if price > 50.0:
        return round(price / 0.1) * 0.1
    if price > 10.0:
        return round(price / 0.05) * 0.05
    return round(price / 0.01) * 0.01


def _threshold_adjust(value: float, cfg: SelectionConfig) -> float:
    if value > 0:
        return max(value - cfg.buy_threshold, 0)
    if value < 0:
        return min(value - cfg.sell_threshold, 0)
    return 0.0


def score_candidates(df: pd.DataFrame, cfg: SelectionConfig = SelectionConfig()) -> pd.DataFrame:
    """參考原始 `predict_result()`，聚焦在選股排序而非完整帳務管理。

    Required columns:
    - 代號
    - 收盤
    - pred_1
    - pred_60
    - history_std

    Optional columns:
    - current_weight_pct
    """
    required = {'代號', '收盤', 'pred_1', 'pred_60', 'history_std'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')

    out = df.copy()
    if 'current_weight_pct' not in out.columns:
        out['current_weight_pct'] = 0.0

    out['risk_adjusted_score'] = np.where(
        out['history_std'].replace(0, np.nan).notna(),
        out['pred_60'] / out['history_std'] * 100.0,
        np.nan,
    )
    out['order_rate'] = (
        cfg.near_chase * out['pred_1'] + cfg.far_chase * out['pred_60']
    ) / (1 + cfg.near_chase + cfg.far_chase)
    out['order_price'] = (out['收盤'] * (1 + out['order_rate'] * 0.01)).map(_tick_round)

    out['suggested_budget_pct'] = (
        out['risk_adjusted_score'] / cfg.spread_risk / cfg.kelly_safety
    ) - out['current_weight_pct']
    out['suggested_budget_pct'] = out['suggested_budget_pct'].map(lambda x: _threshold_adjust(x, cfg))

    out['action'] = np.select(
        [out['suggested_budget_pct'] > 0, out['suggested_budget_pct'] < 0],
        ['BUY', 'SELL'],
        default='HOLD',
    )

    out = out.sort_values(['risk_adjusted_score', 'pred_1'], ascending=False)
    out['rank'] = np.arange(1, len(out) + 1)
    return out.head(cfg.top_k).reset_index(drop=True)
