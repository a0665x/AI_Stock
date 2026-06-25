from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .analytics import add_indicators
from .order_planner import _as_float
from .smc_adapter import build_smc_context
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
    return pd.DataFrame(
        columns=[
            "ticker",
            "strategy",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "return_pct",
            "stop_hit",
            "signal",
            "direction",
        ]
    )


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
    """Run a stateful, non-overlapping strategy simulation.

    Earlier versions sampled every ``holding_days`` bars independently. That made
    charts confusing because one trade could exit on the same date the next trade
    entered, and short entries were still drawn as BUY markers. This routine uses
    a simple position state machine: only enter when flat, exit by stop or time,
    then wait at least one full bar before considering the next entry.
    """
    data = _prepare_strategy_frame(one)
    trades: list[dict[str, Any]] = []
    horizon = max(1, int(holding_days))
    cooldown_bars = 1
    if len(data) <= horizon + 35:
        return _summary_row(ticker, strategy, horizon, risk_tolerance_pct, pd.DataFrame(), "NO_DATA"), _empty_trades()

    entry_idx = 35
    last_exit_idx = -cooldown_bars - 2
    while entry_idx < len(data) - horizon:
        if entry_idx <= last_exit_idx + cooldown_bars:
            entry_idx += 1
            continue
        row = data.iloc[entry_idx]
        direction, signal, _strength = _signal_from_row(row, strategy)
        if direction == 0:
            entry_idx += 1
            continue
        entry = _as_float(row.get("close"), np.nan)
        if not np.isfinite(entry) or entry <= 0:
            entry_idx += 1
            continue
        future = data.iloc[entry_idx + 1 : entry_idx + horizon + 1]
        if future.empty:
            break
        stop_pct = max(float(risk_tolerance_pct), 1.0) / 100.0
        if direction > 0:
            stop_price = entry * (1 - stop_pct)
            stop_hits = future[future["low"] <= stop_price]
            if not stop_hits.empty:
                exit_label = stop_hits.index[0]
                exit_idx = int(data.index.get_loc(exit_label))
                exit_row = data.iloc[exit_idx]
                exit_price = stop_price
                stop_hit = True
            else:
                exit_idx = min(entry_idx + horizon, len(data) - 1)
                exit_row = data.iloc[exit_idx]
                exit_price = _as_float(exit_row.get("close"), entry)
                stop_hit = False
            ret = exit_price / entry - 1
        else:
            stop_price = entry * (1 + stop_pct)
            stop_hits = future[future["high"] >= stop_price]
            if not stop_hits.empty:
                exit_label = stop_hits.index[0]
                exit_idx = int(data.index.get_loc(exit_label))
                exit_row = data.iloc[exit_idx]
                exit_price = stop_price
                stop_hit = True
            else:
                exit_idx = min(entry_idx + horizon, len(data) - 1)
                exit_row = data.iloc[exit_idx]
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
                "direction": int(direction),
            }
        )
        last_exit_idx = exit_idx
        entry_idx = exit_idx + cooldown_bars + 1
    trades_df = pd.DataFrame(trades, columns=_empty_trades().columns) if trades else _empty_trades()
    latest_signal = _signal_from_row(data.iloc[-1], strategy)[1] if not data.empty else "NO_DATA"
    return _summary_row(ticker, strategy, horizon, risk_tolerance_pct, trades_df, latest_signal), trades_df


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


def _empty_strategy_visualization_payload(ticker: str) -> dict[str, Any]:
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.46, 0.13, 0.13, 0.13, 0.15],
        subplot_titles=(f"{ticker} Strategy Price Signals", "Volume", "RSI14", "MACD", "Equity / Drawdown"),
        specs=[[{}], [{}], [{}], [{}], [{"secondary_y": True}]],
    )
    return {
        "figure": fig,
        "equity_curve": pd.DataFrame(columns=["date", "strategy", "equity"]),
        "drawdown_curve": pd.DataFrame(columns=["date", "strategy", "drawdown_pct"]),
        "trade_markers": pd.DataFrame(columns=["date", "price", "strategy", "side", "return_pct"]),
        "strategy_metrics": pd.DataFrame(columns=["strategy", "trade_count", "win_rate", "cumulative_return_pct", "max_drawdown_pct", "profit_factor"]),
    }


