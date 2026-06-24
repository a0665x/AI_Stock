# AI_Stock

<p align="center">
  <a href="README.md"><strong>English</strong></a> |
  <a href="README-zh.md">繁體中文</a>
</p>

AI_Stock is a multilingual stock research and decision-support dashboard. It does not place trades automatically, and it does not present model output as financial advice. Its purpose is to help users inspect price action, technical indicators, walk-forward backtests, factor research, SHAP attribution, and cross-stock relationships in one Web UI.

## What it can do

- Multilingual Web UI: Traditional Chinese, English, Japanese, and Korean from the selector in the upper-right corner.
- Interactive historical price and candlestick charts with buy/sell/stop-loss reference lines and backtest B/S markers.
- Opportunity Radar cards that summarize decision state, Kelly sizing, backtest win rate, return, buy level, and stop-loss level for each ticker.
- Sidebar Watchlist with mini sparklines, latest close, 1-day move, and decision state for each ticker.
- Market heatmap that uses tile size for activity and color for recent performance, so users can quickly spot hot or weak names.
- Smart Tuning Lite: button-triggered scan across holding days, exit rules, and risk widths, ranked by a composite score using return, win rate, Profit Factor, drawdown, and stop-loss hit rate.
- Trade Vision Center: advanced candlestick workbench with market structure, BOS/ChoCH, support/resistance and supply/demand zones, Entry/SL/TP, risk/reward box, MTF Matrix, Signal Score, and AI Trade Narrative. It is research support only and never places trades.
- Next-Day Order Planner: converts strategy-level buy/sell/stop references into more reachable next-session buy/sell ranges, tactical stop, hard stop, and touch-probability labels for current holdings. It is research support only and never places orders.
- Strategy Health Cards that turn sample size, max drawdown, Profit Factor, win rate, cumulative return, and Kelly state into readable warnings.
- Technical snapshot: SMA, EMA, RSI, MACD, KD, MFI, ATR, Bollinger position, volume ratio, volatility, drawdown, support, and resistance.
- Decision report: model expected return, relationship-adjusted return, buy reference, sell reference, stop-loss reference, Kelly position, decision reason, and explanation for Kelly 0.0%.
- Walk-forward backtest: win rate, maximum drawdown, stop-loss hit rate, cumulative return, individual trades, and comparison across holding periods and exit rules.
- Factor research: sliding-window samples use past N days of candlestick, KD, MACD, RSI, volume, drawdown, and volatility factors as X, then use future 1/3/5/10-day up/down outcome as y. The report compares Accuracy, AUC, baseline, ticker × horizon heatmap, SHAP/fallback importance, correlations, grouped win rates, and y heatmap.
- SHAP / fallback attribution: triggered by button, so the dashboard does not recompute expensive attribution on every page load.
- Multi-stock return-correlation and positive/negative peer-pressure analysis.
- Local portfolio import from private my_stocks.json / my_sotcks.json: the app pre-fills current holdings, merges them with model decisions, and creates a stop-loss / take-profit / add-limit / reduce-check trade plan. It does not place orders.
- yfinance / CSV data sources. Docker mode stores yfinance cache under docker_runtime/market_cache.
- The futu-api Python package is included, but Futu OpenD still needs an external machine or remote OpenD service that can actually run OpenD.

## UI preview

The screenshots below show the English dashboard. The gallery uses HTML with inline CSS for horizontal scrolling. If a Markdown renderer filters CSS, the images still remain visible and may simply fall back to a vertical layout.

<div style="display:flex; overflow-x:auto; gap:16px; padding:8px 0 16px 0; scroll-snap-type:x mandatory;">
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-decision.png" alt="AI Stock decision report dashboard" width="760">
    <figcaption>Decision report: buy/sell/stop-loss references, relationship-adjusted return, and Kelly position.</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-price.png" alt="AI Stock candlestick and price chart" width="760">
    <figcaption>Price charts: candlestick trend, moving averages, and volume context.</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-backtest.png" alt="AI Stock walk-forward backtest" width="760">
    <figcaption>Walk-forward backtest: win rate, drawdown, stop-loss hit rate, and cumulative return curve.</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-relationships.png" alt="AI Stock stock relationship heatmap" width="760">
    <figcaption>Stock relationships: return-correlation heatmap and positive/negative peer pressure.</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-factor.png" alt="AI Stock factor research dashboard" width="760">
    <figcaption>Factor research: multi-horizon Accuracy/AUC, ticker × horizon heatmap, and factor attribution.</figcaption>
  </figure>
</div>

## Project layout

- src/ai_stock/: stock analysis modules and Streamlit application.
- tests/: pytest behavior tests.
- spec/: project notes, task records, and beginner tutorial.
- spec/tutor_guide.md: beginner guide covering UI usage, technical terms, Kelly sizing, wait-for-confirmation decisions, backtesting, factor research, and example interpretation workflows.
- Dockerfile / docker-compose.yml / run.sh: Docker Compose entry points for one-command launch and management.

## Quick start with Docker Compose

