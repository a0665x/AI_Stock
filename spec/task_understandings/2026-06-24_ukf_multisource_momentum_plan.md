# UKF + Multi-Source Momentum Model Plan

Date: 2026-06-24
Scope: AI Stock / Next-Day Order Planner / Swing Trading technical extension

## Current implementation

The UI now uses a lightweight, dependency-free UKF-style momentum line in the next-day order technical chart. It combines existing in-dashboard indicators into a noisy momentum observation:

- price returns
- RSI14
- MACD histogram
- Bollinger position
- volume ratio
- short-term trend / return context

The filter smooths day-to-day noise and exposes a bounded momentum state for swing trading. This is intentionally a research indicator, not an execution signal and not a trained neural model.

## Why this helps next-day order planning

The existing next-day order planner answers: what buy/sell/stop levels are close enough to be reachable tomorrow?

The UKF momentum layer adds: is the recent move noisy, improving, or deteriorating around those reachable levels?

Practical usage:

- Buy zone + RSI cooling + MACD histogram stabilizing + UKF momentum improving: pullback buy limit has better context.
- Sell zone + RSI overheated + MACD histogram shrinking + UKF momentum rolling over: take-profit / rebound-reduce limit has stronger context.
- Tactical stop near price + UKF momentum falling below neutral: stop alert should be treated more seriously.
- Suggested order level far from price + UKF neutral/noisy: order is more strategic than next-day executable.

## Future model architecture: Neural sequence model + UKF

Target architecture:

1. Multi-source feature builder
   - OHLCV bars from yfinance / Futu OpenD / broker API
   - Existing technical factors: RSI, MACD, KD, Bollinger, ATR, MFI, OBV, volume ratio, support/resistance distance, drawdown
   - Factor research outputs: horizon 1/3/5/10 win rate, AUC, SHAP top-factor direction, grouped win-rate bins
   - Trade Vision outputs: BOS/ChoCH event type, support/demand distance, premium/discount state, MTF trend scores
   - Portfolio state: position size, unrealized PnL, cost distance, concentration, current suggested order type
   - Optional external sentiment/event features

2. Sequence model
   - LSTM baseline for 20/60/120-bar sequence inputs
   - Transformer encoder for multi-horizon inputs once dataset size is large enough
   - Outputs latent forward momentum, uncertainty proxy, and horizon-specific direction probabilities

3. UKF state filter
   - State vector example:
     - latent_momentum
     - latent_trend
     - volatility_regime
     - liquidity_pressure
     - sentiment_pressure
   - Neural model output becomes nonlinear transition / observation input.
   - UKF smooths noisy model output and updates state day by day.

4. Decision fusion
   - Combine UKF state with next-day touch probability.
   - Convert strategy-level price into executable next-session order range.
   - Produce: buy limit zone, sell limit zone, tactical stop, hard stop, order type, confidence, and explanation.

## Candidate data sources for non-price / sentiment / event inputs

## 資料來源候選：非價格、輿論、事件與波動輸入

The current yfinance source mainly provides OHLCV. To move toward the industry-style neural + UKF pipeline, additional time-series inputs are needed.

### Market and macro events

- FRED economic data: rates, inflation, unemployment, yield curve
- Nasdaq / company earnings calendars
- Finnhub earnings calendar and company news API
- Alpha Vantage news sentiment API
- Polygon.io market news and corporate events
- TradingEconomics macro calendar

Usage:
- Convert events into event-distance features: days_to_earnings, is_cpi_week, is_fomc_week, post_earnings_gap.
- Add event volatility regime feature before next-day order planning.

### News and sentiment

- Finnhub company news
- Alpha Vantage news sentiment
- NewsAPI / GDELT for broad news volume
- Reddit / StockTwits / X if credentials and terms allow

Usage:
- Daily sentiment score per ticker
- News volume spike
- Positive/negative headline ratio
- Sentiment surprise compared with 20-day baseline

### Options / volatility

- yfinance options chain when available
- Polygon.io options data
- Tradier options API

Usage:
- Implied volatility percentile
- Put/call skew
- Unusual options volume
- Expected move into next session

### Flow / liquidity

- Volume profile from OHLCV approximation
- Broker/Futu real-time order book if OpenD becomes available
- VWAP / intraday bars if data source supports 1m/5m

Usage:
- Liquidity pressure
- Intraday VWAP distance
- Gap-fill probability
- Whether next-day limit price is realistic given recent intraday ranges

## Implementation roadmap

Phase A: deterministic feature foundation

- Keep current lightweight UKF momentum in chart.
- Add a reusable feature table that joins technical, structure, factor-research, portfolio, and order-planner features by ticker/date.
- Save feature snapshots to runtime cache, not Git.

Phase B: multi-source adapters

- Add optional adapters for news/event/sentiment data.
- All external credentials must live in .env or runtime config and be ignored by Git.
- UI should show missing-source warnings instead of failing.

Phase C: model training experiment

- Add offline notebook/script for LSTM baseline.
- Use time-series split only; no random split.
- Compare against simple baselines: logistic regression, gradient boosting, existing factor research.
- Target: horizon 1/3/5 next-day direction and forward return bucket.

Phase D: UKF fusion

- Feed neural model outputs into UKF state update.
- Produce filtered latent momentum and uncertainty bands.
- Surface this in Next-Day Order Planner as confidence and risk explanation.

Phase E: production UI integration

- Keep model inference opt-in / cached.
- Never auto-place orders.
- Add disclaimer: research aid only.
- Show out-of-sample metrics before allowing users to trust the signal.

## Validation requirements

- Walk-forward validation by time, never random split.
- Per-ticker and pooled-market results separated.
- Report horizon 1/3/5/10 accuracy, AUC, baseline, max drawdown, and order fill simulation.
- Show whether the filtered UKF signal improves next-day order hit quality, not just prediction accuracy.

## Risks

- Sentiment/news data can be noisy and delayed.
- Small sample sizes per ticker can overfit LSTM/Transformer quickly.
- UKF smooths noise but cannot create signal if upstream features are weak.
- High model complexity must not obscure the current transparent order-plan logic.