def _strategy_trades_for_selection(trades: pd.DataFrame, ticker: str, strategies: Iterable[str]) -> pd.DataFrame:
    if trades.empty or "ticker" not in trades.columns:
        return _empty_trades()
    selected = {str(s) for s in strategies}
    out = trades[trades["ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
    if "strategy" in out.columns and selected and "COMPOSITE" not in selected:
        out = out[out["strategy"].astype(str).isin(selected)]
    elif "strategy" in out.columns and selected and "COMPOSITE" in selected:
        out = out[out["strategy"].astype(str).isin(selected - {"COMPOSITE"})]
    return out.sort_values("exit_date") if "exit_date" in out.columns else out


def _equity_and_drawdown_from_trades(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return (
            pd.DataFrame(columns=["date", "strategy", "equity"]),
            pd.DataFrame(columns=["date", "strategy", "drawdown_pct"]),
            pd.DataFrame(columns=["strategy", "trade_count", "win_rate", "cumulative_return_pct", "max_drawdown_pct", "profit_factor"]),
        )
    rows_equity: list[dict[str, Any]] = []
    rows_drawdown: list[dict[str, Any]] = []
    rows_metrics: list[dict[str, Any]] = []
    grouped = list(trades.groupby("strategy")) if "strategy" in trades.columns else [("COMPOSITE", trades)]
    if len(grouped) > 1:
        grouped.append(("COMPOSITE", trades))
    for strategy, group in grouped:
        group = group.sort_values("exit_date").copy()
        returns = pd.to_numeric(group.get("return_pct"), errors="coerce").fillna(0.0)
        equity = (1 + returns).cumprod()
        peak = equity.cummax()
        drawdown = equity / peak - 1
        for idx, (_gidx, row) in enumerate(group.iterrows()):
            date = row.get("exit_date", row.get("entry_date"))
            rows_equity.append({"date": date, "strategy": strategy, "equity": float(equity.iloc[idx])})
            rows_drawdown.append({"date": date, "strategy": strategy, "drawdown_pct": float(drawdown.iloc[idx] * 100)})
        rows_metrics.append(
            {
                "strategy": strategy,
                "trade_count": int(len(group)),
                "win_rate": float((returns > 0).mean()) if len(group) else np.nan,
                "cumulative_return_pct": float((equity.iloc[-1] - 1) * 100) if len(group) else 0.0,
                "max_drawdown_pct": float(drawdown.min() * 100) if len(group) else 0.0,
                "profit_factor": _profit_factor(returns),
            }
        )
    return pd.DataFrame(rows_equity), pd.DataFrame(rows_drawdown), pd.DataFrame(rows_metrics)


def _trade_markers_from_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["date", "price", "strategy", "side", "return_pct"])
    rows: list[dict[str, Any]] = []
    for _, row in trades.iterrows():
        strategy = row.get("strategy", "")
        ret = _as_float(row.get("return_pct"), 0.0)
        direction = int(_as_float(row.get("direction", 1), 1))
        if direction < 0:
            rows.append({"date": row.get("entry_date"), "price": row.get("entry_price"), "strategy": strategy, "side": "SELL", "return_pct": ret})
            rows.append({"date": row.get("exit_date"), "price": row.get("exit_price"), "strategy": strategy, "side": "BUY_TO_COVER", "return_pct": ret})
        else:
            rows.append({"date": row.get("entry_date"), "price": row.get("entry_price"), "strategy": strategy, "side": "BUY", "return_pct": ret})
            rows.append({"date": row.get("exit_date"), "price": row.get("exit_price"), "strategy": strategy, "side": "SELL", "return_pct": ret})
    return pd.DataFrame(rows)


def _add_trade_lifecycle_annotations(fig: go.Figure, trades: pd.DataFrame, data: pd.DataFrame) -> None:
    """Draw entry/exit vertical lines plus per-trade PnL connectors on row 1.

    Marker-only strategy charts are hard to scan.  These annotations make each
    simulated position visible as a lifecycle: entry line, exit line, and the
    dashed connector between the two prices.  Green means the completed trade
    made money; red means it lost money.  This is about realized backtest PnL,
    not SHAP/factor contribution direction.
    """
    if trades.empty or data.empty:
        return
    price_min = _as_float(pd.to_numeric(data["low"], errors="coerce").min(), np.nan)
    price_max = _as_float(pd.to_numeric(data["high"], errors="coerce").max(), np.nan)
    if not np.isfinite(price_min) or not np.isfinite(price_max) or price_min >= price_max:
        return
    plotted_trade_names: set[str] = set()
    for _, row in trades.iterrows():
        entry_date = row.get("entry_date")
        exit_date = row.get("exit_date")
        entry_price = _as_float(row.get("entry_price"), np.nan)
        exit_price = _as_float(row.get("exit_price"), np.nan)
        ret = _as_float(row.get("return_pct"), np.nan)
        if pd.isna(entry_date) or pd.isna(exit_date) or not np.isfinite(entry_price) or not np.isfinite(exit_price):
            continue
        win = bool(np.isfinite(ret) and ret >= 0)
        color = "#16a34a" if win else "#dc2626"
        fill = "rgba(22,163,74,0.08)" if win else "rgba(220,38,38,0.08)"
        pnl_name = "Trade PnL Win" if win else "Trade PnL Loss"
        fig.add_shape(
            type="line",
            x0=entry_date,
            x1=entry_date,
            y0=price_min,
            y1=price_max,
            line=dict(color="#0f172a", width=1, dash="dot"),
            name="Trade Entry Vertical Line",
            row=1,
            col=1,
        )
        fig.add_shape(
            type="line",
            x0=exit_date,
            x1=exit_date,
            y0=price_min,
            y1=price_max,
            line=dict(color=color, width=1, dash="dot"),
            name="Trade Exit Vertical Line",
            row=1,
            col=1,
        )
        fig.add_shape(
            type="rect",
            x0=entry_date,
            x1=exit_date,
            y0=min(entry_price, exit_price),
            y1=max(entry_price, exit_price),
            fillcolor=fill,
            line=dict(width=0),
            layer="below",
            name="Trade Profit Area" if win else "Trade Loss Area",
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[entry_date, exit_date],
                y=[entry_price, exit_price],
                mode="lines+markers",
                name=pnl_name,
                legendgroup=pnl_name,
                showlegend=pnl_name not in plotted_trade_names,
                line=dict(color=color, width=2, dash="dash"),
                marker=dict(size=7, color=color),
                customdata=[[row.get("strategy", ""), ret], [row.get("strategy", ""), ret]],
                hovertemplate="%{customdata[0]} trade<br>%{x}<br>price=%{y:.2f}<br>PnL=%{customdata[1]:.2%}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        plotted_trade_names.add(pnl_name)
        mid_price = (entry_price + exit_price) / 2
        fig.add_annotation(
            x=exit_date,
            y=mid_price,
            text=f"{ret:+.2%}" if np.isfinite(ret) else "n/a",
            showarrow=True,
            arrowhead=2,
            arrowcolor=color,
            font=dict(color=color, size=11),
            bgcolor="rgba(255,255,255,0.78)",
            bordercolor=color,
            borderwidth=1,
            row=1,
            col=1,
        )


def build_strategy_visualization_payload(
    prices: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    ticker: str,
    strategies: Iterable[str] = ("COMPOSITE",),
    order_recommendations: pd.DataFrame | None = None,
    show_smc: bool = True,
) -> dict[str, Any]:
    """Build a strategy visualization payload for the Streamlit workbench.

    The figure keeps strategy-level evidence in one place: price candles, indicator
    traces, buy/sell markers from the selected strategy trades, optional SMC zones,
    and an equity/drawdown panel. It is research-only and does not place orders.
    """
    if prices.empty or "ticker" not in prices.columns:
        return _empty_strategy_visualization_payload(ticker)
    one = prices[prices["ticker"].astype(str).str.upper() == str(ticker).upper()].sort_values("date").copy()
    if one.empty:
        return _empty_strategy_visualization_payload(ticker)
    data = add_indicators(one)
    selected_trades = _strategy_trades_for_selection(trades, ticker, strategies)
    equity, drawdown, metrics = _equity_and_drawdown_from_trades(selected_trades)
    markers = _trade_markers_from_trades(selected_trades)

    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.46, 0.13, 0.13, 0.13, 0.15],
        subplot_titles=(f"{ticker} Strategy Price Signals", "Volume", "RSI14", "MACD", "Equity / Drawdown"),
        specs=[[{}], [{}], [{}], [{}], [{"secondary_y": True}]],
    )
    fig.add_trace(
        go.Candlestick(
            x=data["date"], open=data["open"], high=data["high"], low=data["low"], close=data["close"], name="K線",
            increasing_line_color="#16a34a", decreasing_line_color="#dc2626",
        ),
        row=1,
        col=1,
    )
    for col, name, color in [("sma_20", "SMA20", "#2563eb"), ("sma_60", "SMA60", "#9333ea"), ("bb_upper_20", "Bollinger Upper", "#94a3b8"), ("bb_lower_20", "Bollinger Lower", "#94a3b8")]:
        if col in data.columns:
            fig.add_trace(go.Scatter(x=data["date"], y=data[col], mode="lines", name=name, line=dict(color=color, width=1.2)), row=1, col=1)
    volume_colors = np.where(pd.to_numeric(data["close"], errors="coerce") >= pd.to_numeric(data["open"], errors="coerce"), "rgba(22,163,74,0.45)", "rgba(220,38,38,0.45)")
    fig.add_trace(go.Bar(x=data["date"], y=data["volume"], name="Volume", marker_color=volume_colors), row=2, col=1)
    if "rsi_14" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["rsi_14"], mode="lines", name="RSI14", line=dict(color="#f59e0b")), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", row=3, col=1)
    if "macd" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["macd"], mode="lines", name="MACD", line=dict(color="#2563eb")), row=4, col=1)
    if "macd_signal" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["macd_signal"], mode="lines", name="MACD Signal", line=dict(color="#f97316")), row=4, col=1)
    if "macd_hist" in data.columns:
        fig.add_trace(go.Bar(x=data["date"], y=data["macd_hist"], name="MACD Hist", marker_color="#64748b"), row=4, col=1)

    if order_recommendations is not None and not order_recommendations.empty:
        rec = order_recommendations[order_recommendations["ticker"].astype(str).str.upper() == str(ticker).upper()].head(1)
        if not rec.empty:
            row = rec.iloc[0]
            x0, x1 = data["date"].iloc[0], data["date"].iloc[-1]
            for low_col, high_col, label, color in [("buy_low", "buy_high", "Strategy Buy Zone", "rgba(22,163,74,0.16)"), ("sell_low", "sell_high", "Strategy Sell Zone", "rgba(220,38,38,0.14)")]:
                y0 = _as_float(row.get(low_col), np.nan)
                y1 = _as_float(row.get(high_col), np.nan)
                if np.isfinite(y0) and np.isfinite(y1):
                    fig.add_shape(type="rect", xref="x", yref="y", x0=x0, x1=x1, y0=min(y0, y1), y1=max(y0, y1), fillcolor=color, line=dict(width=0), layer="below", row=1, col=1)
                    fig.add_trace(go.Scatter(x=[x1], y=[(y0 + y1) / 2], mode="markers+text", name=label, text=[label], marker=dict(size=8, color=color.replace("0.16", "0.85").replace("0.14", "0.85"))), row=1, col=1)
            for price_col, label, color in [("stop_loss", "Strategy Stop", "#dc2626"), ("take_profit", "Strategy Take Profit", "#16a34a")]:
                y = _as_float(row.get(price_col), np.nan)
                if np.isfinite(y):
                    fig.add_hline(y=y, line_dash="dash", line_color=color, annotation_text=label, row=1, col=1)

    if not markers.empty:
        buys = markers[markers["side"] == "BUY"]
        sells = markers[markers["side"] == "SELL"]
        covers = markers[markers["side"] == "BUY_TO_COVER"]
        fig.add_trace(go.Scatter(x=buys["date"], y=buys["price"], mode="markers", name="Strategy Buy Entry", marker=dict(symbol="triangle-up", size=12, color="#16a34a", line=dict(color="#052e16", width=1)), customdata=buys[["strategy", "return_pct"]], hovertemplate="%{x}<br>%{customdata[0]} buy entry<br>price=%{y:.2f}<br>trade ret=%{customdata[1]:.2%}<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=sells["date"], y=sells["price"], mode="markers", name="Strategy Sell / Short Entry", marker=dict(symbol="triangle-down", size=12, color="#dc2626", line=dict(color="#450a0a", width=1)), customdata=sells[["strategy", "return_pct"]], hovertemplate="%{x}<br>%{customdata[0]} sell / short entry<br>price=%{y:.2f}<br>trade ret=%{customdata[1]:.2%}<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=covers["date"], y=covers["price"], mode="markers", name="Strategy Buy-to-Cover Exit", marker=dict(symbol="circle", size=9, color="#22c55e", line=dict(color="#052e16", width=1)), customdata=covers[["strategy", "return_pct"]], hovertemplate="%{x}<br>%{customdata[0]} buy-to-cover exit<br>price=%{y:.2f}<br>trade ret=%{customdata[1]:.2%}<extra></extra>"), row=1, col=1)
        _add_trade_lifecycle_annotations(fig, selected_trades, data)

    if show_smc:
        smc_context = build_smc_context(data)
        # Keep legend entries visible even when the current sample has no SMC objects.
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", name="SMC Liquidity", marker=dict(color="#0ea5e9", size=8)), row=1, col=1)
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", name="SMC Order Block", marker=dict(color="#a855f7", size=8)), row=1, col=1)
        liquidity = smc_context.get("liquidity", pd.DataFrame())
        if isinstance(liquidity, pd.DataFrame) and not liquidity.empty:
            for _, row in liquidity.tail(8).iterrows():
                y = _as_float(row.get("level", row.get("price")), np.nan)
                if np.isfinite(y):
                    fig.add_hline(y=y, line_dash="dot", line_color="#0ea5e9", annotation_text="SMC Liquidity", row=1, col=1)
            fig.add_trace(go.Scatter(x=[data["date"].iloc[-1]], y=[data["close"].iloc[-1]], mode="markers", name="SMC Liquidity", marker=dict(color="#0ea5e9", size=1)), row=1, col=1)
        order_blocks = smc_context.get("order_blocks", pd.DataFrame())
        if isinstance(order_blocks, pd.DataFrame) and not order_blocks.empty:
            for _, row in order_blocks.tail(6).iterrows():
                y0 = _as_float(row.get("bottom", row.get("low", row.get("y0"))), np.nan)
                y1 = _as_float(row.get("top", row.get("high", row.get("y1"))), np.nan)
                if np.isfinite(y0) and np.isfinite(y1):
                    fig.add_shape(type="rect", xref="x", yref="y", x0=data["date"].iloc[max(0, len(data) - 80)], x1=data["date"].iloc[-1], y0=min(y0, y1), y1=max(y0, y1), fillcolor="rgba(168,85,247,0.12)", line=dict(color="rgba(168,85,247,0.45)", width=1), layer="below", row=1, col=1)
            fig.add_trace(go.Scatter(x=[data["date"].iloc[-1]], y=[data["close"].iloc[-1]], mode="markers", name="SMC Order Block", marker=dict(color="#a855f7", size=1)), row=1, col=1)

    if not equity.empty:
        for strategy, group in equity.groupby("strategy"):
            fig.add_trace(go.Scatter(x=group["date"], y=group["equity"], mode="lines", name=f"Equity Curve {strategy}" if strategy != "COMPOSITE" else "Equity Curve", line=dict(width=2)), row=5, col=1, secondary_y=False)
    else:
        fig.add_trace(go.Scatter(x=[], y=[], mode="lines", name="Equity Curve"), row=5, col=1, secondary_y=False)
    if not drawdown.empty:
        comp = drawdown[drawdown["strategy"].astype(str) == "COMPOSITE"] if "COMPOSITE" in set(drawdown["strategy"].astype(str)) else drawdown
        fig.add_trace(go.Scatter(x=comp["date"], y=comp["drawdown_pct"], mode="lines", fill="tozeroy", name="Drawdown", line=dict(color="#dc2626")), row=5, col=1, secondary_y=True)
    else:
        fig.add_trace(go.Scatter(x=[], y=[], mode="lines", name="Drawdown"), row=5, col=1, secondary_y=True)
    fig.update_layout(
        height=950,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=30, r=30, t=80, b=30),
    )
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot")
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)
    fig.update_yaxes(title_text="MACD", row=4, col=1)
    fig.update_yaxes(title_text="Equity", row=5, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Drawdown %", row=5, col=1, secondary_y=True)
    return {
        "figure": fig,
        "equity_curve": equity,
        "drawdown_curve": drawdown,
        "trade_markers": markers,
        "strategy_metrics": metrics,
    }
