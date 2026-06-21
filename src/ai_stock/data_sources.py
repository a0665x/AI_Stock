from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable, Literal

import pandas as pd

CANONICAL_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]
YFINANCE_DISK_CACHE_TTL_SECONDS = 60 * 60

_COLUMN_ALIASES = {
    "日期": "date",
    "Date": "date",
    "datetime": "date",
    "代號": "ticker",
    "股票代號": "ticker",
    "symbol": "ticker",
    "Symbol": "ticker",
    "開盤": "open",
    "Open": "open",
    "最高": "high",
    "High": "high",
    "最低": "low",
    "Low": "low",
    "收盤": "close",
    "Close": "close",
    "成交股數": "volume",
    "成交量": "volume",
    "Volume": "volume",
}


@dataclass(frozen=True)
class DataRequest:
    tickers: tuple[str, ...]
    period: str = "1y"
    interval: str = "1d"
    provider: Literal["yfinance", "futu", "csv"] = "yfinance"


def normalize_ohlcv(df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    """Normalize common OHLCV schemas into the project canonical format.

    Canonical columns: date, ticker, open, high, low, close, volume.
    Supports the Chinese column names already used by the legacy engine.
    """
    out = df.rename(columns={c: _COLUMN_ALIASES.get(c, c) for c in df.columns}).copy()
    if "ticker" not in out.columns:
        if ticker is None:
            raise ValueError("ticker column is missing; pass ticker=... for single-symbol data")
        out["ticker"] = ticker
    missing = set(CANONICAL_COLUMNS) - set(out.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")

    out = out[CANONICAL_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["ticker"] = out["ticker"].astype(str)
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["date", "ticker", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)


def _normalized_tickers(tickers: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(t).strip().upper() for t in tickers if str(t).strip())


def _yfinance_cache_dir() -> Path:
    return Path(os.environ.get("AI_STOCK_MARKET_CACHE_DIR", "runtime/market_cache")).expanduser()


def _yfinance_cache_path(tickers: Iterable[str], period: str, interval: str, cache_dir: Path | None = None) -> Path:
    payload = {
        "provider": "yfinance",
        "tickers": list(_normalized_tickers(tickers)),
        "period": period,
        "interval": interval,
        "schema": 1,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    label = "_".join(payload["tickers"])[:60] or "empty"
    safe_label = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in label)
    return (cache_dir or _yfinance_cache_dir()).joinpath(f"yf_{safe_label}_{period}_{interval}_{digest}.pkl")


def clear_yfinance_disk_cache(cache_dir: str | Path | None = None) -> int:
    """Delete persisted yfinance cache files and return how many files were removed."""
    root = Path(cache_dir).expanduser() if cache_dir is not None else _yfinance_cache_dir()
    if not root.exists():
        return 0
    removed = 0
    for path in root.glob("yf_*.pkl"):
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def _read_yfinance_disk_cache(path: Path, ttl_seconds: int) -> pd.DataFrame | None:
    if ttl_seconds <= 0 or not path.exists():
        return None
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > ttl_seconds:
        return None
    try:
        cached = pd.read_pickle(path)
    except Exception:
        return None
    return normalize_ohlcv(cached) if not cached.empty else cached


def _write_yfinance_disk_cache(path: Path, prices: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    prices.to_pickle(tmp)
    tmp.replace(path)


def _download_yfinance_history(tickers: Iterable[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Download historical OHLCV via yfinance without consulting local caches."""
    import yfinance as yf

    frames: list[pd.DataFrame] = []
    for ticker in _normalized_tickers(tickers):
        raw = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False)
        if raw.empty:
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0] for c in raw.columns]
        raw = raw.reset_index().rename(columns={"Date": "date", "Datetime": "date"})
        frames.append(normalize_ohlcv(raw, ticker=ticker))
    if not frames:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def fetch_yfinance_history(tickers: Iterable[str], period: str = "1y", interval: str = "1d", *, disk_cache_ttl_seconds: int = YFINANCE_DISK_CACHE_TTL_SECONDS) -> pd.DataFrame:
    """Fetch historical OHLCV via yfinance with a persistent disk cache.

    This is the ARM-friendly provider used before OpenD/Futu can be deployed on a supported host.
    The disk cache survives Docker/container restarts when runtime/ is mounted as a volume.
    """
    normalized = _normalized_tickers(tickers)
    cache_path = _yfinance_cache_path(normalized, period, interval)
    cached = _read_yfinance_disk_cache(cache_path, disk_cache_ttl_seconds)
    if cached is not None:
        return cached

    prices = _download_yfinance_history(normalized, period=period, interval=interval)
    if not prices.empty and disk_cache_ttl_seconds > 0:
        _write_yfinance_disk_cache(cache_path, prices)
    return prices


def fetch_futu_history(*args, **kwargs) -> pd.DataFrame:
    """Placeholder adapter for Futu OpenAPI.

    The Python futu-api package can be installed, but actual quote access requires OpenD.
    OpenD is not available on this ARM host, so this function deliberately fails with an actionable message.
    """
    raise RuntimeError(
        "Futu OpenAPI historical quote fetching requires a running OpenD service. "
        "This ARM host cannot run OpenD directly; use yfinance/csv fallback here or point to OpenD on another machine."
    )


def load_history(request: DataRequest) -> pd.DataFrame:
    if request.provider == "yfinance":
        return fetch_yfinance_history(request.tickers, period=request.period, interval=request.interval)
    if request.provider == "futu":
        return fetch_futu_history(request)
    raise ValueError("CSV provider should be loaded by normalize_ohlcv(pd.read_csv(...))")
