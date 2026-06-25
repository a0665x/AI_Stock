from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

from .analytics import add_indicators
from .order_planner import _as_float
from .swing_order_chart import compute_ukf_momentum_state

ORDER_STRATEGIES: dict[str, str] = {
    "bollinger": "布林決策",
    "smc": "SMC 決策",
    "ukf": "UKF 動能決策",
    "kd_macd": "KD/MACD 決策",
    "shap_factor": "SHAP 因子代理決策",
}

BACKTEST_RANGE_DAYS: dict[str, int] = {
    "1周": 7,
    "2周": 14,
    "1個月": 30,
    "3個月": 90,
    "半年": 180,
    "1年": 365,
}

_SUMMARY_COLUMNS = [
    "ticker",
    "strategy",
    "strategy_label",
    "holding_days",
    "risk_tolerance_pct",
    "backtest_range",
    "trade_count",
    "win_rate",
    "avg_return_pct",
    "cumulative_return_pct",
    "max_drawdown_pct",
    "stop_hit_rate",
    "profit_factor",
    "strategy_edge_score",
    "latest_signal",
]

_ORDER_COLUMNS = [
    "ticker",
    "best_strategy",
    "best_strategy_label",
    "holding_days",
    "risk_tolerance_pct",
    "side",
    "urgency_score",
    "strategy_edge_score",
    "buy_low",
    "buy_high",
    "sell_low",
    "sell_high",
    "stop_loss",
    "take_profit",
    "reason",
]


def filter_backtest_window(prices: pd.DataFrame, backtest_range: str) -> pd.DataFrame:
    """Return the trailing date window requested by the UI.

    Unknown labels fall back to the full input so custom ranges never crash.
    """
    if prices.empty or "date" not in prices.columns:
        return prices.copy()
    days = BACKTEST_RANGE_DAYS.get(str(backtest_range))
    if not days:
        return prices.copy()
    out = prices.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    max_date = out["date"].max()
    if pd.isna(max_date):
        return prices.copy()
    return out[out["date"] >= max_date - pd.Timedelta(days=int(days))].copy()


def _select_tickers(prices: pd.DataFrame, selected_tickers: str | Iterable[str]) -> list[str]:
    if prices.empty or "ticker" not in prices.columns:
        return []
    available = sorted(prices["ticker"].dropna().astype(str).str.upper().unique())
    if selected_tickers == "ALL":
        return available
    selected = {str(t).upper() for t in selected_tickers if str(t).strip()} if not isinstance(selected_tickers, str) else {selected_tickers.upper()}
    return [ticker for ticker in available if ticker in selected]


def _empty_summary() -> pd.DataFrame:
    return pd.DataFrame(columns=_SUMMARY_COLUMNS)


def _empty_trades() -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "strategy", "entry_date", "exit_date", "entry_price", "exit_price", "return_pct", "stop_hit", "signal"])


