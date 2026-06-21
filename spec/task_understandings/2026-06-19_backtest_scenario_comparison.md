# Backtest Scenario Comparison

## User request
Add comparison across different holding periods and exit rules in the Streamlit backtest tab.

## Implemented
- `src/ai_stock/backtesting.py`
  - Added `exit_rule` support to `run_backtest()`:
    - `time`: exit at the end of the holding window.
    - `stop_loss`: exit early if forward low hits stop-loss, otherwise time exit.
    - `trailing_stop`: exit if price falls from post-entry peak by configured trailing-stop percentage, otherwise time exit.
  - Added trade columns: `exit_rule`, `exit_reason`, `holding_days`.
  - Added summary columns: `time_exit_rate`, `trailing_stop_hit_rate`, `holding_days`, `exit_rule`, `strategy`.
  - Added `compare_backtest_scenarios()` for grid comparison over holding days and exit rules.

- `src/ai_stock/app.py`
  - Sidebar now has a manual toggle: `啟用持有天數 / 出場規則比較`.
  - Supports selecting holding periods: 3, 5, 10, 20, 30 days.
  - Supports selecting exit rules: 時間出場, 停損優先, 移動停損.
  - Supports configurable trailing-stop percentage.
  - Backtest tab now includes:
    - scenario comparison chart ranked by cumulative return.
    - scenario comparison table.
    - CSV export for comparison.
  - Comparison is off by default to keep initial Streamlit load responsive.

## Verification
- TDD RED first: added `test_backtest_compares_holding_periods_and_exit_rules`, confirmed import failure because `compare_backtest_scenarios` did not exist.
- GREEN: implemented scenario comparison and exit-rule logic.
- Test result: `pytest -q` => 8 passed.
- Compile result: `python -m compileall src tests` => passed.
- Smoke test with yfinance AAPL/MSFT/NVDA 1y:
  - prices: (753, 7)
  - base_summary: (3, 13)
  - base_trades: (78, 14)
  - scenario_comparison: (27, 13)
- Streamlit health check: `ok` at http://127.0.0.1:8507/_stcore/health.
- Browser check confirmed sidebar toggle and backtest tab section are visible.
