from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

from .analytics import add_indicators

FEATURE_LABELS = {
    "return_1d": "1日動能",
    "return_5d": "5日動能",
    "return_20d": "20日動能",
    "rsi_14": "RSI14",
    "macd_hist": "MACD 柱",
    "volatility_20d": "20日波動",
    "volume_ratio_20d": "量能比",
    "distance_sma20": "偏離 SMA20",
    "distance_sma60": "偏離 SMA60",
    "bb_position_20": "布林通道位置",
    "atr_pct_14": "ATR%",
    "stoch_k_14": "KD-K",
    "mfi_14": "MFI14",
    "drawdown_from_60d_high": "距60日高點回撤",
    "max_drawdown_60d": "60日最大回撤",
}

FEATURE_COLS = list(FEATURE_LABELS)


def _feature_ready_frame(prices: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    enriched = add_indicators(prices).sort_values("date").copy()
    enriched["target_return"] = enriched["close"].shift(-horizon) / enriched["close"] - 1
    return enriched.dropna(subset=FEATURE_COLS + ["target_return"]).reset_index(drop=True)


def _shap_contributions(model: RandomForestRegressor, latest: pd.DataFrame) -> tuple[np.ndarray, str]:
    import shap  # optional dependency; caller catches failures

    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(latest)
    if isinstance(values, list):
        values = values[0]
    arr = np.asarray(values)
    if arr.ndim == 2:
        arr = arr[0]
    return arr.astype(float), "shap_tree_explainer"


def _permutation_contributions(
    model: RandomForestRegressor,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    latest: pd.DataFrame,
) -> tuple[np.ndarray, str]:
    result = permutation_importance(model, x_train, y_train, n_repeats=8, random_state=42)
    importances = result.importances_mean
    baseline = x_train.median(numeric_only=True)
    spread = x_train.std(numeric_only=True).replace(0, np.nan)
    signed_distance = ((latest.iloc[0] - baseline) / spread).fillna(0).to_numpy(dtype=float)
    return importances * np.sign(signed_distance), "permutation_importance_fallback"


def explain_one_ticker(prices: pd.DataFrame, horizon: int = 5, top_n: int = 8) -> pd.DataFrame:
    """Return feature attribution rows for one ticker's future-return model.

    The preferred path uses SHAP TreeExplainer. On ARM or optional package failure,
    the function falls back to signed permutation importance so the UI still has a
    transparent attribution table instead of silently hiding the analysis.
    """
    work = _feature_ready_frame(prices, horizon=horizon)
    ticker = str(prices["ticker"].iloc[0]) if not prices.empty else ""
    if len(work) < 45:
        return pd.DataFrame(
            columns=["ticker", "feature", "feature_label", "value", "contribution", "method", "direction"]
        )

    x = work[FEATURE_COLS]
    y = work["target_return"]
    # Keep the model deliberately simple and explainable for the dashboard.
    model = RandomForestRegressor(
        n_estimators=160,
        max_depth=4,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x, y)
    latest = x.tail(1)

    try:
        contributions, method = _shap_contributions(model, latest)
    except Exception:
        if len(x) >= 80:
            x_train, _, y_train, _ = train_test_split(x, y, test_size=0.25, shuffle=False)
        else:
            x_train, y_train = x, y
        contributions, method = _permutation_contributions(model, x_train, y_train, latest)

    rows = []
    for feature, value, contribution in zip(FEATURE_COLS, latest.iloc[0].to_numpy(dtype=float), contributions):
        rows.append(
            {
                "ticker": ticker,
                "feature": feature,
                "feature_label": FEATURE_LABELS.get(feature, feature),
                "value": float(value),
                "contribution": float(contribution),
                "method": method,
                "direction": "正向" if contribution > 0 else "負向" if contribution < 0 else "中性",
            }
        )
    out = pd.DataFrame(rows)
    out["abs_contribution"] = out["contribution"].abs()
    return out.sort_values("abs_contribution", ascending=False).head(top_n).drop(columns="abs_contribution").reset_index(drop=True)


def build_attribution_report(prices: pd.DataFrame, horizon: int = 5, top_n: int = 8) -> pd.DataFrame:
    rows = []
    for _, group in prices.sort_values(["ticker", "date"]).groupby("ticker", sort=False):
        rows.append(explain_one_ticker(group.reset_index(drop=True), horizon=horizon, top_n=top_n))
    rows = [row for row in rows if not row.empty]
    if not rows:
        return pd.DataFrame(columns=["ticker", "feature", "feature_label", "value", "contribution", "method", "direction"])
    return pd.concat(rows, ignore_index=True)
