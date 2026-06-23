from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analytics import add_indicators
from .backtesting import run_backtest
from .data_sources import normalize_ohlcv

ACTION_TONE = {
    "BUY_WATCH": "bullish",
    "HOLD_WAIT": "neutral",
    "SELL_OR_AVOID": "bearish",
}


def build_opportunity_radar(decision_report: pd.DataFrame, backtest_summary: pd.DataFrame | None = None, top_n: int = 6) -> pd.DataFrame:
    """Create beginner-friendly opportunity cards from decision and backtest tables."""
    if decision_report.empty:
        return pd.DataFrame()
    out = decision_report.copy()
    if backtest_summary is not None and not backtest_summary.empty:
        bt_cols = ["ticker", "win_rate", "cumulative_return", "max_drawdown", "profit_factor", "trades"]
        bt = backtest_summary[[c for c in bt_cols if c in backtest_summary.columns]].copy()
        out = out.merge(bt, on="ticker", how="left")
    out["tone"] = out.get("action", pd.Series(index=out.index, dtype=object)).map(ACTION_TONE).fillna("neutral")
    out["adjusted_return_pct"] = out.get("relationship_adjusted_return_pct", out.get("expected_return_pct", np.nan))
    out["kelly_pct"] = out.get("kelly_fraction", 0).fillna(0) * 100
    out["win_rate_pct"] = out.get("win_rate", np.nan) * 100 if "win_rate" in out.columns else np.nan
    out["backtest_return_pct"] = out.get("cumulative_return", np.nan) * 100 if "cumulative_return" in out.columns else np.nan
    out["max_drawdown_pct"] = out.get("max_drawdown", np.nan) * 100 if "max_drawdown" in out.columns else np.nan
    out["reason"] = out.get("action_reason", "").fillna("").astype(str)
    priority = {"bullish": 0, "neutral": 1, "bearish": 2}
    out["_tone_rank"] = out["tone"].map(priority).fillna(3)
    out = out.sort_values(["_tone_rank", "adjusted_return_pct"], ascending=[True, False]).head(top_n)
    columns = [
        "ticker",
        "action",
        "tone",
        "adjusted_return_pct",
        "expected_return_pct",
        "kelly_pct",
        "win_rate_pct",
        "backtest_return_pct",
        "max_drawdown_pct",
        "profit_factor",
        "trades",
        "suggested_buy_price",
        "suggested_sell_price",
        "stop_loss_price",
        "reason",
    ]
    return out[[c for c in columns if c in out.columns]].reset_index(drop=True)