def _signal_from_row(row: pd.Series, strategy: str) -> tuple[int, str, float]:
    close = _as_float(row.get("close"), np.nan)
    if not np.isfinite(close):
        return 0, "NO_DATA", 0.0
    rsi = _as_float(row.get("rsi_14"), 50.0)
    macd_hist = _as_float(row.get("macd_hist"), 0.0)
    bb_pos = _as_float(row.get("bb_position_20"), 0.5)
    k = _as_float(row.get("stoch_k_14"), 50.0)
    d = _as_float(row.get("stoch_d_3"), 50.0)
    ret5 = _as_float(row.get("return_5d"), 0.0)
    ret20 = _as_float(row.get("return_20d"), 0.0)
    volume_ratio = _as_float(row.get("volume_ratio_20d"), 1.0)
    ukf = _as_float(row.get("ukf_momentum", 50.0), 50.0)
    smc_bias = str(row.get("smc_bias", "MIXED")).upper()
    smc_conf = _as_float(row.get("smc_confidence_score"), 50.0)

    if strategy == "bollinger":
        if bb_pos <= 0.20 and rsi < 48:
            return 1, "BOLLINGER_DISCOUNT_BOUNCE", min(100.0, (0.25 - bb_pos) * 180 + (50 - rsi))
        if bb_pos >= 0.80 and rsi > 55:
            return -1, "BOLLINGER_PREMIUM_FADE", min(100.0, (bb_pos - 0.75) * 180 + (rsi - 50))
        return 0, "BOLLINGER_NEUTRAL", 35.0
    if strategy == "smc":
        if smc_bias == "BULLISH" and smc_conf >= 55:
            return 1, "SMC_BULLISH_ALIGNMENT", smc_conf
        if smc_bias == "BEARISH" and smc_conf >= 55:
            return -1, "SMC_BEARISH_ALIGNMENT", smc_conf
        return 0, "SMC_MIXED", smc_conf * 0.55
    if strategy == "ukf":
        if ukf >= 58:
            return 1, "UKF_BULLISH_MOMENTUM", ukf
        if ukf <= 42:
            return -1, "UKF_BEARISH_MOMENTUM", 100 - ukf
        return 0, "UKF_NEUTRAL", abs(ukf - 50) * 2
    if strategy == "kd_macd":
        if k > d and macd_hist > 0 and rsi < 72:
            return 1, "KD_MACD_BULLISH", min(100.0, 45 + abs(k - d) + macd_hist * 150 + max(volume_ratio - 1, 0) * 12)
        if k < d and macd_hist < 0:
            return -1, "KD_MACD_BEARISH", min(100.0, 45 + abs(k - d) + abs(macd_hist) * 150)
        return 0, "KD_MACD_NEUTRAL", 35.0
    if strategy == "shap_factor":
        # Lightweight proxy: use the same families the SHAP/factor page often ranks highly
        # without triggering an expensive model run on this actionable planning page.
        factor_score = ret5 * 0.45 + ret20 * 0.35 + macd_hist * 0.12 + (volume_ratio - 1) * 0.08
        if factor_score > 0.004:
            return 1, "FACTOR_PROXY_BULLISH", min(100.0, 50 + factor_score * 1800)
        if factor_score < -0.004:
            return -1, "FACTOR_PROXY_BEARISH", min(100.0, 50 + abs(factor_score) * 1800)
        return 0, "FACTOR_PROXY_NEUTRAL", 35.0
    return 0, "UNKNOWN_STRATEGY", 0.0


def _prepare_strategy_frame(one: pd.DataFrame) -> pd.DataFrame:
    enriched = add_indicators(one.sort_values("date").copy())
    ukf = compute_ukf_momentum_state(enriched)
    if not ukf.empty:
        enriched = enriched.merge(ukf[["date", "ukf_momentum"]], on="date", how="left")
    if "ukf_momentum" not in enriched.columns:
        enriched["ukf_momentum"] = 50.0
    return enriched


