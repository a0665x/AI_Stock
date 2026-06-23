# Task Understanding: Phase 2 visual workbench

Date: 2026-06-23

## User request

Implement the second QuantDinger-inspired visual workbench phase:

1. Watchlist + mini sparkline.
2. Market heatmap.
3. Smart Tuning Lite.

Keep the dashboard as decision support only; do not add live trading, broker accounts, or order execution.

## Implementation

### Core module

Updated `src/ai_stock/visual_insights.py` with:

- `build_watchlist_sparklines()`
  - One row per ticker.
  - Latest close, 1D/5D return, action, decision badge, relationship-adjusted return, Kelly, and compact sparkline close-series list.

- `build_market_heatmap_table()`
  - One row per ticker.
  - Tile size from recent volume × close activity.
  - Color value from recent 5D return.
  - Signal score blends relationship-adjusted return, Kelly, action state, and recent return.

- `build_smart_tuning_lite()`
  - Button-triggered parameter scan.
  - Scans holding days, exit rules, and risk-width values.
  - Ranks scenarios using cumulative return, win rate, Profit Factor, max drawdown, and stop-loss hit rate.

### UI

Updated `src/ai_stock/app.py`:

- Sidebar now renders `Watchlist` cards with mini SVG sparkline, latest close, 1D move, and action badge.
- Home / decision tab now includes `市場熱力圖` / Market heatmap treemap.
- Backtest tab now includes `Smart Tuning Lite` section:
  - Sidebar controls for tuning holding days and risk-width values.
  - Button-triggered scan only, to avoid slow auto-computation on ARM.
  - Bar chart ranking and downloadable CSV.

### i18n

Updated `src/ai_stock/i18n.py` with new Traditional Chinese / English / Japanese / Korean labels for Watchlist, Market heatmap, and Smart Tuning Lite UI text.

### Docs

Updated:

- `README.md`
- `README-en.md`
- `README-zh.md`
- `spec/PROJECT_MAP.md`

## Verification

- New tests:
  - `tests/test_phase2_visual_workbench.py`
  - `tests/test_phase2_ui_source.py`

- Local verification:
  - `pytest -q` → `34 passed`
  - `python -m compileall src` → pass

- Docker verification:
  - `./run.sh rebuild && ./run.sh test` → `34 passed`
  - `./run.sh down_up`
  - health endpoint `http://127.0.0.1:8507/_stcore/health` → `ok`

- Browser verification:
  - Watchlist appears in sidebar.
  - Smart Tuning Lite controls appear in sidebar and Backtest page.
  - No browser console errors.
  - Docker log has no runtime exception.

- Container smoke:

```text
prices: (753, 7)
watchlist: (3, 11)
heatmap: (3, 13)
smart_tuning: (24, 14)
top: NVDA | 3d | time | risk 3%
```

## Notes

Smart Tuning Lite is intentionally not auto-run. It scans multiple backtests and should remain button-triggered, especially on AGX / ARM hosts.