def build_strategy_health_cards(backtest_summary: pd.DataFrame, decision_report: pd.DataFrame | None = None) -> pd.DataFrame:
    """Turn backtest metrics into natural-language strategy diagnostics."""
    if backtest_summary.empty:
        return pd.DataFrame(
            [{"ticker": "ALL", "severity": "warning", "title": "資料不足", "message": "目前沒有足夠回測資料，請拉長歷史區間或降低回測訓練視窗。"}]
        )
    decision = pd.DataFrame() if decision_report is None else decision_report.copy()
    rows: list[dict] = []
    for _, row in backtest_summary.iterrows():
        ticker = str(row.get("ticker", ""))
        trades = int(row.get("trades", 0) or 0)
        win_rate = float(row.get("win_rate", np.nan))
        max_drawdown = float(row.get("max_drawdown", np.nan))
        profit_factor = float(row.get("profit_factor", np.nan))
        cumulative_return = float(row.get("cumulative_return", np.nan))
        decision_row = decision[decision["ticker"] == ticker].head(1) if not decision.empty and "ticker" in decision.columns else pd.DataFrame()
        action = str(decision_row["action"].iloc[0]) if not decision_row.empty and "action" in decision_row else ""
        kelly = float(decision_row["kelly_fraction"].iloc[0]) if not decision_row.empty and "kelly_fraction" in decision_row else np.nan

        if trades < 10:
            rows.append({"ticker": ticker, "severity": "warning", "code": "low_sample", "title": "樣本數不足", "message": f"樣本數不足：{ticker} 目前只有 {trades} 筆回測交易，勝率與報酬只能當方向參考。", "trades": trades})
        if np.isfinite(max_drawdown) and max_drawdown <= -0.15:
            rows.append({"ticker": ticker, "severity": "danger", "code": "high_drawdown", "title": "最大回撤偏高", "message": f"最大回撤偏高：{ticker} 最大回撤 {max_drawdown * 100:.1f}%，需要降低倉位、提高停損或改用更保守出場規則。", "max_drawdown_pct": max_drawdown * 100})
        if np.isfinite(profit_factor) and profit_factor < 1:
            rows.append({"ticker": ticker, "severity": "danger", "code": "low_profit_factor", "title": "Profit Factor 低於 1", "message": f"Profit Factor 低於 1：{ticker} 獲利交易不足以覆蓋虧損交易，暫不適合只靠此策略進場。", "profit_factor": profit_factor})
        if np.isfinite(win_rate) and win_rate < 0.45:
            rows.append({"ticker": ticker, "severity": "warning", "code": "low_win_rate", "title": "勝率偏低", "message": f"{ticker} 回測勝率 {win_rate * 100:.1f}%，需搭配更強確認訊號。", "win_rate_pct": win_rate * 100})
        if np.isfinite(cumulative_return) and cumulative_return < 0:
            rows.append({"ticker": ticker, "severity": "warning", "code": "negative_return", "title": "累積報酬為負", "message": f"{ticker} 在目前參數下累積報酬為 {cumulative_return * 100:.1f}%，代表策略方向暫時不佳。", "cumulative_return_pct": cumulative_return * 100})
        if np.isfinite(kelly) and kelly <= 0 and action == "HOLD_WAIT":
            rows.append({"ticker": ticker, "severity": "info", "code": "hold_zero_kelly", "title": "等待確認", "message": f"{ticker} Kelly 為 0 且決策為等待確認，代表模型優勢尚未大過近期風險。"})

    if not rows:
        rows.append({"ticker": "ALL", "severity": "ok", "code": "health_ok", "title": "策略健檢通過", "message": "目前回測沒有明顯樣本不足、回撤過高或 Profit Factor 過低警訊。"})
    severity_rank = {"danger": 0, "warning": 1, "info": 2, "ok": 3}
    return pd.DataFrame(rows).sort_values("severity", key=lambda s: s.map(severity_rank).fillna(9)).reset_index(drop=True)


def _add_horizontal_line(fig: go.Figure, x_values: pd.Series, y: float, name: str, color: str, dash: str = "dash") -> None:
    if not np.isfinite(y) or x_values.empty:
        return
    fig.add_trace(
        go.Scatter(
            x=[x_values.min(), x_values.max()],
            y=[y, y],
            mode="lines",
            name=name,
            line={"color": color, "dash": dash, "width": 2},
            hovertemplate=f"{name}: %{{y:.2f}}<extra></extra>",
        )
    )


