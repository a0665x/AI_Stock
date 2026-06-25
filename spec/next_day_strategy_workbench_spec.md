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
3. Open technical chart for the chosen ticker.
4. Use report-only pages for deeper explanation.

## User controls

### Ticker scope

Control: `策略工作台股票範圍`

Options:

- 全選: test all tickers in the next-day order plan.
- 自選: select one or more tickers first.

Recommendation: start with one ticker, then run all tickers after the settings look reasonable.

### Holding horizon

Control: `工作台持有天數`

Options:

- 1 day
- 5 days
- 10 days
- 15 days
- 30 days

All strategy backtests and order urgency calculations use this horizon. This prevents mixing a 1-day execution signal with a 30-day swing setup.

### Risk tolerance

Control: `風險耐受度%`

Default: 10%

Used as the strategy backtest stop width and as a planning assumption for order risk. It is a slider because it is a continuous risk parameter.

### Backtest range

Control: `工作台回測期間`

Options:

- 1周
- 2周
- 1個月
- 3個月
- 半年
- 1年

The range limits the trailing history used for this strategy suitability check.

### Strategy fields

Control: `策略欄位`

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

## Core module

File: `src/ai_stock/order_strategy_workbench.py`

Main public functions:

- `filter_backtest_window(prices, backtest_range)`
- `build_order_strategy_workbench(...)`

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

Required checks:

- local pytest
- Docker build/test
- Streamlit health check
- Browser smoke for tab/control visibility
