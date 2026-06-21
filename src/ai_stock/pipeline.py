from __future__ import annotations

import pandas as pd

from .analytics import compute_correlation_table, compute_latest_technical_snapshot, compute_relationship_pressure
from .attribution import build_attribution_report
from .backtesting import run_backtest
from .data_sources import DataRequest, load_history, normalize_ohlcv
from .forecasting import build_decision_report
from .factor_research import build_factor_research_report


def analyze_prices(prices: pd.DataFrame, horizon: int = 5) -> dict[str, pd.DataFrame]:
    normalized = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    correlations = compute_correlation_table(normalized)
    backtest = run_backtest(normalized, horizon=horizon, lookback=120, step=horizon)
    factor_report = build_factor_research_report(normalized, window=7, horizon=1, top_n=12)
    return {
        "prices": normalized,
        "technical_snapshot": compute_latest_technical_snapshot(normalized),
        "correlations": correlations,
        "relationship_pressure": compute_relationship_pressure(normalized, correlations),
        "decision_report": build_decision_report(normalized, horizon=horizon),
        "attribution_report": build_attribution_report(normalized, horizon=horizon),
        "backtest_summary": backtest.summary,
        "backtest_trades": backtest.trades,
        "backtest_equity_curve": backtest.equity_curve,
        "factor_summary": factor_report.summary,
        "factor_importance": factor_report.importance,
        "factor_correlations": factor_report.correlations,
        "factor_grouped_win_rates": factor_report.grouped_win_rates,
        "factor_y_heatmap": factor_report.y_heatmap,
    }


def analyze_tickers(tickers: list[str], period: str = "1y", interval: str = "1d", horizon: int = 5) -> dict[str, pd.DataFrame]:
    prices = load_history(DataRequest(tuple(tickers), period=period, interval=interval, provider="yfinance"))
    return analyze_prices(prices, horizon=horizon)
