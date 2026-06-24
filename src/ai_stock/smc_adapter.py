from __future__ import annotations

from typing import Any

import importlib
import io
from contextlib import redirect_stdout
import numpy as np
import pandas as pd

from .trade_vision import detect_market_structure

_FVG_COLUMNS = ["zone_id", "date", "end_date", "zone_type", "status", "y0", "y1", "direction", "strength", "label", "source"]
_OB_COLUMNS = ["zone_id", "date", "end_date", "zone_type", "y0", "y1", "direction", "strength", "label", "source"]
_LIQUIDITY_COLUMNS = ["date", "level", "direction", "status", "strength", "label", "source"]
_SWING_COLUMNS = ["date", "price", "type", "strength", "source"]
_EVENT_COLUMNS = ["date", "price", "event_type", "reference_price", "description", "source"]


def _empty_context(engine: str = "fallback", error: str | None = None) -> dict[str, Any]:
    return {
        "engine": engine,
        "error": error,
        "fvg_zones": pd.DataFrame(columns=_FVG_COLUMNS),
        "order_blocks": pd.DataFrame(columns=_OB_COLUMNS),
        "liquidity": pd.DataFrame(columns=_LIQUIDITY_COLUMNS),
        "swings": pd.DataFrame(columns=_SWING_COLUMNS),
        "structure_events": pd.DataFrame(columns=_EVENT_COLUMNS),
    }


def smartmoneyconcepts_available() -> bool:
    """Return True when the optional smartmoneyconcepts package is importable."""
    try:
        with redirect_stdout(io.StringIO()):
            pkg = importlib.import_module("smartmoneyconcepts")
    except Exception:
        return False
    return bool(getattr(pkg, "smc", None))


def _smc_module() -> Any | None:
    try:
        with redirect_stdout(io.StringIO()):
            pkg = importlib.import_module("smartmoneyconcepts")
    except Exception:
        return None
    return getattr(pkg, "smc", None)


def _prep_ohlc(one: pd.DataFrame) -> pd.DataFrame:
    required = ["date", "open", "high", "low", "close", "volume"]
    if one.empty or not set(required).issubset(one.columns):
        return pd.DataFrame(columns=required)
    data = one[required].sort_values("date").reset_index(drop=True).copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.dropna(subset=["date", "open", "high", "low", "close"]).reset_index(drop=True)


def _date_at(data: pd.DataFrame, idx: Any, default_pos: int = 0) -> Any:
    try:
        pos = int(idx)
    except Exception:
        pos = default_pos
    pos = max(0, min(pos, len(data) - 1)) if len(data) else 0
    return data["date"].iloc[pos] if len(data) else pd.NaT


