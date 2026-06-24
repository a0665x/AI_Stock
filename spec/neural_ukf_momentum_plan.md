# Neural + UKF Momentum Roadmap

Date: 2026-06-24
Scope: future architecture for improving the AI Stock next-day / swing-trading order planner with multi-source time-series inputs and UKF-based noise filtering.

## Why this is not implemented as a live trading model yet

The current dashboard is a research assistant, not an auto-trading system. The next-day order planner already uses current price, recent intraday range, technical indicators, decision report, portfolio holdings, and reachable touch-probability labels. A neural network + UKF stack can be useful later, but it must be trained, walk-forward validated, and monitored before it is allowed to influence suggested order levels.

For now, the UI includes a lightweight UKF-style denoised momentum indicator in the next-day order technical chart. It smooths noisy technical momentum from RSI, MACD histogram, Bollinger position, volume ratio, and short returns. It is not a trained deep-learning forecast.

## Target model concept

Goal:
Predict short-horizon momentum and order-direction confidence for next-day / swing-trading plans.

Inputs X_t:
1. Market OHLCV features
   - open, high, low, close, volume
   - returns: 1D, 3D, 5D, 10D, 20D
   - intraday range and gap features
   - rolling volatility and ATR%
   - volume ratio / OBV / MFI

2. Technical indicators
   - RSI
   - MACD / MACD histogram
   - KD / stochastic K,D
   - Bollinger position and band width
   - SMA / EMA slope and crossover state
   - support / resistance distance
   - swing high / swing low / BOS / ChoCH events from Trade Vision Center
   - next-day order touch-probability features

3. Portfolio / risk context
   - current position size
   - unrealized PnL%
   - Kelly fraction
   - current action class
   - strategy-level buy/sell/stop distance
   - tactical stop distance

4. Market / peer context
   - SPY / QQQ / sector ETF returns
   - VIX or volatility proxy
   - peer correlation pressure
   - sector relative strength

5. Event and sentiment time series
   - earnings date proximity
   - macro calendar flags
   - news sentiment
   - social sentiment
   - analyst rating changes
   - option-implied sentiment when available

Target y:
- classification: future 1D / 3D / 5D direction above threshold
- regression: future forward return
- touch target: whether next-day buy zone / sell zone / tactical stop is touched
- risk target: whether hard stop / tactical stop is hit before TP

## Neural + UKF architecture

Stage 1: sequence encoder
- Baseline: LSTM / GRU over rolling windows, e.g. 20 to 60 bars.
- Later: Temporal Fusion Transformer or lightweight Transformer encoder.
- Output: latent momentum state estimate z_t and uncertainty proxy.

Stage 2: UKF state filtering
State vector example:
- price_momentum
- momentum_velocity
- volatility_regime
- volume_pressure
- sentiment_pressure
- structure_bias

Observation vector:
- neural output z_t
- raw technical momentum score
- realized return / volatility observations
- sentiment/event observations

UKF role:
- smooth noisy model outputs
- update state as new bars arrive
- separate signal from daily noise
- produce filtered trend probability and confidence band

Stage 3: decision bridge
The filtered state must not directly place orders. It should feed:
- next-day order plan confidence
- buy/sell/tactical stop reachability adjustment
- swing-trading readiness score
- risk warning flags

## Data source options for non-price inputs

### Free / low-friction sources

1. yfinance
- OHLCV, dividends/splits, some fundamentals, earnings dates for selected tickers.
- Already integrated for price data.
- Useful for baseline only.

2. Stooq / Alpha Vantage / Twelve Data / Finnhub free tiers
- Can provide prices, fundamentals, news in limited quota.
- Requires API key for many endpoints.
- Should be cached aggressively.

3. SEC EDGAR
- 8-K / 10-Q / 10-K filing dates and textual changes.
- Useful for event risk and fundamental event flags.
- More suitable for slower horizons than next-day scalping.

4. FRED
- Macro time series: rates, CPI, unemployment, treasury yields.
- Useful as market regime context.

5. RSS/news feeds
- Company press releases, finance RSS, exchange announcements.
- Can be converted into daily sentiment counts.

### Paid / API-key sources that would improve quality

1. Finnhub
- Company news, sentiment, earnings calendar, analyst ratings.

2. Polygon.io
- Market data, news, options, corporate actions.

3. Benzinga / NewsAPI / GDELT
- News volume and sentiment proxies.

4. Tiingo / IEX Cloud / Intrinio
- Financial data and events.

5. Option data providers
- Put/call ratio, IV rank, skew, unusual options flow.
- Potentially strong input for next-day order confidence, but usually paid.

### Social / sentiment sources

1. Reddit
- r/stocks, r/wallstreetbets, ticker mentions.
- Needs careful filtering; noisy and regime-dependent.

2. X/Twitter
- Ticker mention volume and sentiment.
- API limitations; must avoid scraping policy violations.

3. Google Trends
- Search interest proxy.
- Coarse but useful for attention spikes.

## Recommended implementation phases

Phase A: current lightweight implementation
- Keep `swing_order_chart.compute_ukf_momentum_state()` as a transparent indicator.
- Inputs: RSI, MACD histogram, Bollinger position, volume ratio, 5D return.
- Output: UKF momentum, velocity, noise band, state label.
- UI: show on next-day order technical chart.

Phase B: feature store
Add `ai_stock/feature_store.py`:
- Build aligned daily feature tables by ticker/date.
- Include price, technical, structure, portfolio, factor, backtest, and market-regime features.
- Keep canonical internal column names.
- Cache to `docker_runtime/feature_cache/`.

Phase C: external event/sentiment adapters
Add optional adapters:
- `event_sources.py` for earnings/macro/calendar flags.
- `news_sentiment.py` for API/RSS sentiment.
- `market_regime.py` for SPY/QQQ/VIX/FRED regime features.
All adapters must degrade gracefully when credentials are absent.

Phase D: supervised multi-horizon dataset
Extend factor research:
- Create sequence windows: ticker × date × lookback × features.
- Targets: 1D/3D/5D/10D direction, return, touch events.
- Use walk-forward splits only.
- Save dataset metadata for reproducibility.

Phase E: neural baseline
Start with simple models:
- logistic / gradient boosting remains benchmark.
- then LSTM / GRU baseline with PyTorch only if installed in an optional extra.
- compare out-of-sample AUC, precision, recall, calibration, and strategy PnL.

Phase F: UKF state filter
Add `ai_stock/ukf_state.py`:
- scalar and multi-dimensional UKF implementation without heavy dependencies first.
- use neural output and technical observations as measurements.
- emit filtered momentum score and confidence interval.

Phase G: UI integration
Add model outputs only as optional research panels:
- filtered momentum confidence
- expected next-day reachability adjustment
- uncertainty warning
- do not auto-change order plan until walk-forward results exceed thresholds.

## Validation rules before affecting suggested orders

A model can influence next-day order levels only if:
1. Walk-forward AUC > 0.55 for target horizon.
2. Performance beats baseline hit rate by at least 3 percentage points.
3. Strategy PnL improves after transaction-cost assumptions.
4. Max drawdown does not worsen materially.
5. Calibration is acceptable: predicted confidence buckets match realized rates.
6. Results hold across at least several tickers or clearly documented ticker-specific regimes.

## Safety boundary

This roadmap is for research and decision support only. No broker order placement, no automatic trading, and no hidden API-key storage should be added without explicit user approval.
