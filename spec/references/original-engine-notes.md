# Original Engine Notes

參考來源：
- `/home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI股票交易引擎原始碼/CH4_CStock_v1_0_5/Part1_data_collector.ipynb`
- `/home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI股票交易引擎原始碼/CH4_CStock_v1_0_5/Part2_model_training.ipynb`
- `/home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI股票交易引擎原始碼/CH4_CStock_v1_0_5/Part3_daily_forecast.ipynb`
- `/home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI股票交易引擎原始碼/CH4_CStock_v1_0_5/cstock.py`

## 最值得沿用的概念

### 1. 候選股池不是只有手動自選
原始 `set_combine()` 會把：
- 手動選股
- 現有持股
- 權值股前 N 檔
合成最後 universe。

新版已先在 `src/ai_stock/universe.py` 重做這個概念，但拿掉函式內直接爬網頁的副作用。

### 2. 特徵工程以技術面為骨架
原始 `char_generator()` 包含：
- SMA / EMA
- VMA
- MACD
- RSI / MOM
- KD
- 波動度特徵
- next-day / 60-day label

新版先在 `src/ai_stock/features.py` 用 pandas 實作近似版，暫時不依賴 TA-Lib。

### 3. 核心排序不是單看報酬，而是看風險調整後的報酬
原始 `predict_result()`：
- `original_ratio = pred_60 / history_std * 100`

這是最值得保留的選股中心公式。

### 4. 短中期預測混合出建議價位
原始 `predict_result()`：
- `order_rate = (NEAR_CHASE * pred_1 + FAR_CHASE * pred_60) / (1 + NEAR_CHASE + FAR_CHASE)`

新版保留同概念在 `selection.py`。

## 不建議原封搬移的部分
- 直接覆寫 `current_asset.csv` 的有狀態流程
- notebook 直接操作商業邏輯
- GRU / TensorFlow 舊版訓練碼
- TA-Lib 與 Windows wheel 依賴
- 視覺化與選股邏輯耦合在同一函式

## 新專案第一階段邊界
- 先做選股，不做下單
- 先做可測試模組，不做 notebook 主導流程
- 先支援 DataFrame scoring，不急著搬完整資料抓取器
