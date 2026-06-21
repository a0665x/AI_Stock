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
    high = g["high"]
    low = g["low"]
    volume = g["volume"]
    g["return_1d"] = close.pct_change()
    for window in [5, 10, 20, 60]:
        g[f"sma_{window}"] = close.rolling(window).mean()
        g[f"ema_{window}"] = close.ewm(span=window, adjust=False).mean()
        g[f"return_{window}d"] = close.pct_change(window)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    g["macd"] = ema12 - ema26
    g["macd_signal"] = g["macd"].ewm(span=9, adjust=False).mean()
    g["macd_hist"] = g["macd"] - g["macd_signal"]
    g["rsi_14"] = _rsi(close, 14)

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    g["bb_upper_20"] = sma20 + 2 * std20
    g["bb_lower_20"] = sma20 - 2 * std20
    g["bb_position_20"] = (close - g["bb_lower_20"]) / (g["bb_upper_20"] - g["bb_lower_20"])

    prev_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    g["atr_14"] = true_range.rolling(14).mean()
    g["atr_pct_14"] = g["atr_14"] / close

    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    g["stoch_k_14"] = 100 * (close - low14) / (high14 - low14)
    g["stoch_d_3"] = g["stoch_k_14"].rolling(3).mean()

    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    tp_delta = typical_price.diff()
    positive_flow = money_flow.where(tp_delta > 0, 0.0).rolling(14).sum()
    negative_flow = money_flow.where(tp_delta < 0, 0.0).rolling(14).sum().abs()
    money_ratio = positive_flow / negative_flow.replace(0, np.nan)
    g["mfi_14"] = 100 - 100 / (1 + money_ratio)

    direction = np.sign(close.diff()).fillna(0)
    g["obv"] = (direction * volume).cumsum()
    g["volatility_20d"] = g["return_1d"].rolling(20).std() * np.sqrt(252)
    g["volume_ratio_20d"] = volume / volume.rolling(20).mean()
    g["distance_sma20"] = close / g["sma_20"] - 1
    g["distance_sma60"] = close / g["sma_60"] - 1
    rolling_high_60 = close.rolling(60).max()
    g["drawdown_from_60d_high"] = close / rolling_high_60 - 1
    g["max_drawdown_60d"] = (close / close.rolling(60).max() - 1).rolling(60).min()
    g["support_20"] = low.rolling(20).min()
    g["resistance_20"] = high.rolling(20).max()
    return g


def compute_latest_technical_snapshot(prices: pd.DataFrame) -> pd.DataFrame:
    data = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    enriched = pd.concat(
        [add_indicators(group) for _, group in data.groupby("ticker", sort=False)],
        ignore_index=True,
    )
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
        "ema_20",
        "ema_60",
        "rsi_14",
        "macd_hist",
        "bb_position_20",
        "atr_pct_14",
        "stoch_k_14",
        "stoch_d_3",
        "mfi_14",
        "volatility_20d",
        "volume_ratio_20d",
        "drawdown_from_60d_high",
        "max_drawdown_60d",
        "support_20",
        "resistance_20",
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


def compute_relationship_pressure(prices: pd.DataFrame, correlations: pd.DataFrame | None = None, window: int = 5) -> pd.DataFrame:
    """Summarize how peer returns may pressure each ticker.

    Positive-correlation pressure rises when stocks that usually move together are up.
    Negative-correlation pressure rises when inverse peers are down. This is not a
    causal claim; it is a decision-report context signal used beside drawdown/SHAP.
    """
    if correlations is None:
        correlations = compute_correlation_table(prices)
    tickers = sorted(prices["ticker"].unique())
    if not tickers:
        return pd.DataFrame()
    latest_returns = (
        prices.sort_values(["ticker", "date"])
        .groupby("ticker")
        .apply(lambda g: g["close"].iloc[-1] / g["close"].iloc[max(0, len(g) - window - 1)] - 1, include_groups=False)
        .to_dict()
    )
    rows = []
    for ticker in tickers:
        pos_terms: list[float] = []
        neg_terms: list[float] = []
        for _, row in correlations.iterrows():
            a = row["ticker_a"]
            b = row["ticker_b"]
            corr = float(row["return_corr"])
            if ticker not in {a, b} or not np.isfinite(corr):
                continue
            peer = b if ticker == a else a
            peer_ret = float(latest_returns.get(peer, np.nan))
            if not np.isfinite(peer_ret):
                continue
            if corr >= 0:
                pos_terms.append(corr * peer_ret)
            else:
                neg_terms.append(abs(corr) * (-peer_ret))
        pos_pressure = float(np.nanmean(pos_terms)) if pos_terms else 0.0
        neg_pressure = float(np.nanmean(neg_terms)) if neg_terms else 0.0
        rows.append(
            {
                "ticker": ticker,
                "relationship_pressure_5d": pos_pressure + neg_pressure,
                "positive_corr_pressure_5d": pos_pressure,
                "negative_corr_pressure_5d": neg_pressure,
                "peer_count": int(len(pos_terms) + len(neg_terms)),
            }
        )
    return pd.DataFrame(rows)
