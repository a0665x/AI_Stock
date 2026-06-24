# 隔日掛單技術圖與 Neural UKF Momentum 規劃

日期：2026-06-24

## 使用者需求

使用者指出隔日掛單計畫不能只給目標買賣價，還需要在同一頁看到支撐該價格的技術圖表：K 線十字游標、布林、RSI、MACD、成交量、K 線型態、趨勢線 / 掛單區間，以及能輔助 swing trading 的去噪動能指標。使用者也提出後續希望研究 LSTM / Transformer + UKF 的多時序動能模型，並想知道除了 yfinance 價格之外可以加入哪些輿論 / 事件 / 市場 regime 輸入。

## 已確認 / 已補強

- `src/ai_stock/swing_order_chart.py` 已提供隔日掛單技術圖核心：
  - K 線 candlestick
  - SMA20 / SMA60
  - Bollinger upper / lower 與區間填色
  - 成交量與 volume ratio
  - RSI14
  - MACD / signal / histogram
  - K 線型態：DOJI、HAMMER、SHOOTING_STAR、BULLISH_ENGULFING、BEARISH_ENGULFING、strong body
  - 隔日買進區、隔日賣出區、戰術停損、硬停損、策略買進、策略停利水平線
  - x unified hover 與 spike line，滑鼠移到任一天可看多面板同步資訊
  - UKF-style denoised momentum：用 RSI、MACD hist、布林位置、量能比、5D return 建立 raw momentum，再以狀態空間濾波平滑成 UKF momentum / velocity / noise band / state label
- `src/ai_stock/app.py` 的「隔日掛單計畫」頁籤已支援：
  - 上方掛單表格 `st.dataframe(..., on_select='rerun', selection_mode='single-row')`
  - 點選 row 後更新 `st.session_state.selected_order_ticker`
  - 若 Streamlit/瀏覽器不支援 row select，提供 `選擇下方技術圖股票` selectbox fallback
  - 下方顯示隔日掛單技術圖與 RSI / MACD / 布林位置 / 量能比 / UKF 動能摘要
- 新增測試：`tests/test_swing_order_chart.py`
  - 驗證 UKF 動能 bounded、noise band 包住狀態值
  - 驗證 K 線型態偵測 doji / bullish engulfing
  - 驗證技術圖包含 K 線、布林、RSI、MACD、UKF、Buy/Sell zone
  - 驗證 technical context summary 可輸出 swing trading 所需摘要

## Neural + UKF TODO

新增 `spec/neural_ukf_momentum_plan.md`，紀錄後續模型規劃：

1. 先建立 feature store：價格、技術指標、市場結構、持倉、隔日掛單、回測、因子研究、market regime。
2. 加入外部時序資料來源：
   - earnings / macro calendar
   - news / RSS / Finnhub / Polygon / Benzinga / GDELT
   - Reddit / X / Google Trends 等注意力與輿論 proxy
   - SPY / QQQ / VIX / sector ETF / FRED macro series
   - options IV / put-call / skew（若有付費資料）
3. 建立 supervised multi-horizon sequence dataset：1D / 3D / 5D / 10D direction、return、touch event、stop/TP event。
4. 先用 logistic / gradient boosting 作 baseline，再試 LSTM / GRU / Transformer。
5. Neural output 不直接下單，而是作為 UKF observation，產生 filtered momentum state 與 confidence band。
6. 只有 walk-forward AUC、baseline uplift、策略 PnL、max drawdown、calibration 都過門檻後，才允許影響隔日掛單價格。

## 安全邊界

目前 UKF 動能是透明技術指標，不是深度學習預測，也不自動下單。後續任何 broker API、真實下單或 API key 儲存都需要使用者另外明確同意。

## 驗證

- `pytest tests/test_swing_order_chart.py -q`：4 passed
- `pytest -q && python -m compileall src`：60 passed
