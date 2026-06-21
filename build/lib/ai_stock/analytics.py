from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .data_sources import normalize_ohlcv


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(group: pd.DataFrame) -> pd.DataFrame:
    g = group.sort_values("date").copy()
    close = g["close"]
    g["return_1d"] = close.pct_change()
    for window in [5, 10, 20, 60]:
        g[f"sma_{window}"] = close.rolling(window).mean()
        g[f"return_{window}d"] = close.pct_change(window)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    g["macd"] = ema12 - ema26
    g["macd_signal"] = g["macd"].ewm(span=9, adjust=False).mean()
    g["macd_hist"] = g["macd"] - g["macd_signal"]
    g["rsi_14"] = _rsi(close, 14)
    g["volatility_20d"] = g["return_1d"].rolling(20).std() * np.sqrt(252)
    g["volume_ratio_20d"] = g["volume"] / g["volume"].rolling(20).mean()
    return g


def compute_latest_technical_snapshot(prices: pd.DataFrame) -> pd.DataFrame:
    data = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    enriched = data.groupby("ticker", group_keys=False).apply(add_indicators, include_groups=False)
    # pandas include_groups=False drops ticker from grouped chunk; restore from original index alignment when needed.
    if "ticker" not in enriched.columns:
        enriched = data[["ticker"]].join(enriched)
    latest = enriched.sort_values("date").groupby("ticker", as_index=False).tail(1).copy()
    latest["last_close"] = latest["close"]
    columns = [
        "ticker",
        "date",
        "last_close",
        "return_1d",
        "return_5d",
        "return_20d",
        "sma_20",
        "sma_60",
        "rsi_14",
        "macd_hist",
        "volatility_20d",
        "volume_ratio_20d",
    ]
    return latest[[c for c in columns if c in latest.columns]].reset_index(drop=True)


def compute_correlation_table(prices: pd.DataFrame) -> pd.DataFrame:
    data = prices.copy().sort_values(["ticker", "date"])
    data["ret"] = data.groupby("ticker")["close"].pct_change()
    wide = data.pivot(index="date", columns="ticker", values="ret")
    rows = []
    for a, b in itertools.combinations(wide.columns, 2):
        pair = wide[[a, b]].dropna()
        if pair.empty:
            continue
        rows.append(
            {
                "ticker_a": a,
                "ticker_b": b,
                "return_corr": float(pair[a].corr(pair[b])),
                "observations": int(len(pair)),
            }
        )
    return pd.DataFrame(rows).sort_values("return_corr", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(
        columns=["ticker_a", "ticker_b", "return_corr", "observations"]
    )
