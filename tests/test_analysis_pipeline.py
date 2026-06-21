from pathlib import Path

import numpy as np
import pandas as pd

from ai_stock.analytics import compute_correlation_table, compute_latest_technical_snapshot, compute_relationship_pressure
from ai_stock.attribution import build_attribution_report
from ai_stock.backtesting import compare_backtest_scenarios, run_backtest
from ai_stock.data_sources import clear_yfinance_disk_cache, fetch_yfinance_history, normalize_ohlcv
from ai_stock.forecasting import build_decision_report


def _price_frame(close, ticker="AAA"):
    idx = pd.date_range("2024-01-01", periods=len(close), freq="D")
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "date": idx,
            "ticker": ticker,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.linspace(1000, 2000, len(close)),
        }
    )


def test_normalize_ohlcv_accepts_chinese_schema():
    raw = pd.DataFrame(
        {
            "日期": pd.date_range("2024-01-01", periods=2),
            "代號": ["2330", "2330"],
            "開盤": [100, 101],
            "最高": [102, 103],
            "最低": [99, 100],
            "收盤": [101, 102],
            "成交股數": [1000, 1100],
        }
    )

    out = normalize_ohlcv(raw)

    assert list(out.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]
    assert out["ticker"].tolist() == ["2330", "2330"]
    assert out["close"].tolist() == [101.0, 102.0]


def test_correlation_table_reports_pairwise_return_relationships():
    a = _price_frame([100, 110, 100, 110, 100], "AAA")
    b = _price_frame([100, 90, 100, 90, 100], "BBB")
    table = compute_correlation_table(pd.concat([a, b], ignore_index=True))

    row = table.iloc[0]
    assert {row["ticker_a"], row["ticker_b"]} == {"AAA", "BBB"}
    assert row["return_corr"] < -0.9
    assert row["observations"] == 4


def test_latest_technical_snapshot_contains_actionable_indicators():
    prices = _price_frame(np.linspace(100, 130, 90), "AAA")

    snapshot = compute_latest_technical_snapshot(prices)

    row = snapshot.iloc[0]
    assert row["ticker"] == "AAA"
    assert row["last_close"] == 130
    assert "rsi_14" in snapshot.columns
    assert "macd_hist" in snapshot.columns
    assert "volatility_20d" in snapshot.columns
    assert "bb_position_20" in snapshot.columns
    assert "atr_pct_14" in snapshot.columns
    assert "stoch_k_14" in snapshot.columns
    assert "mfi_14" in snapshot.columns
    assert "max_drawdown_60d" in snapshot.columns


def test_decision_report_produces_buy_sell_levels_and_kelly_fraction():
    prices = _price_frame(np.linspace(100, 130, 180), "AAA")

    report = build_decision_report(prices, horizon=5)

    row = report.iloc[0]
    assert row["ticker"] == "AAA"
    assert row["model"] in {"arima", "linear_regression"}
    assert row["suggested_buy_price"] <= row["last_close"]
    assert row["suggested_sell_price"] >= row["last_close"]
    assert 0.0 <= row["kelly_fraction"] <= 1.0
    assert "risk_unit_pct" in report.columns
    assert "max_drawdown_60d_pct" in report.columns
    assert "relationship_adjusted_return_pct" in report.columns
    assert "kelly_reason" in report.columns
    assert "action_reason" in report.columns
    assert isinstance(row["kelly_reason"], str)
    assert isinstance(row["action_reason"], str)
    assert "預估" in row["action_reason"]


def test_decision_report_explains_zero_kelly_and_hold_wait():
    flat = 100 + np.sin(np.arange(220) / 3) * 0.1
    prices = _price_frame(flat, "AAA")

    report = build_decision_report(prices, horizon=5)

    row = report.iloc[0]
    assert row["action"] == "HOLD_WAIT"
    assert row["kelly_fraction"] == 0.0
    assert "Kelly 為 0" in row["kelly_reason"]
    assert "等待確認" in row["action_reason"]
    assert "門檻" in row["action_reason"]


def test_streamlit_decision_table_surfaces_kelly_and_action_reason_columns():
    app_source = Path(__file__).resolve().parents[1].joinpath("src", "ai_stock", "app.py").read_text(encoding="utf-8")

    assert "Kelly / 決策原因" in app_source
    assert "Kelly 原因" in app_source
    assert "決策原因" in app_source
    assert "為什麼 Kelly 可能是 0.0%？" in app_source


