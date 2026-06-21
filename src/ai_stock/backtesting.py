from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .analytics import add_indicators
from .data_sources import normalize_ohlcv


@dataclass(frozen=True)
class BacktestResult:
    summary: pd.DataFrame
    trades: pd.DataFrame
    equity_curve: pd.DataFrame


def _empty_result() -> BacktestResult:
    return BacktestResult(summary=pd.DataFrame(), trades=pd.DataFrame(), equity_curve=pd.DataFrame())


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return np.nan
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    return float(drawdown.min())


def _build_summary(ticker: str, trades: pd.DataFrame, equity_curve: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "ticker": ticker,
            "trades": 0,
            "win_rate": np.nan,
            "stop_loss_hit_rate": np.nan,
            "time_exit_rate": np.nan,
            "trailing_stop_hit_rate": np.nan,
            "cumulative_return": 0.0,
            "max_drawdown": 0.0,
            "avg_trade_return": np.nan,
            "profit_factor": np.nan,
        }

    wins = trades["return_pct"] > 0
    gains = trades.loc[trades["return_pct"] > 0, "return_pct"].sum()
    losses = abs(trades.loc[trades["return_pct"] < 0, "return_pct"].sum())
    profit_factor = float(gains / losses) if losses > 0 else np.inf
    exit_reason = trades.get("exit_reason", pd.Series(index=trades.index, dtype=object))
    return {
        "ticker": ticker,
        "trades": int(len(trades)),
        "win_rate": float(wins.mean()),
        "stop_loss_hit_rate": float(trades["stop_hit"].mean()),
        "time_exit_rate": float(exit_reason.eq("time").mean()) if not exit_reason.empty else np.nan,
        "trailing_stop_hit_rate": float(exit_reason.eq("trailing_stop").mean()) if not exit_reason.empty else np.nan,
        "cumulative_return": float(equity_curve["cumulative_return"].iloc[-1]) if not equity_curve.empty else 0.0,
        "max_drawdown": _max_drawdown(equity_curve["equity"]) if not equity_curve.empty else 0.0,
        "avg_trade_return": float(trades["return_pct"].mean()),
        "profit_factor": profit_factor,
    }


def _fast_walk_forward_signal(history: pd.DataFrame, horizon: int) -> dict:
    enriched = add_indicators(history).dropna(subset=["close"])
    latest = enriched.iloc[-1]
    last_close = float(latest["close"])
    return_5d = float(latest.get("return_5d", 0.0)) if np.isfinite(float(latest.get("return_5d", np.nan))) else 0.0
    return_20d = float(latest.get("return_20d", 0.0)) if np.isfinite(float(latest.get("return_20d", np.nan))) else 0.0
    expected_return = return_20d * min(horizon / 20.0, 1.0) * 0.6 + return_5d * min(horizon / 5.0, 1.0) * 0.4
    vol = float(enriched["return_1d"].tail(60).std() * np.sqrt(horizon))
    atr_pct = float(latest.get("atr_pct_14", np.nan))
    risk_unit = max(v for v in [vol, atr_pct, 0.01] if np.isfinite(v))
    max_drawdown_60d = float(latest.get("max_drawdown_60d", np.nan))
    drawdown_penalty = abs(max_drawdown_60d) * 0.25 if np.isfinite(max_drawdown_60d) else 0.0
    threshold = max(risk_unit + drawdown_penalty, 0.01)
    if expected_return > threshold:
        action = "BUY_WATCH"
    elif expected_return < -threshold:
        action = "SELL_OR_AVOID"
    else:
        action = "HOLD_WAIT"
    support = float(latest.get("support_20", enriched["low"].tail(20).min()))
    stop_loss = min(last_close * (1 - max(risk_unit * 1.5, 0.03)), support * 0.98)
    return {
        "action": action,
        "expected_return_pct": expected_return * 100,
        "relationship_adjusted_return_pct": expected_return * 100,
        "stop_loss_price": float(stop_loss),
        "kelly_fraction": float(np.clip(max(expected_return, 0) / max(risk_unit, 0.01) * 0.1, 0.0, 1.0)),
    }


def _choose_exit(
    future: pd.DataFrame,
    entry_price: float,
    stop_loss: float,
    exit_rule: str,
    trailing_stop_pct: float = 0.05,
) -> tuple[pd.Series, float, bool, str]:
    if future.empty:
        raise ValueError("future window is empty")

    if exit_rule == "time":
        exit_row = future.iloc[-1]
        return exit_row, float(exit_row["close"]), False, "time"

    if exit_rule == "stop_loss":
        stop_hits = future[future["low"] <= stop_loss] if np.isfinite(stop_loss) else pd.DataFrame()
        if not stop_hits.empty:
            exit_row = stop_hits.iloc[0]
            return exit_row, float(stop_loss), True, "stop_loss"
        exit_row = future.iloc[-1]
        return exit_row, float(exit_row["close"]), False, "time"

    if exit_rule == "trailing_stop":
        peak = entry_price
        fallback_stop = stop_loss if np.isfinite(stop_loss) else entry_price * (1 - trailing_stop_pct)
        for _, row in future.iterrows():
            peak = max(peak, float(row["high"]))
            trailing_stop = max(fallback_stop, peak * (1 - trailing_stop_pct))
            if float(row["low"]) <= trailing_stop:
                return row, float(trailing_stop), True, "trailing_stop"
        exit_row = future.iloc[-1]
        return exit_row, float(exit_row["close"]), False, "time"

    raise ValueError(f"Unsupported exit_rule: {exit_rule}")


