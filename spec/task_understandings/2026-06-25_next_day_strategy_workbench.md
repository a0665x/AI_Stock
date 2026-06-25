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
- `build_strategy_visualization_payload()`

Supported strategy families:

- `bollinger` / 布林決策
- `smc` / SMC 決策
- `ukf` / UKF 動能決策
- `kd_macd` / KD/MACD 決策
- `shap_factor` / SHAP 因子代理決策

The new tab exposes layered controls with user-facing labels:

1. `要驗證哪些股票`: all tickers or selected tickers.
2. `預計持有天數`: 1/5/10/15/30 days.
3. `可承受停損幅度%`: slider, default 10%.
4. `用多久歷史驗證`: 1周/2周/1個月/3個月/半年/1年.
5. `選擇策略`: multiselect checkboxes for discrete strategy families.
6. `啟動隔日策略回測`: explicit button; no eager global computation.

Outputs:

- `策略勝率 / 股性適配表`
- `最佳掛單區間`
- `策略買賣點與績效曲線`
- `策略績效摘要`
- CSV download for workbench recommendations.

Strategy visualization follow-up added:

- `策略視覺化股票` dropdown selects one ticker after the workbench run.
- `策略視覺化策略` multiselect can show `綜合策略` and/or individual strategies.
- `顯示 SMC 特徵` checkbox can hide/show SMC Order Block / Liquidity overlays.
- Chart overlays stateful strategy markers on candles: long entries are BUY, long exits are SELL, bearish/fade entries are SELL, and short/fade exits are BUY_TO_COVER.
- Chart adds per-trade vertical dotted entry/exit lines, a dashed PnL connector, green/red profit/loss area, and an exit annotation such as `+6.00%` or `-4.63%` so the user can see exactly where each trade made or lost money.
- Strategy trades are non-overlapping: after an exit, at least one full bar must pass before the same strategy can enter again. This avoids misleading same-candle or adjacent-candle buy/sell markers.
- Chart also overlays strategy buy/sell zones, SMA/Bollinger/RSI/MACD/volume, equity curve, and drawdown curve.
- The metrics table summarizes trade count, win rate, cumulative return, max drawdown, and Profit Factor for the selected strategy view.
- The strategy suitability bar chart now explains its colors: green/yellow/red mean high/mixed/weak strategy suitability for the selected ticker and history window. This is not SHAP positive/negative correlation.
- Sidebar `個人交易偏好` was added for manual trading assumptions: no day trading, max orders per stock per day, default shares/lots per order, and usual holding days. The usual holding days value becomes the default for the workbench `預計持有天數` control.
- Sidebar was later narrowed to global controls only: data source, ticker universe, history period, K-line interval, global decision horizon, personal trading preferences, CSV upload, and manual refresh. Backtest/Smart Tuning controls now live in `回測`; factor controls live in `因子研究`; price-chart volume display lives in `價格圖表`.
- The workbench tab now includes `頁籤使用目的` explaining what the tab is for and how to use it.

Follow-up integration implemented in the same cycle:

- `src/ai_stock/order_planner.py` now exposes `integrate_strategy_recommendations_into_order_plan()`.
- `隔日掛單計畫` reads the last workbench result from session state and adds final buy/sell/stop/take-profit fields.
- The priority heatmap uses final strategy ranges when available.
- The row-linked technical chart overlays the final strategy ranges, not only the original base ranges.

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

- 88 passed

New tests:

- `tests/test_order_strategy_workbench.py`
- `tests/test_next_day_strategy_workbench_ui_source.py`
- `tests/test_strategy_visualization.py`
- `tests/test_strategy_visualization_ui_source.py`
- `tests/test_strategy_state_machine.py`
- `tests/test_sidebar_refactor_ui_source.py`

## Follow-up ideas

- Add direct integration from factor research SHAP importance cache into `shap_factor` strategy.
- Add color-styled BUY/SELL urgency table similar to the existing next-day order heatmap.
- Move analysis-only tabs into an `分析報表` group if Streamlit navigation is later refactored into pages.
