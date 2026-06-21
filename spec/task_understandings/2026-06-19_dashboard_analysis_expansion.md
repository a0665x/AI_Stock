# 2026-06-19 Dashboard Analysis Expansion

## 任務
使用者希望把 `AI_Stock` 從初始選股骨架推進到可視化決策輔助工具：
1. 可即時或近即時查看歷史價格曲線 / K 線
2. 可輸入多個股票代號並產生技術分析與市場關係表格
3. 保留未來走勢估計，但先不用 AI 黑箱模型，改用可解釋數學 / 統計 baseline
4. UI 與報表要能一眼看出買價 / 賣價 / 停損參考
5. ARM 主機不能跑 Futu OpenD，因此需先用替代 API 打通架構

## 本次完成
- 建立 `pyproject.toml`，用專案 `.venv` 管理依賴，不污染系統 Python
- 安裝並驗證：pandas、plotly、streamlit、yfinance、scikit-learn、statsmodels、pytest、futu-api
- 新增 `src/ai_stock/data_sources.py`
  - canonical OHLCV schema: `date/ticker/open/high/low/close/volume`
  - 支援中文欄位 normalization
  - yfinance fallback provider
  - Futu/OpenD adapter boundary 與 ARM 限制訊息
- 新增 `src/ai_stock/analytics.py`
  - 最新技術 snapshot
  - 多股票報酬相關性表格
- 新增 `src/ai_stock/forecasting.py`
  - ARIMA baseline
  - sklearn HuberRegressor fallback
  - Kelly fraction
  - suggested buy / sell / stop-loss / action
- 新增 `src/ai_stock/pipeline.py`
  - DataFrame in/out 的完整分析 pipeline
- 新增 `src/ai_stock/app.py`
  - Streamlit UI：K 線、SMA、技術表、相關性表、決策報表、CSV 下載
- 新增 `tests/test_analysis_pipeline.py`
  - schema normalization、相關性、技術 snapshot、決策報表測試
- 更新 README 與 spec 快速入口文件

## 驗證結果
- `pytest -q`：4 passed
- `python -m compileall -q src tests`：通過
- synthetic pipeline smoke：產生 prices / technical_snapshot / correlations / decision_report
- Streamlit health check：`http://127.0.0.1:8507/_stcore/health` 回傳 `ok`
- yfinance fallback：成功抓取 AAPL/MSFT 近一個月資料
- `futu-api` import：OK；但 OpenD 仍需外部服務

## 目前邊界
- 尚未做自動交易與下單
- 尚未做完整台股資料源品質驗證
- 尚未串遠端 Futu OpenD
- 預測結果是 explainable baseline，不是投資保證

## 建議下一步
1. 決定第一版主要市場：美股、台股，或兩者都要
2. 若要台股即時 / 盤中行情，提供或建立一台可跑 Futu OpenD 的主機，ARM 主機只連遠端 OpenD
3. 擴充回測：把「前幾天依照報表買/賣會怎樣」量化成 hit-rate、max drawdown、profit factor
4. 增加 watchlist 儲存與報表排程
5. 加入更多非價格因子：財報、營收、法人、新聞事件，但仍保持 DataFrame in/out