def run_backtest(
    prices: pd.DataFrame,
    horizon: int = 5,
    lookback: int = 120,
    step: int | None = None,
    only_buy_watch: bool = False,
    exit_rule: str = "stop_loss",
    trailing_stop_pct: float = 0.05,
) -> BacktestResult:
    """Walk-forward long-only decision-report backtest.

    At every ``step`` bars after ``lookback``, build the same decision report the UI
    uses from historical data only. When the report says BUY_WATCH, enter at that
    bar's close, exit at ``horizon`` bars later, or earlier if the forward low hits
    the report's stop-loss level.
    """
    if prices.empty:
        return _empty_result()

    normalized = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    normalized = normalized.sort_values(["ticker", "date"]).reset_index(drop=True)
    step = step or max(1, horizon)
    all_summaries: list[dict] = []
    all_trades: list[dict] = []
    all_equity: list[pd.DataFrame] = []

    for ticker, group in normalized.groupby("ticker"):
        group = group.sort_values("date").reset_index(drop=True)
        trades: list[dict] = []
        equity_rows: list[dict] = []
        equity = 1.0
        min_required = max(lookback, 60, horizon + 10)
        if len(group) <= min_required + horizon:
            all_summaries.append(_build_summary(str(ticker), pd.DataFrame(), pd.DataFrame()))
            continue

        for entry_idx in range(min_required, len(group) - horizon, step):
            history = group.iloc[: entry_idx + 1].copy()
            signal_row = _fast_walk_forward_signal(history, horizon=horizon)
            action = str(signal_row.get("action", ""))
            if only_buy_watch and action != "BUY_WATCH":
                continue

            entry = group.iloc[entry_idx]
            future = group.iloc[entry_idx + 1 : entry_idx + horizon + 1]
            if future.empty:
                continue
            stop_loss = float(signal_row.get("stop_loss_price", np.nan))
            entry_price = float(entry["close"])
            exit_row, exit_price, stop_hit, exit_reason = _choose_exit(
                future,
                entry_price=entry_price,
                stop_loss=stop_loss,
                exit_rule=exit_rule,
                trailing_stop_pct=trailing_stop_pct,
            )

            trade_return = exit_price / entry_price - 1.0
            equity *= 1.0 + trade_return
            trade = {
                "ticker": str(ticker),
                "entry_date": entry["date"],
                "exit_date": exit_row["date"],
                "entry_price": entry_price,
                "exit_price": float(exit_price),
                "return_pct": float(trade_return),
                "stop_hit": bool(stop_hit),
                "exit_rule": exit_rule,
                "exit_reason": exit_reason,
                "holding_days": horizon,
                "action": action,
                "expected_return_pct": float(signal_row.get("expected_return_pct", np.nan)),
                "relationship_adjusted_return_pct": float(signal_row.get("relationship_adjusted_return_pct", np.nan)),
                "kelly_fraction": float(signal_row.get("kelly_fraction", np.nan)),
            }
            trades.append(trade)
            equity_rows.append(
                {
                    "ticker": str(ticker),
                    "date": exit_row["date"],
                    "equity": float(equity),
                    "cumulative_return": float(equity - 1.0),
                    "last_trade_return": float(trade_return),
                }
            )

        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_rows)
        all_summaries.append(_build_summary(str(ticker), trades_df, equity_df))
        if not trades_df.empty:
            all_trades.append(trades_df)
        if not equity_df.empty:
            all_equity.append(equity_df)

    summary_df = pd.DataFrame(all_summaries)
    if not summary_df.empty:
        summary_df["holding_days"] = horizon
        summary_df["exit_rule"] = exit_rule
        summary_df["strategy"] = f"持有 {horizon} 天 / {_exit_rule_label(exit_rule)}"
        summary_df = summary_df.sort_values("cumulative_return", ascending=False).reset_index(drop=True)
    return BacktestResult(
        summary=summary_df,
        trades=pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame(),
        equity_curve=pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame(),
    )


def _exit_rule_label(exit_rule: str) -> str:
    return {
        "time": "時間出場",
        "stop_loss": "停損優先",
        "trailing_stop": "移動停損",
    }.get(exit_rule, exit_rule)


def compare_backtest_scenarios(
    prices: pd.DataFrame,
    horizons: list[int] | tuple[int, ...] = (3, 5, 10),
    exit_rules: list[str] | tuple[str, ...] = ("time", "stop_loss", "trailing_stop"),
    lookback: int = 120,
    only_buy_watch: bool = False,
    trailing_stop_pct: float = 0.05,
) -> pd.DataFrame:
    """Run a grid of holding periods and exit rules, returning one comparable table."""
    rows: list[pd.DataFrame] = []
    for horizon in horizons:
        for exit_rule in exit_rules:
            result = run_backtest(
                prices,
                horizon=int(horizon),
                lookback=lookback,
                step=int(horizon),
                only_buy_watch=only_buy_watch,
                exit_rule=exit_rule,
                trailing_stop_pct=trailing_stop_pct,
            )
            if not result.summary.empty:
                rows.append(result.summary)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(["cumulative_return", "win_rate"], ascending=[False, False]).reset_index(drop=True)
