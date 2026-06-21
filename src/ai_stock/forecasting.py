from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor, LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .analytics import add_indicators, compute_correlation_table, compute_relationship_pressure


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


def _kelly_reason(expected_return: float, risk_unit: float, kelly_fraction: float, win_rate: float = 0.52) -> str:
    if not np.isfinite(expected_return) or not np.isfinite(risk_unit) or risk_unit <= 0:
        return "Kelly 為 0：缺少足夠或有效的預估報酬 / 風險資料。"
    edge_pct = expected_return * 100
    risk_pct = risk_unit * 100
    break_even_edge = ((1 - win_rate) / win_rate) * risk_unit * 100
    if kelly_fraction <= 0:
        return (
            f"Kelly 為 0：預估報酬 {edge_pct:+.2f}%，風險單位 {risk_pct:.2f}%，"
            f"在保守勝率假設 {win_rate:.0%} 下，約需大於 {break_even_edge:.2f}% 的優勢才值得配置。"
        )
    return f"Kelly {kelly_fraction * 100:.1f}%：預估報酬 {edge_pct:+.2f}% 相對風險單位 {risk_pct:.2f}% 已有正優勢，但仍已套用半 Kelly 保守折減。"


def _action_reason(action: str, expected_return: float, decision_threshold: float, drawdown_penalty: float) -> str:
    edge_pct = expected_return * 100
    threshold_pct = decision_threshold * 100
    drawdown_penalty_pct = drawdown_penalty * 100
    if action == "BUY_WATCH":
        return f"偏多觀察：預估報酬 {edge_pct:+.2f}% 高於買進門檻 {threshold_pct:.2f}%；門檻已納入波動與回撤懲罰 {drawdown_penalty_pct:.2f}%。"
    if action == "SELL_OR_AVOID":
        return f"減碼/避開：預估報酬 {edge_pct:+.2f}% 低於負向門檻 -{threshold_pct:.2f}%；風險報酬不對稱。"
    return f"等待確認：預估報酬 {edge_pct:+.2f}% 仍在 ±{threshold_pct:.2f}% 門檻內；代表模型優勢尚未明顯大過近期波動與回撤風險。"


def _forecast_arima(close: pd.Series, horizon: int) -> tuple[float, str]:
    from statsmodels.tsa.arima.model import ARIMA

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(close.astype(float), order=(1, 1, 1)).fit()
        pred = model.forecast(steps=horizon)
    return float(pred.iloc[-1]), "arima"


def _forecast_linear(features: pd.DataFrame, horizon: int) -> tuple[float, str]:
    work = features.dropna().copy()
    feature_cols = [
        "return_1d",
        "return_5d",
        "return_20d",
        "rsi_14",
        "macd_hist",
        "volatility_20d",
        "volume_ratio_20d",
        "distance_sma20",
        "distance_sma60",
        "bb_position_20",
        "atr_pct_14",
        "stoch_k_14",
        "mfi_14",
        "drawdown_from_60d_high",
        "max_drawdown_60d",
    ]
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
    latest = enriched.dropna(subset=["close"]).tail(1).iloc[0]
    max_drawdown_60d = float(latest.get("max_drawdown_60d", np.nan))
    drawdown_from_high = float(latest.get("drawdown_from_60d_high", np.nan))
    atr_pct = float(latest.get("atr_pct_14", np.nan))
    risk_unit = max(v for v in [vol, atr_pct, 0.01] if np.isfinite(v))
    kelly = _kelly_fraction(expected_return, risk_unit)
    recent_low = float(enriched["low"].tail(20).min())
    recent_high = float(enriched["high"].tail(20).max())
    support = float(latest.get("support_20", recent_low)) if np.isfinite(float(latest.get("support_20", np.nan))) else recent_low
    resistance = float(latest.get("resistance_20", recent_high)) if np.isfinite(float(latest.get("resistance_20", np.nan))) else recent_high
    buy_price = min(last_close * (1 - risk_unit), support)
    sell_price = max(last_close * (1 + risk_unit), resistance, predicted_price)
    stop_loss = min(last_close * (1 - max(risk_unit * 1.5, 0.03)), support * 0.98)

    drawdown_penalty = abs(max_drawdown_60d) * 0.25 if np.isfinite(max_drawdown_60d) else 0.0
    decision_threshold = max(risk_unit + drawdown_penalty, 0.01)
    if expected_return > decision_threshold:
        action = "BUY_WATCH"
    elif expected_return < -decision_threshold:
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
        "action_reason": _action_reason(action, expected_return, decision_threshold, drawdown_penalty),
        "kelly_reason": _kelly_reason(expected_return, risk_unit, kelly),
        "risk_unit_pct": risk_unit * 100,
        "drawdown_from_60d_high_pct": drawdown_from_high * 100 if np.isfinite(drawdown_from_high) else np.nan,
        "max_drawdown_60d_pct": max_drawdown_60d * 100 if np.isfinite(max_drawdown_60d) else np.nan,
        "atr_pct_14": atr_pct * 100 if np.isfinite(atr_pct) else np.nan,
        "rsi_14": float(latest.get("rsi_14", np.nan)),
        "bb_position_20": float(latest.get("bb_position_20", np.nan)),
        "mfi_14": float(latest.get("mfi_14", np.nan)),
    }


def build_decision_report(prices: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    rows = []
    sorted_prices = prices.sort_values(["ticker", "date"])
    for _, group in sorted_prices.groupby("ticker"):
        if len(group) < max(40, horizon + 10):
            continue
        rows.append(forecast_one_ticker(group.reset_index(drop=True), horizon=horizon))
    if not rows:
        return pd.DataFrame()
    report = pd.DataFrame(rows)
    correlations = compute_correlation_table(sorted_prices)
    pressure = compute_relationship_pressure(sorted_prices, correlations)
    if not pressure.empty:
        report = report.merge(pressure, on="ticker", how="left")
    relationship_cols = ["relationship_pressure_5d", "positive_corr_pressure_5d", "negative_corr_pressure_5d"]
    for col in relationship_cols:
        if col in report.columns:
            report[col] = report[col] * 100
    if "relationship_pressure_5d" in report.columns:
        # Conservative: peer relationship context influences the displayed edge,
        # but only at 25% weight so correlation is not mistaken for causality.
        report["relationship_adjusted_return_pct"] = report["expected_return_pct"] + report["relationship_pressure_5d"].fillna(0) * 0.25
    else:
        report["relationship_adjusted_return_pct"] = report["expected_return_pct"]
    return report.sort_values("relationship_adjusted_return_pct", ascending=False).reset_index(drop=True)
