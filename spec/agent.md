# agent quickstart

進入這個專案時，先讀：
1. `spec/PROJECT_MAP.md`
2. `spec/project_herness.md`
3. `spec/map.md`
4. `spec/references/original-engine-notes.md`
5. 最新的 `spec/task_understandings/*.md`

## 這個專案要做什麼
從原始 `CH4_CStock_v1_0_5` 擷取可重用概念，建立新的股票決策輔助系統，而不是直接照搬整個 notebook trading engine。

現階段已從純選股骨架擴展為：歷史價格 / K 線、技術分析、股票間相關性、ARIMA / sklearn fallback 走勢估計、Kelly sizing、回測、因子研究，以及 Streamlit 決策報表。

## 目前最重要的檔案
- `src/ai_stock/data_sources.py`：資料來源、OHLCV schema、yfinance fallback、persistent disk cache、Futu/OpenD 邊界
- `src/ai_stock/analytics.py`：技術指標 snapshot、股票相關性表格、正/負相關 peer pressure
- `src/ai_stock/attribution.py`：SHAP TreeExplainer / permutation fallback 歸因分析
- `src/ai_stock/factor_research.py`：sliding-window 因子研究，過去 N 天技術因子 → 未來 1/3/5/10 天漲跌比較，輸出 horizon 勝率/AUC 趨勢、每檔股票 × horizon 表現熱力圖、SHAP/fallback importance、相關係數、分組勝率與 y heatmap
- `src/ai_stock/backtesting.py`：快速 walk-forward 回測、勝率/最大回撤/停損命中率/累積報酬、持有天數與出場規則比較
- `src/ai_stock/forecasting.py`：ARIMA / sklearn fallback、Kelly、買賣停損參考、回撤與 risk unit、Kelly / 決策原因提示
- `src/ai_stock/order_planner.py`：隔日掛單計畫；用持倉、決策報表與最近日內波動產生可成交買賣區、戰術/硬停損與觸及機率；整合 15m / 1h / 1d SMC 信心分數、買賣急迫度與優先處理分數；可合併隔日策略工作台的最終策略結果，回寫最終買賣停損停利區間；研究輔助，不自動下單
- `src/ai_stock/order_strategy_workbench.py`：隔日策略工作台；按鈕觸發比較布林、SMC、UKF 動能、KD/MACD、SHAP 因子代理策略，依股票範圍、持有天數、風險耐受度與回測期間輸出策略勝率、適配分數與最終買賣停損區間；同時提供非重疊交易狀態機買賣點、每筆交易垂直進出場線、綠/紅 PnL 連線、可選 SMC overlay、權益曲線、回撤曲線與績效摘要視覺化 payload；結果會合併回隔日掛單計畫；研究輔助，不自動下單
- `src/ai_stock/training_data.py`：分析結果數據 / Training Data；每檔股票每日一列，包含 OHLCV、技術指標、SMC flags、UKF、K 線型態與未來 N 天報酬/漲跌目標，並排序最相關欄位，作為未來三天趨勢 AI model 的資料基礎
- `src/ai_stock/swing_order_chart.py`：隔日掛單技術圖；表格 row 聯動 K 線、布林、RSI、MACD、成交量、K 線型態、FVG/IFVG、Order Block、Liquidity、Swing、SFP、BOS/ChoCH、掛單區與 UKF-style 去噪動能
- `src/ai_stock/smc_adapter.py`：smartmoneyconcepts optional adapter；第三方 SMC engine 優先，資料不足或套件失敗時 fallback 內建規則
- `spec/next_day_order_planner_spec.md`：隔日掛單計畫完整 spec，含可成交價格、SMC 多週期、策略工作台最終推薦回寫、熱力表與圖例說明
- `spec/next_day_strategy_workbench_spec.md`：隔日策略工作台完整 spec，含股票選擇、可承受停損幅度、預計持有天數、策略選擇、歷史驗證期間、策略適配分數、每筆交易垂直線/PnL 連線、個人交易偏好、最終掛單區間與回寫隔日掛單計畫
- `spec/ui_simplification_training_data_goal.md`：持續 UI 簡化與 Training Data 目標；說明等待確認、horizon 改名、頁籤收斂與 subagent 使用者視角 QA
- `src/ai_stock/trade_vision.py`：智能交易視覺中心；市場結構、BOS/ChoCH、支撐壓力/供需區、MTF Matrix、Signal Score 與交易計畫視覺化
- `src/ai_stock/pipeline.py`：程式化分析 pipeline
- `src/ai_stock/app.py`：Streamlit UI；主導航已收斂為 `今日決策`、`交易計畫`、`圖表分析`、`策略驗證`、`研究中心`；今日決策含 TradingView 式行動清單與人話版 BUY/SELL/WAIT 顯示；右上角可切換繁中 / English / 日本語 / 한국어；sidebar 只保留資料來源、股票清單、歷史區間、K 線週期、決策天數、個人交易偏好、CSV 上傳與手動刷新等全域設定，頁面專屬參數留在各頁籤內
- `src/ai_stock/i18n.py`：Web UI 多語言字典與欄位翻譯 helper
- `spec/tutor_guide.md`：新手導讀，說明如何操作 UI、理解技術指標 / Kelly / 等待確認 / 回測 / 因子研究，以及如何把勝率與 AUC 轉成買賣觀察
- `spec/neural_ukf_momentum_plan.md`：LSTM/Transformer + UKF 多時序動能模型 TODO / 架構規劃，包含可用外部輿論、事件、宏觀與市場 regime 資料來源
- `src/ai_stock/universe.py` / `features.py` / `selection.py`：初始選股核心
- `tests/test_analysis_pipeline.py`：目前 smoke / behavior tests

## 常用指令
```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
./run.sh --help
./run.sh up
./run.sh status
./run.sh logs
./run.sh down
```

若 `./run.sh` 尚未有執行權限，可先用：
```bash
bash run.sh up
```

本機開發模式：
```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
. .venv/bin/activate
pytest -q
streamlit run src/ai_stock/app.py --server.headless true --server.port 8507 --server.address 0.0.0.0
```

若 `.venv` 不存在：
```bash
uv venv .venv
. .venv/bin/activate
uv pip install -e '.[dev,futu]'
```

## 重要原則
- 優先模組化，不讓 notebook / UI 承擔商業邏輯
- 優先可測試的 DataFrame in / DataFrame out 介面
- ARM 主機不能直接跑 Futu OpenD；若要即時行情，用遠端 OpenD 或先以 yfinance/CSV 打通流程
- yfinance 快取分兩層：Streamlit 記憶體 cache + Docker 版 `docker_runtime/market_cache/yf_*.pkl` 磁碟 cache。UI「重新抓資料 / 更新分析」會同步清除兩層 cache。
- 預測先保持可解釋，不用 AI 黑箱直接喊漲跌
