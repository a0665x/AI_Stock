# 2026-06-24 smartmoneyconcepts adapter

## Goal
接入 `smartmoneyconcepts` Python 套件作為隔日掛單技術圖的可選 SMC engine，提升 FVG / Swing / BOS / CHoCH / Order Block / Liquidity 的計算來源；保留內建 fallback，避免套件不可用時破壞 UI。

## Implementation
- 新增 `src/ai_stock/smc_adapter.py`
  - `smartmoneyconcepts_available()`：安靜檢查套件是否可匯入。
  - `build_smc_context()`：統一輸出 schema：
    - `fvg_zones`
    - `order_blocks`
    - `liquidity`
    - `swings`
    - `structure_events`
  - 優先使用 `smartmoneyconcepts.smc`：
    - `fvg()`
    - `swing_highs_lows()`
    - `bos_choch()`
    - `ob()`
    - `liquidity()`
  - 套件不可用或計算失敗時 fallback 到內建 `detect_market_structure()`。
- 更新 `src/ai_stock/swing_order_chart.py`
  - 技術圖優先讀 `build_smc_context()`。
  - 圖上新增：
    - `SMC Order Block` trace / 區塊
    - `SMC Liquidity` trace / 水平線
  - FVG / IFVG、Swing、BOS/CHoCH 若外部 engine 沒資料，仍使用既有內建規則。
- 更新 `pyproject.toml`
  - 加入 `smartmoneyconcepts>=0.0.27`。
- 更新 `app.py`
  - 隔日掛單技術圖說明文字標示 smartmoneyconcepts 優先、內建 fallback。

## Validation
- 本機：`65 passed`
- Docker：`65 passed`
- Docker smoke：`smartmoneyconcepts_available=True`，`engine=smartmoneyconcepts`，圖表包含 `SMC Order Block` 與 `SMC Liquidity` trace。
- Streamlit health：`ok`。

## Notes
- 這仍是研究輔助，不自動下單。
- `smartmoneyconcepts` 主要基於 OHLCV 計算 SMC 訊號，不代表真正交易所 order flow。
- Liquidity / OB 若資料不足可能為空；圖表仍保留空 trace 與 fallback，避免 crash。
