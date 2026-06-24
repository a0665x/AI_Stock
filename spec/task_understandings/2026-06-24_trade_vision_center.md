# Task Understanding: Trade Vision Center

Date: 2026-06-24

## Goal
新增「智能交易視覺中心 / Trade Vision Center」頁簽，把決策報表、價格圖表、持倉下單計畫、回測與結構訊號整合成一個專業交易視覺化研究面板；不自動下單。

## Implementation
- 新增 `src/ai_stock/trade_vision.py`
  - `detect_market_structure()`：偵測 swing high/low、BOS_UP/BOS_DOWN、CHOCH_UP/CHOCH_DOWN、支撐壓力聚類。
  - `build_trade_zones()`：產生 support/resistance、demand/supply、premium/discount/equilibrium zones。
  - `build_trade_plan_from_decision()`：從決策報表轉成 Entry / SL / TP1 / TP2 / TP3 / RR / Kelly / plan status。
  - `build_mtf_matrix()`：用 1D/1W/1M 統整 trend、momentum、volume、volatility、signal strength。
  - `compute_trade_signal_score()`：依 trend/momentum/volume/structure/risk/portfolio 權重產出 composite score 與狀態。
  - `build_trade_narrative()`：產生 3~6 條中文交易輔助摘要。
  - `build_trade_vision_chart()`：Plotly 進階 K 線圖，含均線、成交量、current price、Entry/SL/TP、risk/reward box、zones、swing、BOS/ChoCH。
- 更新 `src/ai_stock/app.py`
  - 新頁簽放在「價格圖表」後、「回測」前。
  - 使用 `@st.cache_data(ttl=600)` 包裝 structure/zones/MTF 計算。
  - 沿用既有 `prices`, `snapshot`, `report`, `visible_tickers`, `_fmt_price`, `_`, `ACTION_BADGE`。
  - 資料不足時以 `st.info()` 提示，不 crash。
- 更新 `src/ai_stock/i18n.py`
  - 補 Trade Vision Center 主要 UI 文案中/英/日/韓翻譯。

## Tests
- 新增 `tests/test_trade_vision.py`
- 新增 `tests/test_trade_vision_ui_source.py`
- 本機驗證：`46 passed` + compileall 通過。

## Safety
- 此頁為研究輔助與半自動下單計畫視覺化，不連券商、不自動下單、不保存 API key/token。
