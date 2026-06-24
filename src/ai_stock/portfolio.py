from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PORTFOLIO_PATHS = ("my_stocks.json", "my_sotcks.json")


@dataclass(frozen=True)
class PortfolioLoadResult:
    holdings: pd.DataFrame
    source_path: str | None
    account_label: str | None
    note: str | None = None


def find_portfolio_file(root: str | Path = ".") -> Path | None:
    base = Path(root)
    # The Docker app uses AI_STOCK_PORTFOLIO_FILE to point at the mounted
    # private runtime copy.  Explicit roots passed by tests or callers should
    # remain isolated and must not be overridden by the process environment.
    if str(base) in {".", ""}:
        env_path = os.environ.get("AI_STOCK_PORTFOLIO_FILE")
        if env_path:
            candidate = Path(env_path).expanduser()
            if candidate.exists() and candidate.is_file():
                return candidate
    for name in DEFAULT_PORTFOLIO_PATHS:
        candidate = base / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _clean_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def load_portfolio_json(path: str | Path) -> PortfolioLoadResult:
    """Load a local broker/account holdings JSON into a canonical DataFrame.

    The JSON is intentionally treated as private local input. It should not be
    committed to Git; the app only reads it when present.
    """
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    holdings = payload.get("holdings", [])
    rows: list[dict[str, Any]] = []
    for row in holdings:
        ticker = _clean_ticker(row.get("ticker"))
        if not ticker:
            continue
        quantity = pd.to_numeric(row.get("quantity"), errors="coerce")
        current_price = pd.to_numeric(row.get("current_price"), errors="coerce")
        cost_price = pd.to_numeric(row.get("cost_price"), errors="coerce")
        market_value = pd.to_numeric(row.get("market_value"), errors="coerce")
        if pd.isna(market_value) and pd.notna(quantity) and pd.notna(current_price):
            market_value = float(quantity) * float(current_price)
        rows.append(
            {
                "ticker": ticker,
                "name_zh": str(row.get("name_zh", "") or ""),
                "quantity": float(quantity) if pd.notna(quantity) else np.nan,
                "broker_current_price": float(current_price) if pd.notna(current_price) else np.nan,
                "cost_price": float(cost_price) if pd.notna(cost_price) else np.nan,
                "market_value": float(market_value) if pd.notna(market_value) else np.nan,
                "today_pnl": float(pd.to_numeric(row.get("today_pnl"), errors="coerce")) if pd.notna(pd.to_numeric(row.get("today_pnl"), errors="coerce")) else np.nan,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["ticker"], keep="last").sort_values("market_value", ascending=False, na_position="last").reset_index(drop=True)
    source_meta = payload.get("source", {}) if isinstance(payload.get("source", {}), dict) else {}
    return PortfolioLoadResult(
        holdings=df,
        source_path=str(source),
        account_label=source_meta.get("account"),
        note=source_meta.get("note"),
    )


def load_local_portfolio(root: str | Path = ".") -> PortfolioLoadResult:
    path = find_portfolio_file(root)
    if path is None:
        return PortfolioLoadResult(pd.DataFrame(), None, None, None)
    return load_portfolio_json(path)


def portfolio_tickers(holdings: pd.DataFrame) -> tuple[str, ...]:
    if holdings.empty or "ticker" not in holdings.columns:
        return tuple()
    return tuple(str(t).strip().upper() for t in holdings["ticker"].dropna().unique() if str(t).strip())


def build_portfolio_order_plan(holdings: pd.DataFrame, decision_report: pd.DataFrame) -> pd.DataFrame:
    """Merge holdings with the decision report and create stop/take-profit order guidance.

    This does not place orders. It produces a human-readable trade plan for the UI:
    stop-loss price, take-profit price, whether to hold/reduce/add, and why.
    """
    if holdings.empty:
        return pd.DataFrame()
    out = holdings.copy()
    if not decision_report.empty:
        decision_cols = [
            "ticker",
            "action",
            "last_close",
            "relationship_adjusted_return_pct",
            "expected_return_pct",
            "kelly_fraction",
            "suggested_buy_price",
            "suggested_sell_price",
            "stop_loss_price",
            "action_reason",
            "kelly_reason",
            "risk_unit_pct",
            "max_drawdown_60d_pct",
        ]
        out = out.merge(decision_report[[c for c in decision_cols if c in decision_report.columns]], on="ticker", how="left")
    else:
        out["action"] = np.nan

    total_value = pd.to_numeric(out.get("market_value"), errors="coerce").sum()
    out["portfolio_weight_pct"] = np.where(total_value > 0, pd.to_numeric(out.get("market_value"), errors="coerce") / total_value * 100, np.nan)
    out["unrealized_pnl"] = (pd.to_numeric(out.get("broker_current_price"), errors="coerce") - pd.to_numeric(out.get("cost_price"), errors="coerce")) * pd.to_numeric(out.get("quantity"), errors="coerce")
    out["unrealized_pnl_pct"] = (pd.to_numeric(out.get("broker_current_price"), errors="coerce") / pd.to_numeric(out.get("cost_price"), errors="coerce") - 1) * 100
    out["today_pnl_pct_of_value"] = pd.to_numeric(out.get("today_pnl"), errors="coerce") / pd.to_numeric(out.get("market_value"), errors="coerce") * 100
    out["price_gap_pct"] = (pd.to_numeric(out.get("last_close"), errors="coerce") / pd.to_numeric(out.get("broker_current_price"), errors="coerce") - 1) * 100
    out["kelly_pct"] = pd.to_numeric(out.get("kelly_fraction"), errors="coerce") * 100

    def decide(row: pd.Series) -> tuple[str, str]:
        action = str(row.get("action", "") or "")
        broker_price = float(row.get("broker_current_price")) if pd.notna(row.get("broker_current_price")) else np.nan
        stop = float(row.get("stop_loss_price")) if pd.notna(row.get("stop_loss_price")) else np.nan
        take = float(row.get("suggested_sell_price")) if pd.notna(row.get("suggested_sell_price")) else np.nan
        buy = float(row.get("suggested_buy_price")) if pd.notna(row.get("suggested_buy_price")) else np.nan
        kelly = float(row.get("kelly_pct")) if pd.notna(row.get("kelly_pct")) else 0.0
        pnl_pct = float(row.get("unrealized_pnl_pct")) if pd.notna(row.get("unrealized_pnl_pct")) else np.nan

        if action == "SELL_OR_AVOID":
            return "REDUCE_OR_EXIT", "模型偏弱；已有持倉時優先檢查是否減碼，停損單不可放寬。"
        if np.isfinite(broker_price) and np.isfinite(stop) and broker_price <= stop:
            return "STOP_LOSS_ALERT", "現價已接近或跌破停損參考，應優先處理風險。"
        if np.isfinite(broker_price) and np.isfinite(take) and broker_price >= take:
            return "TAKE_PROFIT_ALERT", "現價已達或超過停利參考，可評估分批停利。"
        if action == "BUY_WATCH" and kelly > 0:
            if np.isfinite(broker_price) and np.isfinite(buy) and broker_price <= buy * 1.02:
                return "ADD_OR_HOLD", "偏多且接近買進參考；若要加碼，仍以限價與既有風險上限為準。"
            return "WAIT_FOR_BUY_PRICE", "偏多但未到理想買價；等待回落或量價確認。"
        if action == "HOLD_WAIT":
            if np.isfinite(pnl_pct) and pnl_pct < -8:
                return "HOLD_WITH_TIGHT_STOP", "目前仍等待確認且持倉虧損，建議用停損價管理，不宜盲目加碼攤平。"
            return "HOLD_WITH_STOP", "訊號尚未明確；已有持倉以持有與停損/停利計畫管理。"
        return "REVIEW_MANUALLY", "缺少足夠決策資料，先人工檢查行情代號與資料來源。"

    decisions = out.apply(decide, axis=1, result_type="expand")
    out["suggested_order_action"] = decisions[0]
    out["order_note"] = decisions[1]
    out["stop_loss_order_price"] = pd.to_numeric(out.get("stop_loss_price"), errors="coerce")
    out["take_profit_order_price"] = pd.to_numeric(out.get("suggested_sell_price"), errors="coerce")
    out["add_buy_limit_price"] = pd.to_numeric(out.get("suggested_buy_price"), errors="coerce")

    columns = [
        "ticker",
        "name_zh",
        "quantity",
        "market_value",
        "portfolio_weight_pct",
        "broker_current_price",
        "last_close",
        "price_gap_pct",
        "cost_price",
        "unrealized_pnl",
        "unrealized_pnl_pct",
        "today_pnl",
        "today_pnl_pct_of_value",
        "action",
        "suggested_order_action",
        "kelly_pct",
        "add_buy_limit_price",
        "stop_loss_order_price",
        "take_profit_order_price",
        "relationship_adjusted_return_pct",
        "risk_unit_pct",
        "max_drawdown_60d_pct",
        "order_note",
        "action_reason",
        "kelly_reason",
    ]
    return out[[c for c in columns if c in out.columns]].sort_values("market_value", ascending=False, na_position="last").reset_index(drop=True)


def summarize_portfolio(holdings: pd.DataFrame, order_plan: pd.DataFrame | None = None) -> dict[str, float | int | str | None]:
    if holdings.empty:
        return {"positions": 0, "total_market_value": 0.0, "total_today_pnl": 0.0, "largest_ticker": None, "largest_weight_pct": np.nan}
    total_market_value = float(pd.to_numeric(holdings.get("market_value"), errors="coerce").sum())
    total_today_pnl = float(pd.to_numeric(holdings.get("today_pnl"), errors="coerce").sum())
    largest = holdings.sort_values("market_value", ascending=False).head(1)
    largest_ticker = str(largest["ticker"].iloc[0]) if not largest.empty else None
    largest_weight = float(largest["market_value"].iloc[0] / total_market_value * 100) if not largest.empty and total_market_value > 0 else np.nan
    stop_alerts = 0
    take_profit_alerts = 0
    reduce_alerts = 0
    if order_plan is not None and not order_plan.empty:
        stop_alerts = int((order_plan["suggested_order_action"] == "STOP_LOSS_ALERT").sum())
        take_profit_alerts = int((order_plan["suggested_order_action"] == "TAKE_PROFIT_ALERT").sum())
        reduce_alerts = int((order_plan["suggested_order_action"] == "REDUCE_OR_EXIT").sum())
    return {
        "positions": int(len(holdings)),
        "total_market_value": total_market_value,
        "total_today_pnl": total_today_pnl,
        "largest_ticker": largest_ticker,
        "largest_weight_pct": largest_weight,
        "stop_alerts": stop_alerts,
        "take_profit_alerts": take_profit_alerts,
        "reduce_alerts": reduce_alerts,
    }
