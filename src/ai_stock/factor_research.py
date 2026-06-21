from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .analytics import add_indicators
from .data_sources import normalize_ohlcv


@dataclass(frozen=True)
class FactorDataset:
    X: pd.DataFrame
    y_direction: pd.Series
    y_return: pd.Series
    meta: pd.DataFrame


@dataclass(frozen=True)
class FactorResearchReport:
    summary: pd.DataFrame
    importance: pd.DataFrame
    correlations: pd.DataFrame
    grouped_win_rates: pd.DataFrame
    y_heatmap: pd.DataFrame
    samples: pd.DataFrame


BASE_FEATURES = [
    "close_return",
    "return_5d",
    "rsi_14",
    "macd_hist",
    "stoch_k_14",
    "stoch_d_3",
    "mfi_14",
    "bb_position_20",
    "atr_pct_14",
    "volatility_20d",
    "volume_ratio_20d",
    "distance_sma20",
    "distance_sma60",
    "drawdown_from_60d_high",
    "max_drawdown_60d",
    "candle_body_pct",
    "upper_shadow_pct",
    "lower_shadow_pct",
    "intraday_range_pct",
    "volume_return_1d",
]

FEATURE_LABELS = {
    "close_return": "收盤報酬",
    "return_5d": "5日報酬",
    "rsi_14": "RSI14",
    "macd_hist": "MACD柱",
    "stoch_k_14": "KD-K",
    "stoch_d_3": "KD-D",
    "mfi_14": "MFI14",
    "bb_position_20": "布林位置",
    "atr_pct_14": "ATR%",
    "volatility_20d": "20日波動",
    "volume_ratio_20d": "量能比",
    "distance_sma20": "距SMA20",
    "distance_sma60": "距SMA60",
    "drawdown_from_60d_high": "距60日高點",
    "max_drawdown_60d": "60日最大回撤",
    "candle_body_pct": "K線實體",
    "upper_shadow_pct": "上影線",
    "lower_shadow_pct": "下影線",
    "intraday_range_pct": "日內振幅",
    "volume_return_1d": "量能變化",
}


def _feature_label(feature: str) -> str:
    if "_lag_" not in feature:
        return FEATURE_LABELS.get(feature, feature)
    base, lag = feature.rsplit("_lag_", 1)
    return f"{FEATURE_LABELS.get(base, base)}｜前{lag}天"


def _prepare_ticker_frame(group: pd.DataFrame) -> pd.DataFrame:
    g = add_indicators(group).sort_values("date").reset_index(drop=True)
    close = g["close"].replace(0, np.nan)
    high = g["high"]
    low = g["low"]
    open_ = g["open"]
    volume = g["volume"].replace(0, np.nan)
    g["close_return"] = g["return_1d"]
    g["candle_body_pct"] = (g["close"] - open_) / close
    g["upper_shadow_pct"] = (high - np.maximum(open_, g["close"])) / close
    g["lower_shadow_pct"] = (np.minimum(open_, g["close"]) - low) / close
    g["intraday_range_pct"] = (high - low) / close
    g["volume_return_1d"] = volume.pct_change()
    fill_defaults = {
        "rsi_14": 50.0,
        "stoch_k_14": 50.0,
        "stoch_d_3": 50.0,
        "mfi_14": 50.0,
        "bb_position_20": 0.5,
    }
    for col in BASE_FEATURES:
        if col not in g.columns:
            continue
        default = fill_defaults.get(col, 0.0)
        g[col] = g[col].replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(default)
    return g