def _profit_factor(returns: pd.Series) -> float:
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def _max_drawdown_from_returns(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    return float(drawdown.min() * 100)


def _run_strategy_backtest(one: pd.DataFrame, ticker: str, strategy: str, holding_days: int, risk_tolerance_pct: float) -> tuple[dict[str, Any], pd.DataFrame]:
    data = _prepare_strategy_frame(one)
    trades: list[dict[str, Any]] = []
    if len(data) <= holding_days + 35:
        return _summary_row(ticker, strategy, holding_days, risk_tolerance_pct, pd.DataFrame(), "NO_DATA"), _empty_trades()
    step = max(1, int(holding_days))
    for entry_idx in range(35, len(data) - holding_days, step):
        row = data.iloc[entry_idx]
        direction, signal, _strength = _signal_from_row(row, strategy)
        if direction == 0:
            continue
        entry = _as_float(row.get("close"), np.nan)
        if not np.isfinite(entry) or entry <= 0:
            continue
        future = data.iloc[entry_idx + 1 : entry_idx + holding_days + 1]
        if future.empty:
            continue
        stop_pct = max(float(risk_tolerance_pct), 1.0) / 100.0
        if direction > 0:
            stop_price = entry * (1 - stop_pct)
            stop_hits = future[future["low"] <= stop_price]
            if not stop_hits.empty:
                exit_row = stop_hits.iloc[0]
                exit_price = stop_price
                stop_hit = True
            else:
                exit_row = future.iloc[-1]
                exit_price = _as_float(exit_row.get("close"), entry)
                stop_hit = False
            ret = exit_price / entry - 1
        else:
            stop_price = entry * (1 + stop_pct)
            stop_hits = future[future["high"] >= stop_price]
            if not stop_hits.empty:
                exit_row = stop_hits.iloc[0]
                exit_price = stop_price
                stop_hit = True
            else:
                exit_row = future.iloc[-1]
                exit_price = _as_float(exit_row.get("close"), entry)
                stop_hit = False
            ret = entry / exit_price - 1 if exit_price > 0 else 0.0
        trades.append(
            {
                "ticker": ticker,
                "strategy": strategy,
                "entry_date": row.get("date"),
                "exit_date": exit_row.get("date"),
                "entry_price": float(entry),
                "exit_price": float(exit_price),
                "return_pct": float(ret),
                "stop_hit": bool(stop_hit),
                "signal": signal,
            }
        )
    trades_df = pd.DataFrame(trades)
    latest_signal = _signal_from_row(data.iloc[-1], strategy)[1] if not data.empty else "NO_DATA"
    return _summary_row(ticker, strategy, holding_days, risk_tolerance_pct, trades_df, latest_signal), trades_df


def _summary_row(ticker: str, strategy: str, holding_days: int, risk_tolerance_pct: float, trades: pd.DataFrame, latest_signal: str) -> dict[str, Any]:
    returns = trades["return_pct"] if not trades.empty and "return_pct" in trades.columns else pd.Series(dtype=float)
    wins = returns > 0
    cumulative = float((1 + returns).prod() - 1) if not returns.empty else 0.0
    win_rate = float(wins.mean()) if not returns.empty else np.nan
    avg = float(returns.mean() * 100) if not returns.empty else np.nan
    pf = _profit_factor(returns) if not returns.empty else np.nan
    max_dd = _max_drawdown_from_returns(returns)
    stop_rate = float(trades["stop_hit"].mean()) if not trades.empty and "stop_hit" in trades.columns else np.nan
    pf_score = min(100.0, (pf if np.isfinite(pf) else 3.0) / 2.0 * 50) if not np.isnan(pf) else 25.0
    win_score = (win_rate * 100) if not np.isnan(win_rate) else 25.0
    ret_score = np.clip(50 + cumulative * 120, 0, 100)
    dd_score = np.clip(100 + max_dd * 3, 0, 100)
    edge = float(np.clip(win_score * 0.35 + pf_score * 0.25 + ret_score * 0.25 + dd_score * 0.15, 0, 100))
    return {
        "ticker": ticker,
        "strategy": strategy,
        "strategy_label": ORDER_STRATEGIES.get(strategy, strategy),
        "holding_days": int(holding_days),
        "risk_tolerance_pct": float(risk_tolerance_pct),
        "backtest_range": "",
        "trade_count": int(len(trades)),
        "win_rate": win_rate,
        "avg_return_pct": avg,
        "cumulative_return_pct": float(cumulative * 100),
        "max_drawdown_pct": max_dd,
        "stop_hit_rate": stop_rate,
        "profit_factor": pf,
        "strategy_edge_score": edge,
        "latest_signal": latest_signal,
    }


def _merge_order_recommendations(summary: pd.DataFrame, next_day_plan: pd.DataFrame, risk_tolerance_pct: float) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=_ORDER_COLUMNS)
    best = summary.sort_values(["ticker", "strategy_edge_score", "trade_count"], ascending=[True, False, False]).groupby("ticker", as_index=False).head(1)
    rows: list[dict[str, Any]] = []
    for _, row in best.iterrows():
        ticker = str(row["ticker"])
        plan_row = next_day_plan[next_day_plan["ticker"].astype(str).str.upper() == ticker].tail(1) if not next_day_plan.empty and "ticker" in next_day_plan.columns else pd.DataFrame()
        prow = plan_row.iloc[0] if not plan_row.empty else pd.Series(dtype=object)
        current = _as_float(prow.get("current_price"), np.nan)
        buy_low = _as_float(prow.get("next_day_buy_low"), current * 0.99 if np.isfinite(current) else np.nan)
        buy_high = _as_float(prow.get("next_day_buy_high"), current * 0.995 if np.isfinite(current) else np.nan)
        sell_low = _as_float(prow.get("next_day_sell_low"), current * 1.005 if np.isfinite(current) else np.nan)
        sell_high = _as_float(prow.get("next_day_sell_high"), current * 1.01 if np.isfinite(current) else np.nan)
        stop = _as_float(prow.get("tactical_stop_price"), current * (1 - risk_tolerance_pct / 100) if np.isfinite(current) else np.nan)
        signal = str(row.get("latest_signal", ""))
        side = "BUY" if "BULL" in signal or "DISCOUNT" in signal else "SELL" if "BEAR" in signal or "PREMIUM" in signal else "WAIT"
        base_urg = _as_float(row.get("strategy_edge_score"), 0.0)
        plan_urg = max(_as_float(prow.get("buy_urgency_score"), 0.0), _as_float(prow.get("sell_urgency_score"), 0.0))
        urgency = float(np.clip(base_urg * 0.65 + plan_urg * 0.35, 0, 100))
        if side == "WAIT":
            urgency *= 0.65
        rows.append(
            {
                "ticker": ticker,
                "best_strategy": str(row.get("strategy", "")),
                "best_strategy_label": str(row.get("strategy_label", "")),
                "holding_days": int(row.get("holding_days", 0)),
                "risk_tolerance_pct": float(risk_tolerance_pct),
                "side": side,
                "urgency_score": urgency,
                "strategy_edge_score": base_urg,
                "buy_low": buy_low,
                "buy_high": buy_high,
                "sell_low": sell_low,
                "sell_high": sell_high,
                "stop_loss": stop,
                "take_profit": sell_low if side in {"BUY", "WAIT"} else sell_high,
                "reason": f"最佳策略：{row.get('strategy_label', row.get('strategy'))}；近端回測 edge {base_urg:.0f}，結合隔日掛單急迫度 {plan_urg:.0f}。",
            }
        )
    return pd.DataFrame(rows, columns=_ORDER_COLUMNS).sort_values("urgency_score", ascending=False).reset_index(drop=True)


