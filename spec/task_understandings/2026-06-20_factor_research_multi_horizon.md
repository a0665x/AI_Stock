# 2026-06-20 Factor Research Multi-Horizon Comparison

## Request
User asked to extend the Docker Streamlit factor research tab so it can compare future 1/3/5/10 day horizons rather than only one selected horizon.

## Changes
- Added `build_factor_horizon_comparison()` in `src/ai_stock/factor_research.py`.
- Each horizon is trained independently, then tables are concatenated with `horizon`, `window`, and `target_threshold` columns preserved.
- Added horizon metadata to y heatmap and sample tables.
- Updated Streamlit sidebar from single `factor_horizon` slider to a multiselect defaulting to `[1, 3, 5, 10]`.
- Updated factor tab to:
  - run “執行多 horizon 因子研究” only when user clicks the button,
  - show multi-horizon model summary,
  - select ticker and horizon for detailed importance/correlation/grouped-win/y-heat views,
  - download multi-horizon factor importance CSV.
- Updated README and spec quickstart docs.

## Verification
- Local targeted TDD test: `pytest tests/test_factor_research.py::test_factor_horizon_comparison_runs_multiple_future_windows_and_preserves_horizon_columns -q` passed.
- Local full suite: `pytest -q` passed with 15 tests.
- Smoke test with AAPL/MSFT/NVDA 1y daily data produced horizons `[1, 3, 5, 10]` across summary, importance, correlations, grouped win rates, y heatmap, and samples.
- Docker image rebuilt; `./run.sh test` passed with 15 tests.
- Docker UI restarted with `./run.sh down_up`; health endpoint returned `ok`.
- Browser inspection confirmed sidebar has “比較預測天數 horizon” with default 1/3/5/10 and DOM contains “執行多 horizon 因子研究”.

## Notes
- Multi-horizon SHAP can be heavier than single horizon, so it remains button-triggered rather than automatic on tab/sidebar changes.
- Existing old `runtime/market_cache` may still be root-owned from earlier Docker runs; Docker Compose now uses `docker_runtime/market_cache` for the active container path.
