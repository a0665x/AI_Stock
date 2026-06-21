from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import pandas as pd

CANONICAL_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]

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


def fetch_yfinance_history(tickers: Iterable[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch historical OHLCV via yfinance as a portable fallback provider.

    This is the ARM-friendly provider used before OpenD/Futu can be deployed on a supported host.
    """
    import yfinance as yf

    frames: list[pd.DataFrame] = []
    for ticker in [str(t).strip() for t in tickers if str(t).strip()]:
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
