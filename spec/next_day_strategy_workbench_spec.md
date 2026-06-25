# Next-Day Strategy Workbench Spec

## Purpose

The Next-Day Strategy Workbench turns the next-day order table from a static report into an actionable, user-triggered research workflow. It helps answer:

- Which ticker should be checked first?
- Which strategy family currently fits that ticker better?
- Which holding horizon is the calculation based on?
- What risk tolerance is assumed for stop/take-profit planning?
- What buy/sell limit zone should be considered for the next session?

This is a research and decision-support tool only. It never sends broker orders and does not store broker credentials.

## Why this exists

The older decision report displayed Kelly fraction and often showed 0.0%. A zero Kelly value is useful as a conservative sizing guardrail, but it is not enough to decide next-day limit orders because prices still move intraday and different stocks respond to different technical regimes. The workbench therefore separates:

- Sizing guardrail: Kelly remains informational.
- Strategy suitability: per-strategy backtest over a user-selected lookback window.
- Actionable order zone: next-day reachable buy/sell/stop range.

## UI location

Tab: `隔日策略工作台`

Placed after `隔日掛單計畫` and before chart/report-only pages, so the flow is:

1. Review next-day order candidates.
2. Run strategy workbench for selected tickers.
3. Return to `隔日掛單計畫`, where the workbench result is merged into the final buy/sell/stop/take-profit levels.
4. Open technical chart for the chosen ticker.
5. Use report-only pages for deeper explanation.

## User controls

### Ticker scope

Control: `要驗證哪些股票`

Options:

- 全選: test all tickers in the next-day order plan.
- 自選: select one or more tickers first.

Recommendation: start with one ticker, then run all tickers after the settings look reasonable.

### Holding horizon

Control: `預計持有天數`

Options:

- 1 day: next-day / very short tactical check.
- 5 days: short swing check.
- 10 days: medium swing check.
- 15 days: swing-to-position check.
- 30 days: longer position check.

All strategy backtests and order urgency calculations use this horizon. This prevents mixing a 1-day execution signal with a 30-day swing setup.

### Risk tolerance

Control: `可承受停損幅度%`

Default: 10%

Used as the strategy backtest stop width and as a planning assumption for order risk. It is not the whole-account risk budget. It is a slider because it is a continuous risk parameter.

### Backtest range

Control: `用多久歷史驗證`

Options:

- 1周
- 2周
- 1個月
- 3個月
- 半年
- 1年

The range limits the trailing history used for this strategy suitability check.

### Strategy fields

Control: `選擇策略`

Options are checkboxes/multiselect, not sliders, because these are discrete strategy families:

- 布林決策 (`bollinger`)
- SMC 決策 (`smc`)
- UKF 動能決策 (`ukf`)
- KD/MACD 決策 (`kd_macd`)
- SHAP 因子代理決策 (`shap_factor`)

The SHAP factor strategy is currently a lightweight factor proxy. It uses the same factor families that the attribution/factor pages often rank, but it does not trigger an expensive SHAP model run inside the workbench.

### Execution

Button: `啟動隔日策略回測`

The workbench is intentionally button-triggered. It does not run in the global app load path to avoid slowing down the dashboard.

### Sidebar scope

The sidebar is intentionally limited to global settings that affect the whole dashboard:

- Data source and ticker universe.
- History period and K-line interval.
- Global decision horizon.
- Personal trading preferences.
- CSV upload and manual refresh.

Page-specific controls stay inside the relevant tab:

- Backtest lookback, comparison horizons, exit rules, trailing stop, Smart Tuning horizons/stop widths, and buy-signal filtering live in `回測`.
- Factor input window, horizons, threshold, and model selection live in `因子研究`.
- Price-chart volume visibility lives in `價格圖表`.

This keeps the left sidebar from becoming a long mixed control panel and makes each tab self-contained.

### Personal trading preferences

Sidebar section: `個人交易偏好`

Current controls:

- `不做當沖`: reminds the workbench to use overnight/multi-day assumptions; the strategy state machine never opens and exits on the same daily bar.
- `每天每股最多掛單次數`: documents the user's manual order cadence; daily backtests already allow at most one new trade lifecycle per ticker per day, and this will constrain future 15m/1h intraday expansion.
- `預設每次掛單股數/張數`: report-only reminder for position sizing; the dashboard still never sends orders.
- `習慣持有幾天`: becomes the default value for the workbench `預計持有天數` control.

These preferences are not broker settings and are not secrets.

## Core module

File: `src/ai_stock/order_strategy_workbench.py`

Main public functions:

- `filter_backtest_window(prices, backtest_range)`
- `build_order_strategy_workbench(...)`
- `build_strategy_visualization_payload(...)`

Constants:

- `ORDER_STRATEGIES`
- `BACKTEST_RANGE_DAYS`

## Strategy semantics

### Bollinger strategy

Uses Bollinger position plus RSI:

- Bullish: price is near lower band and RSI is not overheated.
- Bearish: price is near upper band and RSI is elevated.

Useful for mean-reversion swing entries/exits.

### SMC strategy

Uses the SMC fields already attached to the next-day plan:

- SMC bias
- SMC confidence score

Useful when FVG/OB/liquidity/structure context is aligned.

