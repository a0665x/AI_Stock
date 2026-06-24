# Next-Day Order Planner / 隔日掛單計畫 Spec

## Purpose

The Next-Day Order Planner converts strategy-level decision prices into more reachable next-session order research levels. It is designed for swing-trading preparation, not broker execution.

Core user question:

> Which holding should I inspect first tomorrow, and where are the practical buy / sell / protection levels?

## Safety Boundary

- Research assistance only.
- No broker connection.
- No automatic order placement.
- Local portfolio files such as `my_stocks.json`, `my_sotcks.json`, and `docker_runtime/portfolio/my_stocks.json` remain ignored by Git.

## Inputs

- `prices`: canonical OHLCV DataFrame with `ticker`, `date`, `open`, `high`, `low`, `close`, `volume`.
- `report`: decision report from `forecasting.build_decision_report()`.
- `holdings`: local portfolio positions from `portfolio.load_local_portfolio()`.
- Optional SMC timeframe frames:
  - `1d`: always available from the current dashboard dataset.
  - `1h`, `15m`: optional yfinance intraday fetch/cache, enabled only when the UI checkbox is selected.

## Core Modules

- `src/ai_stock/order_planner.py`
  - `build_next_day_order_plan()`
  - `build_smc_timeframe_signals()`
  - `augment_order_plan_with_smc()`
- `src/ai_stock/smc_adapter.py`
  - Optional `smartmoneyconcepts` adapter.
  - Falls back to internal SMC rules when package/data is unavailable.
- `src/ai_stock/swing_order_chart.py`
  - Row-linked technical chart for the selected ticker.
- `src/ai_stock/app.py`
  - Streamlit UI glue, heatmap, dataframe, row selection, and chart rendering.

## Next-Day Price Logic

The planner does not use strategy prices directly as next-day order prices.

It derives reachable ranges from recent intraday movement:

- median 20-day intraday range
- 80th percentile 20-day intraday range
- current close
- decision-level suggested buy / sell / hard stop

Outputs include:

- next-day buy range
- next-day sell range
- tactical stop
- hard stop
- strategy buy level
- strategy take-profit level
- touch probability labels

## Touch Probability Labels

Price distance is compared with recent intraday range.

- `HIGH`: within about 0.35 × median intraday range.
- `MEDIUM`: within about 0.65 × median intraday range.
- `LOW_MEDIUM`: within about 1.0 × 80th percentile intraday range.
- `LOW_STRATEGY_LEVEL`: too far for a normal next-day touch; treat as strategy-level.

## Suggested Order Type Semantics

Order type uses both model decision and portfolio P/L.

Important rule:

- Losing holding + reachable rebound sell zone = `REBOUND_REDUCE_LIMIT`, not `TAKE_PROFIT_LIMIT`.
- Profitable holding + weak edge = `PROTECT_PROFIT_STOP`.
- Strong buy/watch + Kelly/edge support = buy/add limit candidates.

This prevents misleading labels such as calling a loss-reduction rebound a take-profit order.

## SMC Multi-Timeframe Confidence

`build_smc_timeframe_signals()` summarizes each ticker/timeframe using:

- FVG / IFVG
- Order Block
- Liquidity
- Swing High / Swing Low
- BOS / ChoCH

The Streamlit UI uses:

- Fast mode: `1d` only.
- Multi-timeframe mode: `15m`, `1h`, `1d` after user enables the checkbox.

`augment_order_plan_with_smc()` adds:

- `smc_confidence_score`
- `smc_bias`
- `smc_timeframe_summary`
- `buy_urgency_score`
- `sell_urgency_score`
- `priority_score`

## Priority Heatmap UI

The priority heatmap is rendered with a pandas `Styler` passed to `st.dataframe()`, not a hand-written HTML table. This avoids a Streamlit / Markdown rendering failure where raw `<tr>` / `<td>` table source can appear in the app.

Color convention:

- Green cell = buy / add urgency.
- Red cell = sell / reduce / protect urgency.
- Blue cell = total priority score.
- Darker color = inspect this ticker sooner.

The heatmap is only a triage panel. The user should still open the linked technical chart before placing a real manual order.

## Row-Linked Swing Trading Chart

The table supports row selection when the current Streamlit version allows it. A fallback selectbox is always available.

The selected ticker drives the technical chart below the table.

Displayed overlays:

- Candlestick chart
- x-unified hover and spike line
- SMA20 / SMA60
- Bollinger Bands
- RSI14
- MACD / MACD Histogram
- Volume
- Next-day buy/sell zones
- tactical stop / hard stop
- strategy buy / strategy take-profit
- candlestick pattern markers
- FVG / IFVG
- SMC Order Blocks
- SMC Liquidity
- Swing High / Low
- SFP
- BOS / ChoCH
- UKF-style denoised momentum

## Legend Glossary

Plotly legend labels do not support custom hover tooltips in Streamlit.

The UI therefore renders a `圖例名詞說明 / Legend glossary` expander with icon-style prefixes:

- 🕯️ K-line
- ━━ SMA20 / SMA60
- 〰️ Bollinger
- ⚡ RSI14
- ▮▮ MACD / MACD Hist
- ▥ Volume
- ◇ UKF Momentum
- ▧ FVG / IFVG
- ▣ SMC Order Block
- ● SMC Liquidity
- ▲▼ Swing High / Low
- ✚ BOS / ChoCH
- ◆ SFP

## Performance Rules

- 15m / 1h SMC is opt-in.
- The default page load uses 1d SMC only.
- SHAP remains button-triggered and is not part of this page load.
- Intraday yfinance frames use existing cache pathways.
- If SMC package/data fails, fallback rules must keep the UI functional.

## Validation

Expected checks:

- Unit tests for order planner SMC augmentation.
- Unit tests for SMC adapter.
- Unit tests for swing chart overlays.
- Source regression test that heatmap uses pandas Styler / `st.dataframe()` and does not include raw `<tr>` / `<td>` table rows.
- Local pytest.
- Docker pytest.
- Streamlit health check.
- Browser smoke for the Next-Day Order Planner tab.