def build_sliding_window_dataset(
    prices: pd.DataFrame,
    window: int = 7,
    horizon: int = 1,
    target_threshold: float = 0.0,
    min_samples_per_ticker: int = 30,
) -> FactorDataset:
    """Build supervised factor samples from past `window` days and future direction.

    For each ticker and anchor day t, X contains lagged features from t-window+1..t,
    and y is the return from close[t] to close[t+horizon]. No future OHLCV is used in X.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    if horizon < 1:
        raise ValueError("horizon must be at least 1")

    data = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    rows: list[dict[str, float]] = []
    y_dir: list[int] = []
    y_ret: list[float] = []
    meta: list[dict[str, object]] = []

    for ticker, group in data.groupby("ticker", sort=False):
        g = _prepare_ticker_frame(group)
        if len(g) < window + horizon + min_samples_per_ticker:
            if min_samples_per_ticker > 1:
                continue
        usable_features = [c for c in BASE_FEATURES if c in g.columns]
        for end_idx in range(window - 1, len(g) - horizon):
            anchor_close = float(g.loc[end_idx, "close"])
            target_close = float(g.loc[end_idx + horizon, "close"])
            if not np.isfinite(anchor_close) or anchor_close <= 0 or not np.isfinite(target_close):
                continue
            forward_return = target_close / anchor_close - 1
            features: dict[str, float] = {}
            valid = True
            for lag in range(1, window + 1):
                source_idx = end_idx - lag + 1
                for col in usable_features:
                    value = g.loc[source_idx, col]
                    if pd.isna(value) or not np.isfinite(value):
                        valid = False
                        break
                    features[f"{col}_lag_{lag}"] = float(value)
                if not valid:
                    break
            if not valid:
                continue
            rows.append(features)
            y_ret.append(float(forward_return))
            y_dir.append(int(forward_return > target_threshold))
            meta.append(
                {
                    "ticker": ticker,
                    "date": pd.Timestamp(g.loc[end_idx, "date"]),
                    "target_date": pd.Timestamp(g.loc[end_idx + horizon, "date"]),
                    "anchor_close": anchor_close,
                    "target_close": target_close,
                }
            )

    X = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)
    if not X.empty:
        X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
    return FactorDataset(
        X=X.reset_index(drop=True),
        y_direction=pd.Series(y_dir, name="direction", dtype="int64"),
        y_return=pd.Series(y_ret, name="forward_return", dtype="float64"),
        meta=pd.DataFrame(meta),
    )


def _make_model(model_type: str, random_state: int):
    if model_type == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", random_state=random_state))
    if model_type == "random_forest":
        return RandomForestClassifier(n_estimators=120, min_samples_leaf=5, class_weight="balanced_subsample", random_state=random_state, n_jobs=-1)
    return GradientBoostingClassifier(n_estimators=80, max_depth=3, learning_rate=0.05, random_state=random_state)


def _predict_proba(model, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    return model.decision_function(X)


def _importance_rows(model, X_test: pd.DataFrame, y_test: pd.Series, ticker: str, top_n: int, random_state: int) -> tuple[list[dict[str, object]], str]:
    method = "permutation_importance_fallback"
    signed = pd.Series(0.0, index=X_test.columns)
    importance = pd.Series(0.0, index=X_test.columns)
    try:
        import shap  # type: ignore

        explainer = shap.Explainer(model, X_test)
        values = explainer(X_test)
        arr = np.asarray(values.values)
        if arr.ndim == 3:
            arr = arr[:, :, -1]
        signed = pd.Series(arr.mean(axis=0), index=X_test.columns)
        importance = pd.Series(np.abs(arr).mean(axis=0), index=X_test.columns)
        method = "shap_explainer"
    except Exception:
        if len(X_test) >= 8 and y_test.nunique() > 1:
            perm = permutation_importance(model, X_test, y_test, n_repeats=5, random_state=random_state, scoring="accuracy")
            importance = pd.Series(np.maximum(perm.importances_mean, 0), index=X_test.columns)
        if hasattr(model, "feature_importances_"):
            importance = pd.Series(getattr(model, "feature_importances_"), index=X_test.columns)
        elif hasattr(model, "named_steps") and "logisticregression" in model.named_steps:
            coef = model.named_steps["logisticregression"].coef_[0]
            signed = pd.Series(coef, index=X_test.columns)
            importance = signed.abs()

    if signed.abs().sum() == 0:
        corr = X_test.apply(lambda col: col.corr(y_test) if col.nunique(dropna=True) > 1 else 0.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        signed = corr * importance.reindex(corr.index).fillna(0.0)

    rows = []
    for feature in importance.sort_values(ascending=False).head(top_n).index:
        value = float(importance.loc[feature])
        signed_value = float(signed.get(feature, 0.0))
        rows.append(
            {
                "ticker": ticker,
                "feature": feature,
                "feature_label": _feature_label(feature),
                "importance": value,
                "signed_contribution": signed_value,
                "direction": "positive" if signed_value >= 0 else "negative",
                "method": method,
            }
        )
    return rows, method


def _correlation_rows(X: pd.DataFrame, y: pd.Series, y_return: pd.Series, ticker: str, top_features: list[str]) -> list[dict[str, object]]:
    rows = []
    for feature in top_features:
        series = X[feature]
        pearson = float(series.corr(y_return)) if series.nunique(dropna=True) > 1 else 0.0
        spearman = float(series.corr(y_return, method="spearman")) if series.nunique(dropna=True) > 1 else 0.0
        try:
            mi = float(mutual_info_classif(series.to_frame(), y, random_state=7, discrete_features=False)[0]) if y.nunique() > 1 else 0.0
        except Exception:
            mi = 0.0
        rows.append(
            {
                "ticker": ticker,
                "feature": feature,
                "feature_label": _feature_label(feature),
                "spearman_corr": 0.0 if not np.isfinite(spearman) else spearman,
                "pearson_corr": 0.0 if not np.isfinite(pearson) else pearson,
                "mutual_info": mi,
            }
        )
    return rows


def _grouped_win_rate_rows(X: pd.DataFrame, y: pd.Series, y_return: pd.Series, ticker: str, top_features: list[str]) -> list[dict[str, object]]:
    rows = []
    for feature in top_features[:8]:
        series = X[feature]
        try:
            buckets = pd.qcut(series.rank(method="first"), q=4, labels=["低", "中低", "中高", "高"], duplicates="drop")
        except Exception:
            continue
        frame = pd.DataFrame({"bucket": buckets, "direction": y.values, "forward_return": y_return.values})
        for bucket, group in frame.groupby("bucket", observed=True):
            if group.empty:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "feature": feature,
                    "feature_label": _feature_label(feature),
                    "bucket": str(bucket),
                    "samples": int(len(group)),
                    "up_rate": float(group["direction"].mean()),
                    "avg_forward_return": float(group["forward_return"].mean()),
                }
            )
    return rows


def _return_bucket(value: float) -> str:
    if value <= -0.03:
        return "大跌"
    if value < 0:
        return "小跌"
    if value < 0.03:
        return "小漲"
    return "大漲"


def build_factor_research_report(
    prices: pd.DataFrame,
    window: int = 7,
    horizon: int = 1,
    target_threshold: float = 0.0,
    model_type: str = "gradient_boosting",
    top_n: int = 20,
    min_samples_per_ticker: int = 40,
    random_state: int = 7,
) -> FactorResearchReport:
    dataset = build_sliding_window_dataset(
        prices,
        window=window,
        horizon=horizon,
        target_threshold=target_threshold,
        min_samples_per_ticker=min_samples_per_ticker,
    )
    if dataset.X.empty:
        empty = pd.DataFrame()
        return FactorResearchReport(empty, empty, empty, empty, empty, empty)

    summary_rows: list[dict[str, object]] = []
    importance_rows: list[dict[str, object]] = []
    corr_rows: list[dict[str, object]] = []
    group_rows: list[dict[str, object]] = []
    heat_rows: list[dict[str, object]] = []
    sample_parts = []

    samples = dataset.meta.copy()
    samples["direction"] = dataset.y_direction.values
    samples["forward_return"] = dataset.y_return.values
    samples = pd.concat([samples.reset_index(drop=True), dataset.X.reset_index(drop=True)], axis=1)

    for ticker, idx in samples.groupby("ticker", sort=False).groups.items():
        idx_list = list(idx)
        X_t = dataset.X.iloc[idx_list].reset_index(drop=True)
        y_t = dataset.y_direction.iloc[idx_list].reset_index(drop=True)
        ret_t = dataset.y_return.iloc[idx_list].reset_index(drop=True)
        meta_t = dataset.meta.iloc[idx_list].reset_index(drop=True)
        if len(X_t) < min_samples_per_ticker or y_t.nunique() < 2:
            continue
        split = max(10, int(len(X_t) * 0.7))
        if split >= len(X_t) - 5:
            split = max(1, len(X_t) - 10)
        X_train, X_test = X_t.iloc[:split], X_t.iloc[split:]
        y_train, y_test = y_t.iloc[:split], y_t.iloc[split:]
        if y_train.nunique() < 2 or y_test.empty:
            continue
        model = _make_model(model_type, random_state)
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        prob = _predict_proba(model, X_test)
        accuracy = float(accuracy_score(y_test, pred))
        try:
            auc = float(roc_auc_score(y_test, prob)) if y_test.nunique() > 1 else np.nan
        except Exception:
            auc = np.nan
        imp_rows, method = _importance_rows(model, X_test, y_test, str(ticker), top_n, random_state)
        top_features = [r["feature"] for r in imp_rows] or list(X_t.columns[:top_n])
        importance_rows.extend(imp_rows)
        corr_rows.extend(_correlation_rows(X_t, y_t, ret_t, str(ticker), top_features))
        group_rows.extend(_grouped_win_rate_rows(X_t, y_t, ret_t, str(ticker), top_features))
        summary_rows.append(
            {
                "ticker": ticker,
                "samples": int(len(X_t)),
                "train_samples": int(len(X_train)),
                "test_samples": int(len(X_test)),
                "baseline_up_rate": float(y_t.mean()),
                "accuracy": accuracy,
                "auc": auc,
                "model": model_type,
                "method": method,
                "window": int(window),
                "horizon": int(horizon),
                "target_threshold": float(target_threshold),
            }
        )
        heat = meta_t.copy()
        heat["forward_return"] = ret_t.values
        heat["direction"] = y_t.values
        heat["return_bucket"] = heat["forward_return"].map(_return_bucket)
        heat["window"] = int(window)
        heat["horizon"] = int(horizon)
        heat["target_threshold"] = float(target_threshold)
        heat_rows.extend(heat[["ticker", "date", "target_date", "forward_return", "direction", "return_bucket", "window", "horizon", "target_threshold"]].to_dict("records"))
        sample_meta = pd.DataFrame(
            {
                "window": int(window),
                "horizon": int(horizon),
                "target_threshold": float(target_threshold),
            },
            index=meta_t.index,
        )
        sample_part = pd.concat([meta_t, y_t.rename("direction"), ret_t.rename("forward_return"), X_t, sample_meta], axis=1)
        sample_parts.append(sample_part)

    return FactorResearchReport(
        summary=pd.DataFrame(summary_rows),
        importance=pd.DataFrame(importance_rows),
        correlations=pd.DataFrame(corr_rows),
        grouped_win_rates=pd.DataFrame(group_rows),
        y_heatmap=pd.DataFrame(heat_rows),
        samples=pd.concat(sample_parts, ignore_index=True) if sample_parts else pd.DataFrame(),
    )


def build_factor_horizon_comparison(
    prices: pd.DataFrame,
    window: int = 7,
    horizons: list[int] | tuple[int, ...] = (1, 3, 5, 10),
    target_threshold: float = 0.0,
    model_type: str = "gradient_boosting",
    top_n: int = 20,
    min_samples_per_ticker: int = 40,
    random_state: int = 7,
) -> dict[str, pd.DataFrame]:
    """Run factor research for multiple future horizons and concatenate tables.

    Each horizon is trained independently so feature importance answers:
    which past-window factors explain the direction for this specific future window.
    """
    unique_horizons: list[int] = []
    for horizon in horizons:
        h = int(horizon)
        if h < 1:
            raise ValueError("horizons must be positive integers")
        if h not in unique_horizons:
            unique_horizons.append(h)
    if not unique_horizons:
        raise ValueError("at least one horizon is required")

    table_parts: dict[str, list[pd.DataFrame]] = {
        "summary": [],
        "importance": [],
        "correlations": [],
        "grouped_win_rates": [],
        "y_heatmap": [],
        "samples": [],
    }
    for horizon in unique_horizons:
        report = build_factor_research_report(
            prices,
            window=window,
            horizon=horizon,
            target_threshold=target_threshold,
            model_type=model_type,
            top_n=top_n,
            min_samples_per_ticker=min_samples_per_ticker,
            random_state=random_state,
        )
        for key, value in {
            "summary": report.summary,
            "importance": report.importance,
            "correlations": report.correlations,
            "grouped_win_rates": report.grouped_win_rates,
            "y_heatmap": report.y_heatmap,
            "samples": report.samples,
        }.items():
            if value.empty:
                continue
            part = value.copy()
            if "horizon" not in part.columns:
                part["horizon"] = horizon
            if "window" not in part.columns:
                part["window"] = window
            if "target_threshold" not in part.columns:
                part["target_threshold"] = target_threshold
            table_parts[key].append(part)

    return {
        key: pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        for key, parts in table_parts.items()
    }


def build_ticker_horizon_metric_matrix(summary: pd.DataFrame, metric: str = "accuracy") -> pd.DataFrame:
    """Pivot ticker × horizon metrics for heatmap visualizations.

    `metric` can be accuracy, auc, baseline_up_rate, or any numeric column in the
    multi-horizon summary table. Values remain in 0..1 ratio space so callers can
    decide whether to render as percent.
    """
    if summary.empty or not {"ticker", "horizon", metric}.issubset(summary.columns):
        return pd.DataFrame()
    work = summary[["ticker", "horizon", metric]].copy()
    work["horizon"] = pd.to_numeric(work["horizon"], errors="coerce")
    work[metric] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=["ticker", "horizon"])
    if work.empty:
        return pd.DataFrame()
    work["horizon"] = work["horizon"].astype(int)
    matrix = work.pivot_table(index="ticker", columns="horizon", values=metric, aggfunc="mean")
    return matrix.sort_index().reindex(sorted(matrix.columns), axis=1)


def build_horizon_metric_trends(summary: pd.DataFrame) -> pd.DataFrame:
    """Aggregate factor-model win-rate and AUC metrics by prediction horizon.

    Input is the multi-horizon `summary` table where each row is ticker × horizon.
    Output is one row per horizon, sorted ascending, ready for trend charts.
    """
    required = {"horizon", "accuracy", "auc", "baseline_up_rate", "samples"}
    if summary.empty or not required.issubset(summary.columns):
        return pd.DataFrame(columns=["horizon", "accuracy", "auc", "baseline_up_rate", "sample_count", "ticker_count"])

    work = summary.copy()
    for col in ["horizon", "accuracy", "auc", "baseline_up_rate", "samples"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    grouped = work.groupby("horizon", as_index=False).agg(
        accuracy=("accuracy", "mean"),
        auc=("auc", "mean"),
        baseline_up_rate=("baseline_up_rate", "mean"),
        sample_count=("samples", "sum"),
        ticker_count=("ticker", "nunique") if "ticker" in work.columns else ("horizon", "size"),
    )
    grouped = grouped.round({"accuracy": 10, "auc": 10, "baseline_up_rate": 10})
    return grouped.sort_values("horizon").reset_index(drop=True)
