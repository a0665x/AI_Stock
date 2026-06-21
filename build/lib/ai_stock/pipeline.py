from __future__ import annotations

import pandas as pd

from .analytics import compute_correlation_table, compute_latest_technical_snapshot
from .data_sources import DataRequest, load_history, normalize_ohlcv
from .forecasting import build_decision_report


def analyze_prices(prices: pd.DataFrame, horizon: int = 5) -> dict[str, pd.DataFrame]:
    normalized = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    return {
        "prices": normalized,
        "technical_snapshot": compute_latest_technical_snapshot(normalized),
        "correlations": compute_correlation_table(normalized),
        "decision_report": build_decision_report(normalized, horizon=horizon),
    }


def analyze_tickers(tickers: list[str], period: str = "1y", interval: str = "1d", horizon: int = 5) -> dict[str, pd.DataFrame]:
    prices = load_history(DataRequest(tuple(tickers), period=period, interval=interval, provider="yfinance"))
    return analyze_prices(prices, horizon=horizon)