def test_relationship_pressure_uses_positive_and_negative_peer_context():
    a = _price_frame(np.linspace(100, 120, 90), "AAA")
    b = _price_frame(np.linspace(80, 100, 90), "BBB")
    c = _price_frame(np.linspace(100, 80, 90), "CCC")
    prices = pd.concat([a, b, c], ignore_index=True)
    corr = compute_correlation_table(prices)

    pressure = compute_relationship_pressure(prices, corr)

    row = pressure[pressure["ticker"] == "AAA"].iloc[0]
    assert row["peer_count"] >= 2
    assert "positive_corr_pressure_5d" in pressure.columns
    assert "negative_corr_pressure_5d" in pressure.columns


def test_attribution_report_produces_signed_feature_rows():
    base = np.linspace(100, 140, 240) + np.sin(np.arange(240) / 3) * 2
    prices = _price_frame(base, "AAA")

    attribution = build_attribution_report(prices, horizon=5, top_n=5)

    assert not attribution.empty
    assert attribution["ticker"].eq("AAA").all()
    assert set(["feature_label", "contribution", "method", "direction"]).issubset(attribution.columns)
    assert attribution["method"].str.len().gt(0).all()


def test_backtest_reports_win_rate_drawdown_stop_hits_and_cumulative_return():
    trend = np.linspace(100, 150, 260) + np.sin(np.arange(260) / 4) * 3
    prices = _price_frame(trend, "AAA")

    result = run_backtest(prices, horizon=5, lookback=90, step=5)

    summary = result.summary.iloc[0]
    assert summary["ticker"] == "AAA"
    assert summary["trades"] > 5
    assert 0.0 <= summary["win_rate"] <= 1.0
    assert summary["max_drawdown"] <= 0.0
    assert 0.0 <= summary["stop_loss_hit_rate"] <= 1.0
    assert "cumulative_return" in result.equity_curve.columns
    assert result.equity_curve["cumulative_return"].iloc[-1] > -1.0
    assert set(["entry_date", "exit_date", "entry_price", "exit_price", "return_pct", "stop_hit"]).issubset(result.trades.columns)


def test_backtest_compares_holding_periods_and_exit_rules():
    trend = np.linspace(100, 160, 320) + np.sin(np.arange(320) / 5) * 4
    prices = _price_frame(trend, "AAA")

    comparison = compare_backtest_scenarios(
        prices,
        horizons=[3, 5, 10],
        exit_rules=["time", "stop_loss", "trailing_stop"],
        lookback=90,
        only_buy_watch=False,
    )

    assert not comparison.empty
    assert set(comparison["holding_days"]) == {3, 5, 10}
    assert set(comparison["exit_rule"]) == {"time", "stop_loss", "trailing_stop"}
    assert set(["ticker", "strategy", "win_rate", "max_drawdown", "stop_loss_hit_rate", "cumulative_return", "trades"]).issubset(comparison.columns)
    assert comparison["strategy"].str.contains("天").all()
    assert comparison["trades"].gt(0).any()


def test_streamlit_shap_analysis_is_button_triggered_not_sidebar_toggle():
    app_source = Path(__file__).resolve().parents[1].joinpath("src", "ai_stock", "app.py").read_text(encoding="utf-8")

    assert "執行 SHAP 歸因分析" in app_source
    assert "shap_attribution" in app_source
    assert "啟用 SHAP 歸因計算" not in app_source
    assert "enable_attribution" not in app_source


def test_streamlit_yfinance_fetch_is_cached_until_manual_refresh():
    app_source = Path(__file__).resolve().parents[1].joinpath("src", "ai_stock", "app.py").read_text(encoding="utf-8")

    assert "YFINANCE_CACHE_TTL_SECONDS" in app_source
    assert "@st.cache_data(ttl=YFINANCE_CACHE_TTL_SECONDS" in app_source
    assert "_clear_cached_market_data" in app_source
    assert "_load_yf.clear()" in app_source
    assert "行情資料已快取" in app_source


def test_yfinance_history_uses_persistent_disk_cache(tmp_path, monkeypatch):
    calls = {"count": 0}
    expected = _price_frame([100, 101, 102], "AAA")

    def fake_download(tickers, period="1y", interval="1d"):
        calls["count"] += 1
        return expected.copy()

    monkeypatch.setenv("AI_STOCK_MARKET_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("ai_stock.data_sources._download_yfinance_history", fake_download)

    first = fetch_yfinance_history(["AAA"], period="1y", interval="1d")
    second = fetch_yfinance_history(["AAA"], period="1y", interval="1d")

    assert calls["count"] == 1
    pd.testing.assert_frame_equal(first, second)
    assert any(tmp_path.glob("*.pkl"))

    clear_yfinance_disk_cache(cache_dir=tmp_path)
    fetch_yfinance_history(["AAA"], period="1y", interval="1d")

    assert calls["count"] == 2
