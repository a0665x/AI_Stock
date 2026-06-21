from __future__ import annotations

from typing import Iterable, Sequence


def _normalize(values: Iterable[str]) -> list[str]:
    return [str(v).strip() for v in values if str(v).strip()]


def build_universe(
    manual_tickers: Sequence[str],
    current_holdings: Sequence[str] | None = None,
    weighted_constituents: Sequence[str] | None = None,
    train_num: int = 50,
) -> list[str]:
    """重做原始 `set_combine()` 的核心概念。

    與原版不同：
    - 不在函式裡直接爬台指權值股
    - 改由呼叫端提供權值股清單
    - 函式只做 deterministic 的集合合成
    """
    manual = set(_normalize(manual_tickers))
    holdings = set(_normalize(current_holdings or []))
    weighted = _normalize(weighted_constituents or [])[:train_num]
    result = sorted(manual | holdings | set(weighted))
    return result