### UKF momentum strategy

Uses denoised UKF-style momentum from `swing_order_chart.py`.

- Momentum above bullish threshold = bullish.
- Momentum below bearish threshold = bearish.

Useful for avoiding noisy raw indicator flips.

### KD/MACD strategy

Uses stochastic K/D alignment and MACD histogram direction.

Useful for shorter-term continuation and reversal checks.

### SHAP factor proxy strategy

Uses lightweight factor proxy inputs:

- 5-day return
- 20-day return
- MACD histogram
- volume ratio

This is a placeholder for future direct factor/SHAP integration. It is cheap enough for an interactive workbench.

## Outputs

### Strategy suitability table

Section: `策略勝率 / 股性適配表`

Columns include:

- ticker
- strategy label
- holding days
- risk tolerance
- backtest range
- trade count
- win rate
- average return
- cumulative return
- max drawdown
- stop hit rate
- profit factor
- strategy edge score
- latest signal

`strategy_edge_score` combines win rate, profit factor, cumulative return, and drawdown into a 0-100 score.

Color semantics in the bar chart:

- Green: higher strategy suitability for the selected ticker/time window.
- Yellow: mixed / needs chart confirmation.
- Red: weak recent suitability for this strategy and ticker.

This color is not SHAP positive/negative contribution. SHAP/factor direction is shown in the factor research and attribution pages, not in this suitability bar chart.

### Best order zone table

Section: `最佳掛單區間`

Columns include:

- ticker
- best strategy
- holding days
- risk tolerance
- side: BUY / SELL / WAIT
- urgency score
- buy low/high
- sell low/high
- stop loss
- take profit reference
- reason

The table merges strategy suitability with the existing next-day reachable order zones. It does not invent broker orders.

### Strategy visualization chart

Section: `策略買賣點與績效曲線`

Controls:

- `策略視覺化股票`: choose one ticker after the workbench has run.
- `策略視覺化策略`: choose `綜合策略` and/or individual strategy families to display.
- `顯示 SMC 特徵`: toggle SMC Order Block / Liquidity overlays so the user can hide structure clutter when they only want the strategy performance curve.

The chart includes:

- Candlesticks and price context.
- SMA20 / SMA60 and Bollinger upper/lower bands.
- Volume panel.
- RSI14 panel.
- MACD / MACD signal / MACD histogram panel.
- Strategy buy entry markers, sell/short-entry markers, and buy-to-cover exit markers from the selected strategy trades.
- Per-trade vertical dotted entry/exit lines so the trade lifecycle is visible even when marker symbols overlap nearby candles.
- Per-trade dashed PnL connector between entry and exit price; green connector/area means the completed backtest trade made money, red connector/area means it lost money.
- PnL annotation at the exit point, e.g. `+6.00%` or `-4.63%`.
- Strategy buy/sell zone overlays from the best order recommendation.
- Optional SMC Liquidity and SMC Order Block overlays.
- Equity curve and drawdown curve in the lower panel.

Strategy marker generation must use a non-overlapping position state machine:

- A strategy can only open a new trade when flat.
- Long trades enter with BUY and exit with SELL.
- Short/fade trades enter with SELL and exit with BUY_TO_COVER.
- A new trade cannot open on the same bar as the previous trade exit.
- At least one full cooldown bar is required after each exit before the next entry is considered.

This avoids misleading charts where one strategy appears to buy and sell on the same candle or on adjacent candles without a realistic position transition.

The companion `策略績效摘要` table shows trade count, win rate, cumulative return, max drawdown, and Profit Factor for the selected strategy view. This makes it easier to compare whether a ticker is more suitable for Bollinger mean-reversion, SMC structure, UKF momentum, KD/MACD continuation, SHAP proxy factors, or a composite blend.

## Integration back into Next-Day Order Planner

The workbench result is not isolated. After a successful run:

1. `st.session_state.order_strategy_workbench_result` holds `order_recommendations`.
2. The `隔日掛單計畫` tab calls `integrate_strategy_recommendations_into_order_plan()`.
3. The base next-day ranges remain visible, but the table adds final fields:
   - final source
   - final side
   - final strategy
   - final strategy edge score
   - final buy range
   - final sell range
   - final stop loss
   - final take-profit reference
4. The priority heatmap uses the final buy/sell ranges when available.
5. The row-linked swing technical chart overlays the final ranges, so the user validates the same levels they would manually enter as orders.

Fallback rule: if there is no workbench result for a ticker, the next-day planner uses the base reachable ranges and marks the source as `BASE_ORDER_PLAN`.

## Performance rules

- The workbench only runs after the user clicks the button.
- Results are kept in `st.session_state.order_strategy_workbench_result`.
- If settings change, the UI warns that displayed results are from the previous run.

## Safety boundaries

- No auto trading.
- No broker API calls.
- No tokens or secrets.
- No runtime holdings/cache files committed to git.

## Verification

Regression tests:

- `tests/test_order_strategy_workbench.py`
- `tests/test_next_day_strategy_workbench_ui_source.py`
- `tests/test_strategy_visualization.py`
- `tests/test_strategy_visualization_ui_source.py`

Required checks:

- local pytest
- Docker build/test
- Streamlit health check
- Browser smoke for tab/control visibility
