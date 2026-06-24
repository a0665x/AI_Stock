# 2026-06-24 Neural-UKF Multi-Modal Momentum Roadmap

## 背景

使用者希望在「隔日掛單計畫」與 swing trading 視覺化中，加入更強的動能判斷：

- 短期先以 UKF / Kalman-style filter 將 RSI、MACD、布林位置、成交量、報酬率等多指標動能去噪。
- 中期規劃 LSTM / Transformer 學習多時序輸入到未來動能的非線性映射，再由 UKF 做即時平滑與狀態更新。
- 目前資料來源以 yfinance OHLCV 為主，缺少輿論、新聞、財報、期權、盤前盤後等外生時序，因此深度模型先列為 TODO，不直接宣稱可提升 out-of-sample 勝率。

## 已落地的短期版本

新增「隔日掛單計畫」下方 swing trading 技術圖：

- K 線與 Plotly 十字游標：hovermode=x unified、x/y spike line。
- SMA20 / SMA60。
- Bollinger Upper / Lower。
- 成交量與 Volume Ratio。
- RSI14。
- MACD / MACD Signal / MACD Histogram。
- K 線型態標記：DOJI、HAMMER、SHOOTING_STAR、BULLISH_ENGULFING、BEARISH_ENGULFING、強多/強空實體。
- 隔日買進區 / 隔日賣出區 / 戰術停損 / 硬停損 / 策略買進 / 策略停利。
- 輕量 UKF-style 動能：輸入 RSI、MACD histogram、布林位置、Volume Ratio、5 日報酬，輸出 raw_momentum、ukf_momentum、velocity、noise band、state_label。

## 下一階段模型架構

### 1. Feature Store

建立每檔 ticker 的 aligned time-series feature table：

內生價格特徵：

- OHLCV、日內 range、gap、ATR、realized volatility。
- RSI、MACD、布林位置、KD/MFI/OBV、SMA/EMA distance。
- Candlestick pattern one-hot / strength。
- Market structure：swing high/low、BOS、ChoCH、support/resistance distance、premium/discount。
- Portfolio context：持倉成本距離、未實現損益、持倉權重。
- Cross-asset context：同/反向關係壓力、sector/peer return。
- Existing decision outputs：relationship_adjusted_return_pct、Kelly、Trade Vision composite score、factor horizon summary。

外生資料候選來源：

- Yahoo Finance / yfinance：價格、volume、基本財報粗資料。
- Polygon.io / Finnhub / Alpha Vantage / Twelve Data：更完整 OHLCV、pre/post market、news sentiment、earnings calendar。
- FMP Financial Modeling Prep：財報、ratio、analyst estimates、earnings calendar。
- SEC EDGAR / companyfacts：10-K/10-Q 結構化基本面。
- Nasdaq Data Link / FRED：利率、VIX、宏觀變數。
- Reddit / X / StockTwits / GDELT：社群/新聞情緒，但要注意 API 成本、rate limit、雜訊與合規。
- Options API：IV、skew、put/call ratio、open interest；對隔日掛單和波動預測很有用，但通常需要付費資料源。

### 2. Supervised Target

依使用場景分開 target，避免一個模型解所有問題：

- next_day_direction：t+1 close/open 或 close/close 是否上漲。
- next_day_reachability：隔日是否觸及 buy zone / sell zone / tactical stop。
- forward_return_h：h=1/3/5/10 日 forward return。
- swing_exit_quality：按照 Smart Tuning 最佳 exit rule 的交易結果。
- momentum_state：未來 h 日 risk-adjusted return 是否大於門檻。

### 3. Neural Encoder

先用低風險模型，再升級：

Phase A：sklearn baseline

- HistGradientBoosting / RandomForest / LogisticRegression。
- 優點：樣本少也比較穩，可用 permutation importance/SHAP fallback。

Phase B：Sequence neural model

- LSTM / GRU：輸入 shape = [batch, lookback_days, feature_dim]。
- Temporal Convolution / TCN：較快、對小資料更穩。
- Transformer Encoder：等資料量和外生特徵夠再上，避免過擬合。

### 4. Neural + UKF Hybrid

模型輸出不是直接當買賣點，而是作為 UKF measurement：

state vector 建議：

- latent_price_level
- latent_momentum
- latent_volatility
- latent_reachability_bias

measurement vector：

- neural predicted return / direction probability
- technical momentum score
- realized close / range
- volume shock
- sentiment shock
- option-implied volatility shock

UKF 角色：

- 將 neural noisy output 平滑成穩定 momentum state。
- 即時更新隔日掛單 bias：買進區靠近/遠離現價、賣出區上移/下移、戰術停損收緊/放寬。
- 輸出不確定性 band，避免只看單點預測。

### 5. Validation

必須做 walk-forward，不可隨機切分：

- train window：過去 1-3 年。
- validation：下一段時間。
- test：最近未見資料。
- metric：AUC、precision@top-k、hit rate、touch rate、profit factor、max drawdown、calibration curve。
- 交易面 metric：隔日限價單觸及率、觸及後 MAE/MFE、停損誤殺率、分批停利成功率。

### 6. UI 落地

未來可新增或擴充頁籤：

- 「模型訓練 / Model Lab」：顯示資料來源、feature coverage、樣本數、walk-forward 表現。
- 「隔日掛單計畫」：新增 neural_ukf_momentum、uncertainty band、reachability probability calibration。
- 「因子研究」：加入外生特徵群組重要度，例如 price/volume/sentiment/options/macro。

## 風險與限制

- yfinance 只有 OHLCV 時，神經網路很容易過擬合；不應宣稱能提升樣本外勝率。
- 社群/新聞情緒延遲、API 成本、ticker disambiguation 都是風險。
- Options / premarket 資料最適合隔日掛單，但多數來源需要付費。
- 任何模型輸出都只能作研究輔助，不自動下單。

## 建議實作順序

1. 先完成目前已做的 UKF-style 技術圖與 row selection 聯動。
2. 建立 feature store schema 與資料品質報表。
3. 加入免費/低成本外生資料 MVP：FRED/VIX、earnings calendar、Yahoo/FMP basic fundamentals。
4. 加入可選付費資料 adapter：Polygon/Finnhub/options。
5. 做 next_day_reachability baseline model。
6. 只有在樣本數與外生資料穩定後，再加 LSTM/TCN/Transformer。
7. 最後用 UKF 融合 neural output 與技術/成交量/情緒輸入。
