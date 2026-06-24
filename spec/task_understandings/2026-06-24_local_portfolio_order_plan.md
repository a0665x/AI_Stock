# 2026-06-24 Local Portfolio Order Plan

## User ask
Read the user's local account holdings from `my_stocks.json` when present, apply the current AI_Stock decision system to those holdings, and expose a UI view that helps decide stop-loss / take-profit / add-limit / reduce checks. Keep the system as decision support only; do not place orders.

## Implementation
- Added `src/ai_stock/portfolio.py`.
  - Loads local private holdings from `my_stocks.json`.
  - Also supports the existing typo-compatible file name `my_sotcks.json`.
  - Supports `AI_STOCK_PORTFOLIO_FILE` for Docker runtime sync.
  - Builds a portfolio order plan by merging holdings with the decision report.
  - Produces stop-loss order reference, take-profit reference, add-limit reference, suggested order action, position weight, unrealized PnL, and notes.
- Updated `src/ai_stock/app.py`.
  - On startup, if a local portfolio file exists, default ticker input is populated from the current holdings.
  - Added home summary metrics for current portfolio status.
  - Added `持倉下單計畫` tab with order-planning table and explanation expander.
  - The UI explicitly warns that it is research support, not automatic trading.
- Updated Docker runtime flow.
  - `docker-compose.yml` sets `AI_STOCK_PORTFOLIO_FILE=/app/runtime/portfolio/my_stocks.json`.
  - `run.sh up` / `down_up` sync local `my_stocks.json` or `my_sotcks.json` into `docker_runtime/portfolio/my_stocks.json` before starting the container.
- Updated `.gitignore`.
  - Excludes both `my_stocks.json` and `my_sotcks.json` so private account data is not uploaded.
- Added tests:
  - `tests/test_portfolio.py`
  - `tests/test_portfolio_ui_source.py`

## Validation
- Local tests: `40 passed`.
- Compile: `python -m compileall src` passed.
- Docker Compose config: valid.
- Docker tests: `40 passed`.
- Docker service: healthy on port 8507.
- Browser check: sidebar auto-filled holdings tickers and displayed local portfolio file loaded from `/app/runtime/portfolio/my_stocks.json`; `持倉下單計畫` tab exists.
- Portfolio smoke with current local holdings:
  - Loaded 12 holdings.
  - yfinance returned 12 ticker histories.
  - Decision report produced 11 rows; one ticker lacked sufficient decision data and became manual-review.
  - Portfolio plan produced 12 rows.
  - Summary total market value from JSON: 39306.45; total today PnL: -1652.41; largest holding: NVDA ~30.67%.

## Safety boundary
This feature does not connect to any broker and does not submit orders. It only generates suggested references for manual review: stop-loss, take-profit, add-limit, reduce/exit checks, and notes.