def build_decision_price_chart(
    one: pd.DataFrame,
    ticker: str,
    show_volume: bool,
    decision_row: pd.Series | dict | None = None,
    backtest_trades: pd.DataFrame | None = None,
) -> go.Figure:
    """Build K-line chart with SMA, decision levels, and B/S backtest markers."""
    one = one.sort_values("date").copy()
    ind = add_indicators(one)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=one["date"],
            open=one["open"],
            high=one["high"],
            low=one["low"],
            close=one["close"],
            name=ticker,
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
        )
    )
    fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_20"], name="SMA20", line={"color": "#2563eb"}))
    fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_60"], name="SMA60", line={"color": "#f97316"}))
    if decision_row is not None:
        row = pd.Series(decision_row)
        _add_horizontal_line(fig, one["date"], float(row.get("suggested_buy_price", np.nan)), "參考買進", "#16a34a")
        _add_horizontal_line(fig, one["date"], float(row.get("suggested_sell_price", np.nan)), "參考賣出", "#2563eb")
        _add_horizontal_line(fig, one["date"], float(row.get("stop_loss_price", np.nan)), "參考停損", "#dc2626")
    if backtest_trades is not None and not backtest_trades.empty:
        trades = backtest_trades[backtest_trades["ticker"].astype(str) == str(ticker)].copy() if "ticker" in backtest_trades.columns else backtest_trades.copy()
        if not trades.empty:
            fig.add_trace(
                go.Scatter(
                    x=trades["entry_date"],
                    y=trades["entry_price"],
                    mode="markers+text",
                    name="回測進場 B",
                    text=["B"] * len(trades),
                    textposition="top center",
                    marker={"symbol": "triangle-up", "size": 12, "color": "#16a34a", "line": {"color": "white", "width": 1}},
                    hovertemplate="B %{x}<br>進場=%{y:.2f}<extra></extra>",
                )
            )
            colors = ["#16a34a" if float(v) >= 0 else "#dc2626" for v in trades.get("return_pct", pd.Series([0] * len(trades)))]
            fig.add_trace(
                go.Scatter(
                    x=trades["exit_date"],
                    y=trades["exit_price"],
                    mode="markers+text",
                    name="回測出場 S",
                    text=["S"] * len(trades),
                    textposition="bottom center",
                    marker={"symbol": "triangle-down", "size": 12, "color": colors, "line": {"color": "white", "width": 1}},
                    hovertemplate="S %{x}<br>出場=%{y:.2f}<extra></extra>",
                )
            )
    if show_volume:
        fig.add_trace(
            go.Bar(
                x=one["date"],
                y=one["volume"],
                name="成交量",
                marker_color="rgba(100,116,139,0.25)",
                yaxis="y2",
            )
        )
        fig.update_layout(yaxis2={"overlaying": "y", "side": "right", "showgrid": False, "title": "Volume"})
    fig.update_layout(
        height=560,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def build_watchlist_sparklines(prices: pd.DataFrame, decision_report: pd.DataFrame | None = None, lookback: int = 30) -> pd.DataFrame:
    """Build a compact watchlist table with recent close series for mini sparklines."""
    if prices.empty:
        return pd.DataFrame()
    normalized = normalize_ohlcv(prices) if set(["開盤", "收盤"]) & set(prices.columns) else prices.copy()
    normalized = normalized.sort_values(["ticker", "date"]).reset_index(drop=True)
    decision = pd.DataFrame() if decision_report is None else decision_report.copy()
    rows: list[dict] = []
    for ticker, group in normalized.groupby("ticker"):
        group = group.sort_values("date")
        closes = group["close"].astype(float)
        if closes.empty:
            continue
        last_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else np.nan
        close_5 = float(closes.iloc[-6]) if len(closes) >= 6 else np.nan
        latest_volume = float(group["volume"].iloc[-1]) if "volume" in group else np.nan
        avg_volume = float(group["volume"].tail(20).mean()) if "volume" in group else np.nan
        decision_row = decision[decision["ticker"].astype(str) == str(ticker)].head(1) if not decision.empty and "ticker" in decision.columns else pd.DataFrame()
        action = str(decision_row["action"].iloc[0]) if not decision_row.empty and "action" in decision_row else ""
        adjusted_return = float(decision_row["relationship_adjusted_return_pct"].iloc[0]) if not decision_row.empty and "relationship_adjusted_return_pct" in decision_row else np.nan
        kelly_pct = float(decision_row["kelly_fraction"].iloc[0]) * 100 if not decision_row.empty and "kelly_fraction" in decision_row else np.nan
        rows.append(
            {
                "ticker": str(ticker),
                "last_close": last_close,
                "change_1d_pct": (last_close / prev_close - 1) * 100 if np.isfinite(prev_close) and prev_close else np.nan,
                "change_5d_pct": (last_close / close_5 - 1) * 100 if np.isfinite(close_5) and close_5 else np.nan,
                "latest_volume": latest_volume,
                "volume_ratio": latest_volume / avg_volume if np.isfinite(latest_volume) and np.isfinite(avg_volume) and avg_volume else np.nan,
                "sparkline": closes.tail(lookback).round(4).tolist(),
                "action": action,
                "tone": ACTION_TONE.get(action, "neutral"),
                "adjusted_return_pct": adjusted_return,
                "kelly_pct": kelly_pct,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    tone_rank = {"bullish": 0, "neutral": 1, "bearish": 2}
    return out.sort_values(["tone", "change_5d_pct"], key=lambda s: s.map(tone_rank).fillna(s) if s.name == "tone" else s, ascending=[True, False]).reset_index(drop=True)


def build_market_heatmap_table(prices: pd.DataFrame, decision_report: pd.DataFrame | None = None) -> pd.DataFrame:
    """Create ticker-level metrics for a market heatmap / treemap."""
    watchlist = build_watchlist_sparklines(prices, decision_report, lookback=20)
    if watchlist.empty:
        return pd.DataFrame()
    action_score = {"BUY_WATCH": 1.0, "HOLD_WAIT": 0.0, "SELL_OR_AVOID": -1.0}
    out = watchlist.copy()
    out["signal_score"] = out["action"].map(action_score).fillna(0.0) + out["adjusted_return_pct"].fillna(0.0) / 10.0 + out["kelly_pct"].fillna(0.0) / 100.0
    out["return_1d_pct"] = out["change_1d_pct"]
    out["return_5d_pct"] = out["change_5d_pct"]
    out["size"] = out["latest_volume"].fillna(0).clip(lower=0) * out["last_close"].fillna(0).clip(lower=0)
    if float(out["size"].sum()) <= 0:
        out["size"] = 1.0
    out["color_value"] = out["return_5d_pct"].fillna(out["signal_score"])
    out["label"] = out["ticker"].astype(str) + "<br>" + out["return_5d_pct"].map(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")
    columns = ["ticker", "label", "tone", "action", "size", "color_value", "return_1d_pct", "return_5d_pct", "signal_score", "last_close", "volume_ratio", "adjusted_return_pct", "kelly_pct"]
    return out[[c for c in columns if c in out.columns]].reset_index(drop=True)


def build_smart_tuning_lite(
    prices: pd.DataFrame,
    horizons: tuple[int, ...] | list[int] = (3, 5, 10),
    exit_rules: tuple[str, ...] | list[str] = ("time", "stop_loss", "trailing_stop"),
    stop_loss_pcts: tuple[float, ...] | list[float] = (0.03, 0.05, 0.08),
    lookback: int = 120,
    only_buy_watch: bool = False,
    trailing_stop_pct: float = 0.05,
) -> pd.DataFrame:
    """Small parameter scan for holding days, exit rules, and risk width.

    ``stop_loss_pct`` is treated as a risk-width scenario label and as the trailing
    width for trailing-stop runs. The underlying stop-loss-first engine still uses
    the walk-forward signal's own support/risk-derived stop level.
    """
    rows: list[pd.DataFrame] = []
    for horizon in horizons:
        for exit_rule in exit_rules:
            for stop_loss_pct in stop_loss_pcts:
                result = run_backtest(
                    prices,
                    horizon=int(horizon),
                    lookback=lookback,
                    step=int(horizon),
                    only_buy_watch=only_buy_watch,
                    exit_rule=str(exit_rule),
                    trailing_stop_pct=float(stop_loss_pct if exit_rule == "trailing_stop" else trailing_stop_pct),
                )
                if result.summary.empty:
                    continue
                summary = result.summary.copy()
                summary["stop_loss_pct"] = float(stop_loss_pct)
                summary["scenario"] = summary["ticker"].astype(str) + f" | {int(horizon)}d | {exit_rule} | risk {float(stop_loss_pct) * 100:.0f}%"
                rows.append(summary)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    safe_pf = out["profit_factor"].replace([np.inf, -np.inf], 5.0).fillna(0).clip(0, 5)
    out["score"] = (
        out["cumulative_return"].fillna(0) * 100
        + out["win_rate"].fillna(0.5) * 25
        + safe_pf * 3
        + out["max_drawdown"].fillna(0) * 60
        - out["stop_loss_hit_rate"].fillna(0) * 5
    )
    out = out.sort_values(["score", "cumulative_return", "win_rate"], ascending=[False, False, False]).reset_index(drop=True)
    out["rank"] = range(1, len(out) + 1)
    columns = [
        "rank",
        "ticker",
        "scenario",
        "holding_days",
        "exit_rule",
        "stop_loss_pct",
        "score",
        "trades",
        "win_rate",
        "stop_loss_hit_rate",
        "cumulative_return",
        "max_drawdown",
        "avg_trade_return",
        "profit_factor",
    ]
    return out[[c for c in columns if c in out.columns]]