Docker is the recommended way to run the dashboard.

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
./run.sh --help
./run.sh up
./run.sh status
```

Open the URL printed by run.sh status, for example:

```text
http://127.0.0.1:8507
```

If the host is logged into Tailscale, run.sh status and run.sh url also print Tailscale MagicDNS and Tailscale IP URLs.

Common commands:

```bash
./run.sh up          # build and start in background
./run.sh down        # stop and remove the container
./run.sh down_up     # down, rebuild, and start again
./run.sh restart     # alias of down_up
./run.sh log         # follow logs
./run.sh logs        # alias of log
./run.sh status      # compose ps + Local/LAN/Tailscale URLs
./run.sh url         # print URLs only
./run.sh test        # run pytest inside the container
./run.sh shell       # open a shell inside the container
```

If run.sh is not executable yet, use:

```bash
bash run.sh up
```

## Basic UI workflow

1. Choose the interface language from the upper-right selector: Traditional Chinese / English / Japanese / Korean.
2. Select a data source from the left sidebar: yfinance or CSV.
3. Enter ticker symbols, for example AAPL, MSFT, NVDA.
4. Choose the history period and candlestick interval. Beginners can start with 1y + 1d.
5. Start with Decision report: buy reference, sell reference, stop-loss reference, Kelly position, and reason for wait-for-confirmation.
6. Open Trade Vision Center for the integrated advanced chart, market structure, Entry/SL/TP, MTF Matrix, Signal Score, and AI Trade Narrative.
7. If my_stocks.json / my_sotcks.json exists locally, open Portfolio order plan to review stop-loss, take-profit, add-limit, and reduce/exit checks for current holdings.
8. Open Next-Day Order Planner to review next-session buy/sell ranges, tactical stop, hard stop, and whether the suggested levels are likely to be touched by normal daily volatility.
9. Check Backtest for win rate, maximum drawdown, stop-loss hit rate, and cumulative return.
10. Check Factor research to compare which 1/3/5/10-day horizon has stronger signal.
11. When deeper explanation is needed, run Attribution or Factor research from the button-triggered sections.
12. Use Stock relationships to check whether selected stocks share the same risk exposure.

For a more detailed beginner explanation, read:

```text
spec/tutor_guide.md
```

## Docker cache

Docker Compose mounts:

```text
./docker_runtime:/app/runtime
```

yfinance disk cache is stored under:

```text
docker_runtime/market_cache/
```

After container restarts, the same ticker / period / interval combination can be loaded from disk cache first. To force fresh market data, click Re-fetch data / update analysis in the sidebar, or manually delete docker_runtime/market_cache/yf_*.pkl.

## Local development

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
uv venv .venv
. .venv/bin/activate
uv pip install -e '.[dev,futu]'
pytest -q
streamlit run src/ai_stock/app.py --server.headless true --server.port 8507 --server.address 0.0.0.0
```

## Core modules

- data_sources.py: OHLCV schema, yfinance fallback, Futu/OpenD adapter boundary, and market-data cache.
- analytics.py: technical snapshot, return correlation, and positive/negative peer pressure.
- forecasting.py: ARIMA / sklearn baseline, Kelly sizing, buy/sell/stop-loss references, and decision reasons.
- backtesting.py: walk-forward backtest plus holding-period and exit-rule comparison.
- attribution.py: SHAP TreeExplainer / permutation-importance fallback.
- factor_research.py: sliding-window technical-factor dataset, multi-horizon up/down classification, Accuracy/AUC trend, ticker × horizon heatmap, SHAP/fallback importance, correlations, grouped win rates, and y heatmap.
- pipeline.py: data → analysis → report pipeline.
- portfolio.py: local private holdings loader plus portfolio stop-loss / take-profit / add-limit / reduce-check planning. It reads my_stocks.json / my_sotcks.json when present and never places orders.
- order_planner.py: next-day order research planner; estimates reachable buy/sell ranges, tactical stop, hard stop, touch probability, and suggested order type from holdings, OHLCV volatility, and the decision report.
- visual_insights.py: Opportunity Radar, Watchlist sparklines, market heatmap, Smart Tuning Lite, Strategy Health Cards, and candlestick decision overlays with backtest B/S markers.
- trade_vision.py: Trade Vision Center engine for swing/BOS/ChoCH market structure, support/resistance and supply/demand zones, premium/discount/equilibrium, Entry/SL/TP trade plans, MTF Matrix, Signal Score, AI Trade Narrative, and advanced Plotly risk/reward candlestick charts.
- app.py: Streamlit UI and multilingual display layer.
- i18n.py: Traditional Chinese / English / Japanese / Korean UI language pack.

## Before pushing to GitHub

This repo includes a .gitignore that excludes:

- .venv, pytest cache, Python cache.
- runtime, docker_runtime, market-data cache, logs, sqlite, pkl/joblib/parquet local data.
- .env, token, credential, secret, and key files.
- .codex, .claude, .cursor, .hermes, AGENTS.md, CLAUDE.md, agent/codex logs, session transcripts, and local assistant traces.

Check before uploading:

```bash
git status --short
git status --ignored --short | head -80
```

## Push to the existing GitHub repo

The target repo is:

```text
https://github.com/a0665x/AI_Stock.git
```

If this local directory has not been initialized as a git repo:

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
git init
git branch -M main
git remote add origin https://github.com/a0665x/AI_Stock.git
git status --short
git add .
git status --short
git commit -m "Initial AI Stock dashboard"
git push -u origin main
```

If git is already initialized locally:

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
git remote -v
git remote add origin https://github.com/a0665x/AI_Stock.git  # only if origin is not set yet
git add .
git commit -m "Add multilingual AI Stock dashboard"
git push -u origin main
```

If GitHub asks for a password, paste your GitHub develop token into the password prompt. Do not write the token into any project file.

## Disclaimer

This project is for research and decision support only. It is not financial advice, and it does not perform automatic trading. Any buy/sell decision should also consider personal risk tolerance, position sizing, transaction cost, liquidity, and external market information.
