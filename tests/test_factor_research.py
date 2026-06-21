from pathlib import Path

import numpy as np
import pandas as pd

from ai_stock.factor_research import (
    build_factor_horizon_comparison,
    build_factor_research_report,
    build_horizon_metric_trends,
    build_sliding_window_dataset,
    build_ticker_horizon_metric_matrix,
)


def _price_frame(close, ticker="AAA"):
    idx = pd.date_range("2024-01-01", periods=len(close), freq="D")
    close = np.asarray(close, dtype=float)
    open_ = close * (1 + np.sin(np.arange(len(close)) / 5) * 0.002)
    high = np.maximum(open_, close) * 1.012
    low = np.minimum(open_, close) * 0.988
    volume = 1000 + np.arange(len(close)) * 5 + (np.sin(np.arange(len(close)) / 3) * 120)
    return pd.DataFrame(
        {
            "date": idx,
            "ticker": ticker,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_sliding_window_dataset_uses_past_seven_days_to_label_next_day_direction():
    close = [100, 101, 102, 103, 104, 105, 106, 108, 107, 109, 111, 110]
    prices = _price_frame(close, "AAA")

    dataset = build_sliding_window_dataset(prices, window=7, horizon=1, min_samples_per_ticker=1)

    assert not dataset.X.empty
    assert len(dataset.X) == len(close) - 7
    assert dataset.y_direction.tolist()[0] == 1
    assert dataset.y_return.iloc[0] == (108 / 106) - 1
    assert dataset.meta.iloc[0]["target_date"] == pd.Timestamp("2024-01-08")
    assert {"close_return_lag_1", "rsi_14_lag_1", "macd_hist_lag_1", "stoch_k_14_lag_1", "candle_body_pct_lag_1"}.issubset(dataset.X.columns)
    assert "close_return_lag_8" not in dataset.X.columns


def test_factor_research_report_explains_direction_model_with_importance_correlation_groups_and_heatmap():
    days = np.arange(260)
    close_a = 100 + days * 0.18 + np.sin(days / 4) * 3 + np.where((days % 17) < 8, 1.2, -1.2)
    close_b = 80 + days * 0.06 + np.cos(days / 5) * 2.5 + np.where((days % 19) < 9, -1.0, 1.0)
    prices = pd.concat([_price_frame(close_a, "AAA"), _price_frame(close_b, "BBB")], ignore_index=True)

    report = build_factor_research_report(prices, window=7, horizon=1, model_type="gradient_boosting", top_n=12)

    assert not report.summary.empty
    assert set(["ticker", "samples", "baseline_up_rate", "accuracy", "auc", "model", "method"]).issubset(report.summary.columns)
    assert report.summary["samples"].ge(40).all()
    assert report.summary["accuracy"].between(0, 1).all()

    assert not report.importance.empty
    assert set(["ticker", "feature", "feature_label", "importance", "signed_contribution", "direction", "method"]).issubset(report.importance.columns)
    assert report.importance["importance"].ge(0).all()

    assert not report.correlations.empty
    assert set(["ticker", "feature", "spearman_corr", "pearson_corr", "mutual_info"]).issubset(report.correlations.columns)

    assert not report.grouped_win_rates.empty
    assert set(["ticker", "feature", "bucket", "samples", "up_rate", "avg_forward_return"]).issubset(report.grouped_win_rates.columns)

    assert not report.y_heatmap.empty
    assert set(["ticker", "date", "target_date", "forward_return", "direction", "return_bucket"]).issubset(report.y_heatmap.columns)


def test_factor_horizon_comparison_runs_multiple_future_windows_and_preserves_horizon_columns():
    days = np.arange(260)
    close_a = 100 + days * 0.16 + np.sin(days / 4) * 3 + np.where((days % 17) < 8, 1.2, -1.2)
    close_b = 80 + days * 0.05 + np.cos(days / 5) * 2.5 + np.where((days % 19) < 9, -1.0, 1.0)
    prices = pd.concat([_price_frame(close_a, "AAA"), _price_frame(close_b, "BBB")], ignore_index=True)

    comparison = build_factor_horizon_comparison(
        prices,
        window=7,
        horizons=[1, 3, 5, 10],
        model_type="gradient_boosting",
        top_n=8,
        min_samples_per_ticker=35,
    )

    assert set(comparison.keys()) == {"summary", "importance", "correlations", "grouped_win_rates", "y_heatmap", "samples"}
    assert set(comparison["summary"]["horizon"]) == {1, 3, 5, 10}
    assert set(comparison["importance"]["horizon"]) == {1, 3, 5, 10}
    assert set(comparison["y_heatmap"]["horizon"]) == {1, 3, 5, 10}
    assert comparison["summary"]["accuracy"].between(0, 1).all()
    assert comparison["summary"].groupby("ticker")["horizon"].nunique().ge(2).all()


def test_horizon_metric_trends_aggregates_accuracy_auc_and_win_rate_by_future_window():
    summary = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "AAA", "BBB", "AAA", "BBB"],
            "horizon": [1, 1, 3, 3, 5, 5],
            "accuracy": [0.55, 0.65, 0.50, 0.60, 0.45, 0.55],
            "auc": [0.52, 0.62, 0.51, 0.57, np.nan, 0.54],
            "baseline_up_rate": [0.48, 0.52, 0.47, 0.51, 0.46, 0.50],
            "samples": [100, 100, 95, 95, 90, 90],
        }
    )

    trends = build_horizon_metric_trends(summary)

    assert trends["horizon"].tolist() == [1, 3, 5]
    assert trends.loc[trends["horizon"] == 1, "accuracy"].iloc[0] == 0.60
    assert trends.loc[trends["horizon"] == 3, "auc"].iloc[0] == 0.54
    assert trends.loc[trends["horizon"] == 5, "ticker_count"].iloc[0] == 2
    assert set(["horizon", "accuracy", "auc", "baseline_up_rate", "sample_count", "ticker_count"]).issubset(trends.columns)


def test_ticker_horizon_metric_matrix_pivots_each_stock_by_future_window_for_heatmaps():
    summary = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "AAA", "BBB", "AAA", "BBB"],
            "horizon": [1, 1, 3, 3, 5, 5],
            "accuracy": [0.55, 0.65, 0.50, 0.60, 0.45, 0.55],
            "auc": [0.52, 0.62, 0.51, 0.57, np.nan, 0.54],
            "baseline_up_rate": [0.48, 0.52, 0.47, 0.51, 0.46, 0.50],
            "samples": [100, 100, 95, 95, 90, 90],
        }
    )

    matrix = build_ticker_horizon_metric_matrix(summary, metric="accuracy")

    assert matrix.index.tolist() == ["AAA", "BBB"]
    assert matrix.columns.tolist() == [1, 3, 5]
    assert matrix.loc["AAA", 1] == 0.55
    assert matrix.loc["BBB", 5] == 0.55


def test_factor_research_tab_is_button_triggered_in_streamlit_app():
    app_source = Path(__file__).resolve().parents[1].joinpath("src", "ai_stock", "app.py").read_text(encoding="utf-8")

    assert "因子研究" in app_source
    assert "執行因子研究" in app_source
    assert "build_factor_research_report" in app_source
    assert "factor_research_report" in app_source
    assert "勝率與 AUC 趨勢" in app_source
    assert "每檔股票 × horizon 表現熱力圖" in app_source
    assert "build_ticker_horizon_metric_matrix" in app_source
    assert "熱力圖指標" in app_source
    assert "build_horizon_metric_trends" in app_source
    assert "sliding window" in app_source
