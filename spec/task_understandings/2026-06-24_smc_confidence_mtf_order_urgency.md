# 2026-06-24 — SMC confidence and multi-timeframe order urgency

## Goal
Add Smart Money Concepts confidence to the Next-Day Order Planner and make the table easier to triage for swing trading.

## Implementation
- Added `build_smc_timeframe_signals()` in `src/ai_stock/order_planner.py`.
  - Accepts canonical OHLCV frames by timeframe, e.g. `15m`, `1h`, `1d`.
  - Uses `smc_adapter.build_smc_context()` so smartmoneyconcepts is preferred and internal fallback still works.
  - Scores FVG/IFVG, Order Blocks, Liquidity, Swing High/Low, BOS and ChoCH into bullish/bearish SMC scores.
- Added `augment_order_plan_with_smc()`.
  - Adds `smc_confidence_score`, `smc_bias`, `smc_timeframe_summary`.
  - Adds `buy_urgency_score`, `sell_urgency_score`, `priority_score`.
  - Urgency combines next-day touch probability, suggested order type, SMC direction, and multi-timeframe confidence.
- Streamlit `隔日掛單計畫` uses fast 1d SMC by default, and exposes a checkbox to fetch/cache 15m and 1h yfinance frames plus the existing 1d frame before augmenting the plan. This avoids blocking the entire dashboard during first page load.
- Added a visual heatmap table:
  - Buy urgency uses green fill.
  - Sell/reduce/protect urgency uses red fill.
  - Darker color means higher priority to inspect and potentially act.
- Added a `圖例名詞說明 / Legend glossary` expander because Plotly/Streamlit does not support custom hover popups on legend text itself.

## Validation
- Unit tests added in `tests/test_order_planner_smc.py`.
- Local pytest: 67 passed.
- Smoke:
  - Actual portfolio produced SMC confidence / urgency / priority columns.
  - yfinance 15m and 1h frames successfully loaded for AAPL/NVDA and produced SMC timeframe signals.

## UI Fix Follow-up
- Fixed the priority heatmap rendering issue where Streamlit/Markdown displayed raw `<tr>` / `<td>` source text in the page.
- Replaced the hand-written HTML table with a pandas `Styler` rendered through `st.dataframe()`, so Streamlit owns table rendering and raw HTML rows cannot leak into the app.
- The table keeps the same triage semantics:
  - Buy/add urgency uses green fill.
  - Sell/reduce/protect urgency uses red fill.
  - Total priority score uses blue fill.
  - Darker color means higher priority to inspect and potentially act.
- Expanded the legend glossary with icon-style prefixes so users can quickly map explanations back to chart markers/lines:
  - 🕯️ K-line
  - ━━ SMA20 / SMA60
  - 〰️ Bollinger
  - ⚡ RSI14
  - ▮▮ MACD / MACD Hist
  - ▧ FVG / IFVG
  - ▣ SMC Order Block
  - ● SMC Liquidity
  - ▲▼ Swing High / Low
  - ✚ BOS / ChoCH
  - ◆ SFP
- Added `spec/next_day_order_planner_spec.md` as the full spec for this page.
- Added regression tests in `tests/test_order_heatmap_rendering.py` to keep the heatmap off raw HTML table rows and preserve glossary icons.

## Notes
This remains research assistance only. It does not connect to a broker and does not place orders.
