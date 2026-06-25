# UI Simplification and Training Data Goal

## Goal
持續把 AI_Stock 從「很多報表頁」收斂成專業決策平台：使用者先看是否需要處理哪檔股票，再看策略與因子是否支持，最後可匯出乾淨 training data 供未來 AI model 預估未來 3 天趨勢。

## Current clarification
- 今日雷達 / 決策總覽的「等待確認」不是沒有模型，也不是 Kelly 造成；它代表舊 forecasting decision report 的預估報酬沒有大過近期波動、ATR、回撤等風險門檻。
- 隔日策略工作台是另一套按鈕觸發的策略回測；它可以產生策略適配與最終買賣區間，但需要逐步整合回主決策語意，避免使用者看到兩套結論。
- `horizon` 對使用者不直覺；UI 應改說「預測幾天後」或「預計持有天數」。

## Target page structure
第一階段保留既有功能，但逐步把頁籤合併為：
1. 決策總覽：今日雷達、最終需要處理的股票、等待確認原因。
2. 掛單與策略：隔日掛單計畫 + 隔日策略工作台 + 策略買賣點。
3. 圖表分析：TradingView-like K 線、SMC、指標 overlays。
4. 研究中心：回測、因子研究、歸因分析、股票關係。
5. 分析結果數據 / Training Data：每日完整 feature table 與 top N correlated columns。

## Training data contract
`src/ai_stock/training_data.py` 產生每檔股票每日一列：
- Identity: `ticker`, `date`
- OHLCV: `open`, `high`, `low`, `close`, `volume`
- Technical indicators: RSI, MACD, KD, Bollinger, ATR, MFI, OBV, volatility, support/resistance
- Signal columns: MACD cross, KD cross, near support/resistance, candlestick patterns
- SMC columns: FVG, Order Block, Liquidity, Swing, BOS/ChoCH flags
- UKF columns: `ukf_momentum`, `ukf_velocity`, `raw_momentum`
- Targets: `forward_return_3d`, `target_up_3d`, `target_close_3d`, plus `target_available_3d` so the last N rows without future answers are not accidentally used as labels

## Top factor ranking
Training Data page ranks columns by absolute Pearson/Spearman relationship to future return. This is a data-quality and feature-screening tool, not final SHAP or model training.

Training Data generation must be button-triggered, not automatic on first page load, because SMC/UKF feature generation can be relatively slow.

## Product iteration rule
Use subagent/browser user-view QA after each major UI consolidation:
- Can a first-time user understand what each tab is for?
- Are technical terms translated to plain language?
- Does the page answer: which stock, buy or sell, price range, why, and historical evidence?

## Safety
- Research assistant only; no broker connection or auto-ordering.
- Runtime holdings/cache/secrets remain ignored and must not be committed.