def _float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _call_flexible(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call optional smc functions across minor API signature differences."""
    try:
        return fn(*args, **kwargs)
    except TypeError:
        return fn(*args)


def _normalise_external_fvg(data: pd.DataFrame, raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=_FVG_COLUMNS)
    rows: list[dict[str, Any]] = []
    end_date = data["date"].iloc[-1] if len(data) else pd.NaT
    for idx, row in raw.reset_index(drop=True).iterrows():
        flag = _float(row.get("FVG"), np.nan)
        top = _float(row.get("Top"), np.nan)
        bottom = _float(row.get("Bottom"), np.nan)
        if not np.isfinite(flag) or not np.isfinite(top) or not np.isfinite(bottom) or flag == 0:
            continue
        direction = "bullish" if flag > 0 else "bearish"
        mitigated = np.isfinite(_float(row.get("MitigatedIndex"), np.nan))
        status = "IFVG" if mitigated else "FVG"
        zone_type = f"FVG_{direction.upper()}"
        y0, y1 = sorted([bottom, top])
        strength = abs(y1 - y0) / max(abs((y0 + y1) / 2), 1e-9)
        rows.append(
            {
                "zone_id": f"smc_fvg_{idx}",
                "date": _date_at(data, idx),
                "end_date": end_date,
                "zone_type": zone_type,
                "status": status,
                "y0": y0,
                "y1": y1,
                "direction": direction,
                "strength": strength,
                "label": f"SMC {status} {direction.title()}",
                "source": "smartmoneyconcepts",
            }
        )
    return pd.DataFrame(rows, columns=_FVG_COLUMNS) if rows else pd.DataFrame(columns=_FVG_COLUMNS)


def _normalise_external_swings(data: pd.DataFrame, raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=_SWING_COLUMNS)
    rows: list[dict[str, Any]] = []
    for idx, row in raw.reset_index(drop=True).iterrows():
        flag = _float(row.get("HighLow"), np.nan)
        level = _float(row.get("Level"), np.nan)
        if not np.isfinite(flag) or not np.isfinite(level) or flag == 0:
            continue
        rows.append(
            {
                "date": _date_at(data, idx),
                "price": level,
                "type": "swing_high" if flag > 0 else "swing_low",
                "strength": abs(flag),
                "source": "smartmoneyconcepts",
            }
        )
    return pd.DataFrame(rows, columns=_SWING_COLUMNS) if rows else pd.DataFrame(columns=_SWING_COLUMNS)


def _normalise_external_events(data: pd.DataFrame, raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=_EVENT_COLUMNS)
    rows: list[dict[str, Any]] = []
    for idx, row in raw.reset_index(drop=True).iterrows():
        level = _float(row.get("Level"), np.nan)
        bos = _float(row.get("BOS"), np.nan)
        choch = _float(row.get("CHOCH"), np.nan)
        for kind, flag in [("BOS", bos), ("CHOCH", choch)]:
            if not np.isfinite(flag) or flag == 0:
                continue
            direction = "UP" if flag > 0 else "DOWN"
            rows.append(
                {
                    "date": _date_at(data, idx),
                    "price": level if np.isfinite(level) else _float(data["close"].iloc[min(idx, len(data) - 1)]),
                    "event_type": f"{kind}_{direction}",
                    "reference_price": level,
                    "description": f"smartmoneyconcepts {kind}_{direction}",
                    "source": "smartmoneyconcepts",
                }
            )
    return pd.DataFrame(rows, columns=_EVENT_COLUMNS) if rows else pd.DataFrame(columns=_EVENT_COLUMNS)


def _normalise_external_order_blocks(data: pd.DataFrame, raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=_OB_COLUMNS)
    rows: list[dict[str, Any]] = []
    end_date = data["date"].iloc[-1] if len(data) else pd.NaT
    for idx, row in raw.reset_index(drop=True).iterrows():
        flag = _float(row.get("OB"), np.nan)
        top = _float(row.get("Top"), np.nan)
        bottom = _float(row.get("Bottom"), np.nan)
        if not np.isfinite(flag) or not np.isfinite(top) or not np.isfinite(bottom) or flag == 0:
            continue
        direction = "bullish" if flag > 0 else "bearish"
        y0, y1 = sorted([bottom, top])
        rows.append(
            {
                "zone_id": f"smc_ob_{idx}",
                "date": _date_at(data, idx),
                "end_date": end_date,
                "zone_type": f"OB_{direction.upper()}",
                "y0": y0,
                "y1": y1,
                "direction": direction,
                "strength": max(0.0, _float(row.get("Percentage"), 50.0) / 100.0),
                "label": f"SMC OB {direction.title()}",
                "source": "smartmoneyconcepts",
            }
        )
    return pd.DataFrame(rows, columns=_OB_COLUMNS) if rows else pd.DataFrame(columns=_OB_COLUMNS)


def _normalise_external_liquidity(data: pd.DataFrame, raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=_LIQUIDITY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for idx, row in raw.reset_index(drop=True).iterrows():
        flag = _float(row.get("Liquidity"), np.nan)
        level = _float(row.get("Level"), np.nan)
        if not np.isfinite(flag) or not np.isfinite(level) or flag == 0:
            continue
        swept = np.isfinite(_float(row.get("Swept"), np.nan))
        direction = "buy_side" if flag > 0 else "sell_side"
        rows.append(
            {
                "date": _date_at(data, idx),
                "level": level,
                "direction": direction,
                "status": "swept" if swept else "resting",
                "strength": abs(flag),
                "label": f"SMC Liquidity {direction.replace('_', ' ').title()}",
                "source": "smartmoneyconcepts",
            }
        )
    return pd.DataFrame(rows, columns=_LIQUIDITY_COLUMNS) if rows else pd.DataFrame(columns=_LIQUIDITY_COLUMNS)


def _fallback_context(data: pd.DataFrame, *, swing_window: int, min_break_pct: float) -> dict[str, Any]:
    ctx = _empty_context("fallback")
    if data.empty:
        return ctx
    structure = detect_market_structure(data, swing_window=swing_window, min_break_pct=min_break_pct)
    swings = structure.get("swings", pd.DataFrame()).copy()
    events = structure.get("structure_events", pd.DataFrame()).copy()
    if not swings.empty:
        swings["source"] = "fallback"
        ctx["swings"] = swings.reindex(columns=_SWING_COLUMNS)
    if not events.empty:
        events["source"] = "fallback"
        ctx["structure_events"] = events.reindex(columns=_EVENT_COLUMNS)
    return ctx


def build_smc_context(
    one: pd.DataFrame,
    *,
    swing_window: int = 3,
    min_break_pct: float = 0.003,
    prefer_external: bool = True,
) -> dict[str, Any]:
    """Build normalized SMC context from smartmoneyconcepts when available.

    The returned schema is stable for Plotly overlays. If the optional package is
    unavailable or errors, the function returns a fallback context based on the
    existing internal market-structure engine. No caller should need to import the
    third-party package directly.
    """
    data = _prep_ohlc(one)
    if data.empty:
        return _empty_context("fallback")
    if not prefer_external:
        return _fallback_context(data, swing_window=swing_window, min_break_pct=min_break_pct)

    smc = _smc_module()
    if smc is None:
        return _fallback_context(data, swing_window=swing_window, min_break_pct=min_break_pct)

    try:
        fvg_raw = _call_flexible(smc.fvg, data.copy()) if hasattr(smc, "fvg") else None
        swings_raw = _call_flexible(smc.swing_highs_lows, data.copy(), swing_length=swing_window) if hasattr(smc, "swing_highs_lows") else None
        bos_raw = _call_flexible(smc.bos_choch, data.copy(), swings_raw, close_break=True) if hasattr(smc, "bos_choch") and swings_raw is not None else None
        ob_raw = _call_flexible(smc.ob, data.copy(), swings_raw) if hasattr(smc, "ob") and swings_raw is not None else None
        liq_raw = _call_flexible(smc.liquidity, data.copy(), swings_raw) if hasattr(smc, "liquidity") and swings_raw is not None else None
        return {
            "engine": "smartmoneyconcepts",
            "error": None,
            "fvg_zones": _normalise_external_fvg(data, fvg_raw),
            "order_blocks": _normalise_external_order_blocks(data, ob_raw),
            "liquidity": _normalise_external_liquidity(data, liq_raw),
            "swings": _normalise_external_swings(data, swings_raw),
            "structure_events": _normalise_external_events(data, bos_raw),
        }
    except Exception as exc:
        ctx = _fallback_context(data, swing_window=swing_window, min_break_pct=min_break_pct)
        ctx["error"] = f"smartmoneyconcepts failed: {exc}"
        return ctx