def build_order_strategy_workbench(
    prices: pd.DataFrame,
    next_day_order_plan: pd.DataFrame,
    *,
    selected_tickers: str | Iterable[str] = "ALL",
    strategies: Iterable[str] = tuple(ORDER_STRATEGIES),
    holding_days: int = 5,
    risk_tolerance_pct: float = 10.0,
    backtest_range: str = "3個月",
) -> dict[str, pd.DataFrame]:
    """Backtest selectable next-day order strategies and rank actionable levels.

    This is intentionally lightweight and deterministic. It answers which strategy
    family historically fits each ticker better for the selected holding horizon;
    it does not place broker orders.
    """
    if prices.empty or "ticker" not in prices.columns:
        return {"summary": _empty_summary(), "trades": _empty_trades(), "order_recommendations": pd.DataFrame(columns=_ORDER_COLUMNS), "strategy_scores": pd.DataFrame()}
    scoped = filter_backtest_window(prices, backtest_range)
    tickers = _select_tickers(scoped, selected_tickers)
    selected_strategies = [s for s in strategies if s in ORDER_STRATEGIES]
    if not tickers or not selected_strategies:
        return {"summary": _empty_summary(), "trades": _empty_trades(), "order_recommendations": pd.DataFrame(columns=_ORDER_COLUMNS), "strategy_scores": pd.DataFrame()}
    summaries: list[dict[str, Any]] = []
    trades: list[pd.DataFrame] = []
    for ticker in tickers:
        one = scoped[scoped["ticker"].astype(str).str.upper() == ticker].sort_values("date").copy()
        for strategy in selected_strategies:
            summary, trade_df = _run_strategy_backtest(one, ticker, strategy, int(holding_days), float(risk_tolerance_pct))
            summary["backtest_range"] = str(backtest_range)
            summaries.append(summary)
            if not trade_df.empty:
                trades.append(trade_df)
    summary_df = pd.DataFrame(summaries, columns=_SUMMARY_COLUMNS)
    trades_df = pd.concat(trades, ignore_index=True) if trades else _empty_trades()
    orders = _merge_order_recommendations(summary_df, next_day_order_plan, risk_tolerance_pct)
    scores = summary_df.pivot_table(index="ticker", columns="strategy_label", values="strategy_edge_score", aggfunc="max").reset_index() if not summary_df.empty else pd.DataFrame()
    return {"summary": summary_df, "trades": trades_df, "order_recommendations": orders, "strategy_scores": scores}
