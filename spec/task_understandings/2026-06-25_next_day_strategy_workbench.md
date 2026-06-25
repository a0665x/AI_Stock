# Task Understanding: Next-Day Strategy Workbench

Date: 2026-06-25

## User request

The user observed that decision fields often show `等待確認` and Kelly is frequently 0.0%, even though stocks still move. They asked for a richer next-day strategy workflow:

- Do not rely on Kelly alone.
- Let the user choose one ticker or all tickers first.
- Let the user set risk tolerance, default 10%.
- Let the user choose a common calculation horizon: 1/5/10/15/30 days.
- Let the user choose strategy families: Bollinger, SMC, UKF momentum, KD/MACD, SHAP/factor-like decision.
- Let the user choose backtest range: previous 1 week / 2 weeks / 1 month / 3 months / half year / 1 year.
- Run backtest after pressing a button.
- Output strategy win rate/suitability and then derive the most intuitive buy/sell limit zone.
- Separate analysis/report pages from direct prediction/action pages.

## Implementation

Added a new actionable tab:

- `隔日策略工作台`

Added module:

- `src/ai_stock/order_strategy_workbench.py`

Main public API:

- `filter_backtest_window()`
- `build_order_strategy_workbench()`

Supported strategy families:

- `bollinger` / 布林決策
- `smc` / SMC 決策
- `ukf` / UKF 動能決策
- `kd_macd` / KD/MACD 決策
- `shap_factor` / SHAP 因子代理決策

The new tab exposes layered controls:

1. `策略工作台股票範圍`: all tickers or selected tickers.
2. `工作台持有天數`: 1/5/10/15/30 days.
3. `風險耐受度%`: slider, default 10%.
4. `工作台回測期間`: 1周/2周/1個月/3個月/半年/1年.
5. `策略欄位`: multiselect checkboxes for discrete strategy families.
6. `啟動隔日策略回測`: explicit button; no eager global computation.

Outputs:

- `策略勝率 / 股性適配表`
- `最佳掛單區間`
- CSV download for workbench recommendations.

## Design decisions

### Kelly remains informational

Kelly still appears elsewhere as a conservative sizing guardrail, but the workbench does not require Kelly > 0 to produce an actionable next-day analysis.

### Checkboxes vs sliders

Strategy families are discrete methods, so they use multiselect/checkbox semantics. Risk tolerance is continuous, so it uses a slider.

### Button-triggered computation

The strategy grid is not run during global page load. It is only run after the user presses `啟動隔日策略回測`, then cached in Streamlit session state.

### SHAP strategy is a proxy for now

The workbench uses a lightweight factor proxy instead of running full SHAP in the interactive button path. It uses 5-day return, 20-day return, MACD histogram, and volume ratio. Future work can connect precomputed factor/SHAP results from the factor research page.

## Verification

Local smoke test with current holdings subset:

- NVDA best strategy: bollinger, BUY side, urgency score produced.
- TSLA best strategy: shap_factor, SELL side, urgency score produced.

Local tests:

- 76 passed

New tests:

- `tests/test_order_strategy_workbench.py`
- `tests/test_next_day_strategy_workbench_ui_source.py`

## Follow-up ideas

- Add direct integration from factor research SHAP importance cache into `shap_factor` strategy.
- Add per-strategy equity curves in the workbench.
- Add color-styled BUY/SELL urgency table similar to the existing next-day order heatmap.
- Move analysis-only tabs into an `分析報表` group if Streamlit navigation is later refactored into pages.
