from __future__ import annotations

import numpy as np
import pandas as pd

from .analytics import add_indicators
from .data_sources import normalize_ohlcv
from .smc_adapter import build_smc_context
from .swing_order_chart import compute_ukf_momentum_state, detect_candlestick_patterns


def _empty_smc_features(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "smc_fvg_bullish": 0,
            "smc_fvg_bearish": 0,
            "smc_order_block_bullish": 0,
            "smc_order_block_bearish": 0,
            "smc_liquidity_nearby": 0,
            "smc_bos_up": 0,
            "smc_bos_down": 0,
            "smc_choch_up": 0,
            "smc_choch_down": 0,
            "smc_swing_high": 0,
            "smc_swing_low": 0,
        },
        index=index,
    )


def _flag_dates(base: pd.DataFrame, events: pd.DataFrame, date_col: str = "date") -> pd.Series:
    if events is None or events.empty or date_col not in events.columns:
        return pd.Series(0, index=base.index, dtype="int64")
    dates = pd.to_datetime(events[date_col]).dt.normalize()
    base_dates = pd.to_datetime(base["date"]).dt.normalize()
    return base_dates.isin(set(dates)).astype("int64")


def _smc_features_for_ticker(one: pd.DataFrame) -> pd.DataFrame:
    features = _empty_smc_features(one.index)
    try:
        ctx = build_smc_context(one)
    except Exception:
        return features

    fvg = ctx.get("fvg_zones", pd.DataFrame())
    if isinstance(fvg, pd.DataFrame) and not fvg.empty:
        if "bias" in fvg.columns:
            bull = fvg[fvg["bias"].astype(str).str.lower().str.contains("bull")]
            bear = fvg[fvg["bias"].astype(str).str.lower().str.contains("bear")]
        elif "fvg_type" in fvg.columns:
            bull = fvg[fvg["fvg_type"].astype(str).str.lower().str.contains("bull")]
            bear = fvg[fvg["fvg_type"].astype(str).str.lower().str.contains("bear")]
        else:
            bull = pd.DataFrame()
            bear = pd.DataFrame()
        features["smc_fvg_bullish"] = _flag_dates(one, bull, "date")
        features["smc_fvg_bearish"] = _flag_dates(one, bear, "date")

    obs = ctx.get("order_blocks", pd.DataFrame())
    if isinstance(obs, pd.DataFrame) and not obs.empty:
        type_col = "bias" if "bias" in obs.columns else "ob_type" if "ob_type" in obs.columns else None
        if type_col:
            bull = obs[obs[type_col].astype(str).str.lower().str.contains("bull")]
            bear = obs[obs[type_col].astype(str).str.lower().str.contains("bear")]
            features["smc_order_block_bullish"] = _flag_dates(one, bull, "date")
            features["smc_order_block_bearish"] = _flag_dates(one, bear, "date")

    liq = ctx.get("liquidity", pd.DataFrame())
    if isinstance(liq, pd.DataFrame) and not liq.empty:
        features["smc_liquidity_nearby"] = _flag_dates(one, liq, "date")

    swings = ctx.get("swings", pd.DataFrame())
    if isinstance(swings, pd.DataFrame) and not swings.empty:
        type_col = "type" if "type" in swings.columns else None
        if type_col:
            features["smc_swing_high"] = _flag_dates(one, swings[swings[type_col].astype(str).str.lower().str.contains("high")], "date")
            features["smc_swing_low"] = _flag_dates(one, swings[swings[type_col].astype(str).str.lower().str.contains("low")], "date")

    events = ctx.get("structure_events", pd.DataFrame())
    if isinstance(events, pd.DataFrame) and not events.empty and "event_type" in events.columns:
        et = events["event_type"].astype(str).str.upper()
        features["smc_bos_up"] = _flag_dates(one, events[et.str.contains("BOS_UP")], "date")
        features["smc_bos_down"] = _flag_dates(one, events[et.str.contains("BOS_DOWN")], "date")
        features["smc_choch_up"] = _flag_dates(one, events[et.str.contains("CHOCH_UP")], "date")
        features["smc_choch_down"] = _flag_dates(one, events[et.str.contains("CHOCH_DOWN")], "date")
    return features.fillna(0).astype("int64")


