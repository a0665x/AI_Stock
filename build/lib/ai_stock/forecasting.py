from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor, LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .analytics import add_indicators


def _kelly_fraction(expected_return: float, volatility: float, win_rate: float = 0.52) -> float:
    """Conservative Kelly sizing from expected return and realized volatility.

    Uses a payoff ratio proxy so the report stays model-light and explainable.
    """
    if not np.isfinite(expected_return) or not np.isfinite(volatility) or volatility <= 0:
        return 0.0
    payoff = abs(expected_return) / volatility
    if payoff <= 0:
        return 0.0
    fraction = win_rate - (1 - win_rate) / payoff
    return float(np.clip(fraction * 0.5, 0.0, 1.0))  # half-Kelly cap


def _forecast_arima(close: pd.Series, horizon: int) -> tuple[float, str]:
    from statsmodels.tsa.arima.model import ARIMA

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(close.astype(float), order=(1, 1, 1)).fit()
        pred = model.forecast(steps=horizon)
    return float(pred.iloc[-1]), "arima"


def _forecast_linear(features: pd.DataFrame, horizon: int) -> tuple[float, str]:
    work = features.dropna().copy()
    feature_cols = ["return_1d", "return_5d", "return_20d", "rsi_14", "macd_hist", "volatility_20d", "volume_ratio_20d"]
    work["target"] = work["close"].shift(-horizon)
    train = work.dropna(subset=feature_cols + ["target"])
    if len(train) < 30:
        x = np.arange(len(work)).reshape(-1, 1)
        y = work["close"].to_numpy(dtype=float)
        model = LinearRegression().fit(x, y)
        return float(model.predict([[len(work) + horizon - 1]])[0]), "linear_regression"
    x_train = train[feature_cols]
    y_train = train["target"]
    model = make_pipeline(StandardScaler(), HuberRegressor())
    model.fit(x_train, y_train)
    latest = work[feature_cols].dropna().tail(1)
    return float(model.predict(latest)[0]), "linear_regression"


def forecast_one_ticker(prices: pd.DataFrame, horizon: int = 5) -> dict:
    enriched = add_indicators(prices)
    close = enriched["close"].dropna()
    last_close = float(close.iloc[-1])
    try:
        predicted_price, model_name = _forecast_arima(close.tail(260), horizon)
    except Exception:
        predicted_price, model_name = _forecast_linear(enriched, horizon)

    expected_return = predicted_price / last_close - 1
    vol = float(enriched["return_1d"].tail(60).std() * np.sqrt(horizon))
    kelly = _kelly_fraction(expected_return, vol)
    recent_low = float(enriched["low"].tail(20).min())
    recent_high = float(enriched["high"].tail(20).max())
    buy_price = min(last_close * (1 - max(vol, 0.01)), recent_low)
    sell_price = max(last_close * (1 + max(vol, 0.01)), recent_high, predicted_price)
    stop_loss = last_close * (1 - max(vol * 1.5, 0.03))

    if expected_return > max(vol, 0.01):
        action = "BUY_WATCH"
    elif expected_return < -max(vol, 0.01):
        action = "SELL_OR_AVOID"
    else:
        action = "HOLD_WAIT"

    return {
        "ticker": str(prices["ticker"].iloc[0]),
        "last_close": last_close,
        "predicted_price": predicted_price,
        "expected_return_pct": expected_return * 100,
        "model": model_name,
        "kelly_fraction": kelly,
        "suggested_buy_price": float(buy_price),
        "suggested_sell_price": float(sell_price),
        "stop_loss_price": float(stop_loss),
        "action": action,
    }


def build_decision_report(prices: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    rows = []
    for _, group in prices.sort_values(["ticker", "date"]).groupby("ticker"):
        if len(group) < max(40, horizon + 10):
            continue
        rows.append(forecast_one_ticker(group.reset_index(drop=True), horizon=horizon))
    return pd.DataFrame(rows).sort_values("expected_return_pct", ascending=False).reset_index(drop=True) if rows else pd.DataFrame()
