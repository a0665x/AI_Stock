# 2026-06-23 Phase 1 Quant Workbench Visual Upgrade

## Goal
Add the first-stage visual features inspired by QuantDinger-style workbench UX without adding broker execution or live trading:

1. Today’s Opportunity Radar
2. Candlestick buy/sell/stop-loss overlays
3. Strategy Health Cards

## Implemented

### Core module
Added `src/ai_stock/visual_insights.py`:

- `build_opportunity_radar(report, backtest_summary, top_n=6)`
  - Combines decision report and walk-forward backtest summary.
  - Produces ticker cards with action, tone, adjusted return, Kelly, buy/sell/stop levels, win rate, cumulative return, and reason.

- `build_strategy_health_cards(backtest_summary, decision_report)`
  - Converts numeric strategy diagnostics into readable warnings.
  - Current checks include low sample count, high max drawdown, Profit Factor below 1, low win rate, negative cumulative return, and zero-Kelly wait state.

- `build_decision_price_chart(price_frame, ticker, show_volume, decision_row, backtest_trades)`
  - Adds buy reference, sell reference, and stop-loss reference horizontal lines.
  - Adds backtest entry B and exit S markers when trades exist.

### Streamlit UI
Updated `src/ai_stock/app.py`:

- Main dashboard now shows `今日機會雷達` / `Today’s Opportunity Radar` directly below the top metrics.
- Decision report tab now shows `策略健檢卡` / `Strategy Health Cards` above the table.
- Price chart tab now overlays decision levels and backtest B/S markers on the candlestick chart.
- New display text and dynamic health-card messages are multilingual through `src/ai_stock/i18n.py`.

### Tests
Added `tests/test_visual_insights.py`:

- opportunity radar generation
- strategy health diagnostics
- decision price chart overlays and B/S markers

## Verification

- Local: `pytest -q` -> 30 passed
- Local: `python -m compileall src` -> passed
- Docker: `./run.sh rebuild && ./run.sh test` -> 30 passed
- Docker health: `curl http://127.0.0.1:8507/_stcore/health` -> ok
- Browser DOM verification:
  - Opportunity Radar rendered
  - Strategy Health Cards rendered
  - Price chart legend contains buy/sell/stop-loss lines and backtest B/S markers

## Boundaries
No live trading, broker account, leverage, order placement, or automated execution was added. These features remain decision-support only.