def build_training_dataset(
    prices: pd.DataFrame,
    *,
    forward_days: int = 3,
    include_smc: bool = True,
    include_patterns: bool = True,
) -> pd.DataFrame:
    """Build per-day model-ready rows for future AI training.

    Each row contains only information known at that date plus forward targets such as
    `forward_return_3d` and `target_up_3d`. The dataset is meant for research/export;
    it does not train a model by itself.
    """
    if forward_days < 1:
        raise ValueError("forward_days must be positive")
    data = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    if data.empty:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for ticker, group in data.groupby("ticker", sort=False):
        one = add_indicators(group).sort_values("date").reset_index(drop=True)
        one["ticker"] = str(ticker)
        close = one["close"].astype(float)
        forward_return = close.shift(-forward_days) / close - 1
        one[f"forward_return_{forward_days}d"] = forward_return
        one[f"target_up_{forward_days}d"] = np.where(forward_return.notna(), (forward_return > 0).astype("int64"), np.nan)
        one[f"target_available_{forward_days}d"] = forward_return.notna().astype("int64")
        one[f"target_close_{forward_days}d"] = close.shift(-forward_days)
        one["trend_state_sma20_60"] = np.select(
            [one["close"] > one["sma_60"], one["close"] < one["sma_60"]],
            [1, -1],
            default=0,
        )
        one["macd_cross_up"] = ((one["macd"] > one["macd_signal"]) & (one["macd"].shift(1) <= one["macd_signal"].shift(1))).astype("int64")
        one["macd_cross_down"] = ((one["macd"] < one["macd_signal"]) & (one["macd"].shift(1) >= one["macd_signal"].shift(1))).astype("int64")
        one["kd_cross_up"] = ((one["stoch_k_14"] > one["stoch_d_3"]) & (one["stoch_k_14"].shift(1) <= one["stoch_d_3"].shift(1))).astype("int64")
        one["kd_cross_down"] = ((one["stoch_k_14"] < one["stoch_d_3"]) & (one["stoch_k_14"].shift(1) >= one["stoch_d_3"].shift(1))).astype("int64")
        one["near_support_20"] = ((one["close"] - one["support_20"]).abs() / one["close"].replace(0, np.nan) < 0.02).astype("int64")
        one["near_resistance_20"] = ((one["resistance_20"] - one["close"]).abs() / one["close"].replace(0, np.nan) < 0.02).astype("int64")
        try:
            ukf = compute_ukf_momentum_state(one)
            for col in ["ukf_momentum", "ukf_velocity", "raw_momentum"]:
                if col in ukf.columns:
                    one[col] = ukf[col].values
        except Exception:
            one["ukf_momentum"] = 0.0
            one["ukf_velocity"] = 0.0
            one["raw_momentum"] = 0.0
        if include_patterns:
            patterns = detect_candlestick_patterns(one)
            one["candle_doji"] = 0
            one["candle_bullish_engulfing"] = 0
            one["candle_bearish_engulfing"] = 0
            if not patterns.empty:
                pat_dates = pd.to_datetime(patterns["date"]).dt.normalize()
                base_dates = pd.to_datetime(one["date"]).dt.normalize()
                for pattern, col in [
                    ("DOJI", "candle_doji"),
                    ("BULLISH_ENGULFING", "candle_bullish_engulfing"),
                    ("BEARISH_ENGULFING", "candle_bearish_engulfing"),
                ]:
                    dates = pat_dates[patterns["pattern"].astype(str).str.upper().eq(pattern)]
                    one[col] = base_dates.isin(set(dates)).astype("int64")
        if include_smc:
            one = pd.concat([one, _smc_features_for_ticker(one)], axis=1)
        frames.append(one)
    out = pd.concat(frames, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    numeric = out.select_dtypes(include=[np.number]).columns
    target_cols = [c for c in out.columns if c.startswith("target_") or c.startswith("forward_return_")]
    feature_numeric = [c for c in numeric if c not in target_cols]
    out[feature_numeric] = out.groupby("ticker", group_keys=False)[feature_numeric].ffill().bfill().fillna(0.0)
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def compute_top_training_features(dataset: pd.DataFrame, *, target_col: str = "forward_return_3d", top_n: int = 20) -> pd.DataFrame:
    """Rank columns by absolute Spearman/Pearson relationship to the forward target."""
    if dataset.empty or target_col not in dataset.columns:
        return pd.DataFrame(columns=["feature", "pearson_corr", "spearman_corr", "abs_score", "non_null_ratio"])
    target = pd.to_numeric(dataset[target_col], errors="coerce")
    rows: list[dict[str, object]] = []
    ignored = {"date", "ticker", target_col, target_col.replace("forward_return", "target_close")}
    for col in dataset.columns:
        if col in ignored or col.startswith("target_"):
            continue
        series = pd.to_numeric(dataset[col], errors="coerce")
        if series.notna().sum() < 10 or series.nunique(dropna=True) <= 1:
            continue
        pearson = float(series.corr(target)) if target.notna().sum() >= 10 else 0.0
        spearman = float(series.corr(target, method="spearman")) if target.notna().sum() >= 10 else 0.0
        pearson = 0.0 if not np.isfinite(pearson) else pearson
        spearman = 0.0 if not np.isfinite(spearman) else spearman
        rows.append(
            {
                "feature": col,
                "pearson_corr": pearson,
                "spearman_corr": spearman,
                "abs_score": max(abs(pearson), abs(spearman)),
                "non_null_ratio": float(series.notna().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("abs_score", ascending=False).head(top_n).reset_index(drop=True)
