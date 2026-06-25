# AI_Stock Project Map

## 專案定位
`AI_Stock` 是從 `CH4_CStock_v1_0_5` 提煉出來的新版股票決策輔助專案。

目前定位從「單純選股骨架」擴展為：
- 歷史價格 / K 線圖表與互動式 UI；K 線可疊加買進 / 賣出 / 停損參考線與回測 B/S marker
- 今日機會雷達：以卡片快速摘要每檔股票的決策、Kelly、回測勝率與買賣價位
- 策略健檢卡：將樣本數、最大回撤、Profit Factor、勝率、累積報酬與 Kelly 狀態轉成新手可讀警訊
- Watchlist + mini sparkline：左側快速顯示各股票最新收盤、1日漲跌、決策狀態與迷你走勢
- 市場熱力圖：以格子大小呈現活躍度、顏色呈現近 5 日報酬，快速找出強弱標的
- Smart Tuning Lite：按鈕觸發掃描持有天數、出場規則與風險寬度，依報酬、勝率、Profit Factor、回撤與停損率排名
- 智能交易視覺中心 / Trade Vision Center：整合進階 K 線、市場結構、BOS/ChoCH、支撐壓力 / 供需區、Entry/SL/TP、Risk/Reward box、MTF Matrix、Signal Score 與 AI Trade Narrative
- 隔日掛單計畫 / Next-Day Order Planner：基於持倉、決策報表與最近日內波動，輸出隔日買進 / 賣出區、戰術停損、硬停損、觸及機率與建議單型；整合 15m / 1h / 1d SMC 訊號產生 SMC 信心分數、買進急迫度、賣出急迫度與優先處理熱力表；若已執行隔日策略工作台，會回寫最終推薦來源/方向/策略/適配分數與最終買賣停損停利區間；表格 row 可聯動下方 swing trading 技術圖，顯示 K 線十字游標、布林、RSI、MACD、成交量、K 線型態、smartmoneyconcepts 優先 / 內建 fallback 的 FVG/IFVG、Order Block、Liquidity、Swing High/Low、SFP 假突破、BOS/ChoCH 結構突破與 UKF-style 去噪動能；研究輔助，不自動下單
- 隔日策略工作台 / Next-Day Strategy Workbench：按鈕觸發的策略適配檢查；使用者先選單檔或全選、設定風險耐受度、指定 1/5/10/15/30 天持有基準、勾選布林/SMC/UKF/KD-MACD/SHAP 因子代理策略與回測期間，輸出勝率、Profit Factor、回撤、策略適配分數、BUY/SELL/WAIT 迫切度與最終買賣停損區間；同頁可用股票下拉與策略多選檢視策略買賣點、每筆交易垂直進出場虛線、綠/紅獲利虧損連線、策略買賣區、SMC overlay、權益曲線、回撤曲線與策略績效摘要；策略適配分數顏色代表高/中/弱適配，不是 SHAP 正負；左側個人交易偏好可記錄不做當沖、每日每股掛單次數、每次股數/張數與習慣持有天數；結果會合併回隔日掛單計畫作為最終人工掛單區間
- Sidebar 重構：左側只保留資料來源、股票清單、歷史區間、K 線週期、決策天數、個人交易偏好、CSV 上傳與手動刷新等全域設定；回測/Smart Tuning、因子研究、價格圖成交量等頁面專屬控制項移到各自頁籤內
- 研究與訓練資料 / Training Data Center：整理每日價格、技術指標、SMC 信號、UKF/K 線型態、未來 1/3/5/10 天報酬與漲跌目標，並排序最有相關性的前 N 個欄位，作為未來 AI model 預估三天趨勢的資料基礎
- 技術分析 snapshot
- 多股票報酬相關性分析（stock relationship / shop analysis）
- 不使用黑箱 AI 的第一版走勢估計：ARIMA 優先、sklearn robust regression fallback
- Kelly sizing、買價 / 賣價 / 停損參考報表
- walk-forward 回測：勝率、最大回撤、停損命中率、累積報酬、逐筆交易、equity curve，以及不同持有天數 / 出場規則比較
- 因子研究：sliding window 將過去 N 天 K線/KD/MACD/RSI/量能/波動/回撤等因子作為 X，將未來 1/3/5/10 天漲跌分別作為 y，輸出各 horizon 的勝率/AUC 趨勢、每檔股票 × horizon 表現熱力圖、SHAP/fallback 重要度、相關係數、分組勝率與 y heatmap

仍暫不處理：
- 自動下單
- 實盤交易帳務
- ARM 主機直接啟動 Futu OpenD（Python `futu-api` 可安裝，但 OpenD 需外部支援主機）
- 舊版 TensorFlow / TA-Lib / notebook workflow 原封搬移

## 模組索引
- [`agent.md`](./agent.md)：給 agent 的快速入口
- [`map.md`](./map.md)：簡化地圖
- [`project_herness.md`](./project_herness.md)：Hermes 啟動摘要
- [`tutor_guide.md`](./tutor_guide.md)：新手導讀；解釋 UI 操作、技術指標、Kelly、回測、因子研究與買賣觀察流程
- [`next_day_order_planner_spec.md`](./next_day_order_planner_spec.md)：隔日掛單計畫完整 spec；說明可成交價位、SMC 多週期信心分數、優先處理熱力表、策略工作台最終推薦回寫、row-linked 技術圖與圖例說明
- [`next_day_strategy_workbench_spec.md`](./next_day_strategy_workbench_spec.md)：隔日策略工作台 spec；說明股票範圍、持有天數、風險耐受度、策略勾選、回測期間、策略適配分數、策略買賣點視覺化、每筆交易垂直線/PnL 連線、策略適配顏色說明、個人交易偏好、權益/回撤曲線、最終掛單區間與回寫隔日掛單計畫
- [`ui_simplification_training_data_goal.md`](./ui_simplification_training_data_goal.md)：/goal 式持續優化目標；說明頁籤收斂、等待確認語意、horizon 改為預測幾天後、Training Data contract 與 subagent 使用者視角 QA 規則
- [`references/original-engine-notes.md`](./references/original-engine-notes.md)：原始交易引擎可借鏡點
- [`task_understandings/2026-05-25_ai_stock_bootstrap.md`](./task_understandings/2026-05-25_ai_stock_bootstrap.md)：初始建立紀錄
- [`task_understandings/2026-06-19_dashboard_analysis_expansion.md`](./task_understandings/2026-06-19_dashboard_analysis_expansion.md)：UI / 分析 / 預測擴展紀錄
- [`task_understandings/2026-06-19_streamlit_ui_readability_revamp.md`](./task_understandings/2026-06-19_streamlit_ui_readability_revamp.md)：Streamlit 決策摘要與分頁式 UI 改版紀錄
- [`task_understandings/2026-06-19_indicators_shap_attribution.md`](./task_understandings/2026-06-19_indicators_shap_attribution.md)：技術指標、SHAP 歸因、回撤與股票關係壓力改版紀錄
- [`task_understandings/2026-06-20_shap_button_trigger.md`](./task_understandings/2026-06-20_shap_button_trigger.md)：SHAP 改為按鈕觸發與 session state 保存紀錄
- [`task_understandings/2026-06-20_yfinance_cache_refresh.md`](./task_understandings/2026-06-20_yfinance_cache_refresh.md)：yfinance 行情 1 小時快取與手動刷新按鈕紀錄
- [`task_understandings/2026-06-20_yfinance_disk_cache.md`](./task_understandings/2026-06-20_yfinance_disk_cache.md)：yfinance persistent disk cache 與 Docker volume 保留紀錄
- [`task_understandings/2026-06-20_factor_research_tab.md`](./task_understandings/2026-06-20_factor_research_tab.md)：sliding-window 因子研究頁籤與 Docker 驗證紀錄
- [`task_understandings/2026-06-20_factor_horizon_metric_trends.md`](./task_understandings/2026-06-20_factor_horizon_metric_trends.md)：因子研究多 horizon 勝率 / AUC 趨勢圖紀錄
- [`task_understandings/2026-06-20_readme_language_split.md`](./task_understandings/2026-06-20_readme_language_split.md)：GitHub README 英文預設入口與繁中指引拆分紀錄
- [`task_understandings/2026-06-23_phase2_visual_workbench.md`](./task_understandings/2026-06-23_phase2_visual_workbench.md)：Watchlist、Market heatmap、Smart Tuning Lite 第二階段視覺工作台紀錄
- [`task_understandings/2026-06-24_trade_vision_center.md`](./task_understandings/2026-06-24_trade_vision_center.md)：智能交易視覺中心 / Trade Vision Center 紀錄
- [`task_understandings/2026-06-24_next_day_order_planner.md`](./task_understandings/2026-06-24_next_day_order_planner.md)：隔日掛單計畫 / Next-Day Order Planner 紀錄
- [`task_understandings/2026-06-24_neural_ukf_momentum_plan.md`](./task_understandings/2026-06-24_neural_ukf_momentum_plan.md)：LSTM/Transformer + UKF 多時序動能模型 TODO / 架構規劃
- [`task_understandings/2026-06-24_swing_order_chart_ukf_plan.md`](./task_understandings/2026-06-24_swing_order_chart_ukf_plan.md)：隔日掛單 row 聯動 swing trading 技術圖、K 線型態與 UKF-style 動能測試補強
- [`task_understandings/2026-06-24_swing_smc_signal_overlays.md`](./task_understandings/2026-06-24_swing_smc_signal_overlays.md)：隔日掛單技術圖新增 FVG/IFVG、Swing High/Low、SFP、BOS/ChoCH 與市場結構 overlay
- [`task_understandings/2026-06-24_smartmoneyconcepts_adapter.md`](./task_understandings/2026-06-24_smartmoneyconcepts_adapter.md)：smartmoneyconcepts adapter；隔日掛單技術圖優先使用第三方 SMC engine 計算 FVG、Order Block、Liquidity、Swing、BOS/ChoCH，失敗時 fallback 內建規則
- [`task_understandings/2026-06-24_smc_confidence_mtf_order_urgency.md`](./task_understandings/2026-06-24_smc_confidence_mtf_order_urgency.md)：隔日掛單計畫加入 15m / 1h / 1d SMC 信心分數、買賣急迫度與優先處理熱力表
- [`task_understandings/2026-06-25_next_day_strategy_workbench.md`](./task_understandings/2026-06-25_next_day_strategy_workbench.md)：隔日策略工作台；可選股票、可承受停損幅度、預計持有天數、策略選擇、歷史驗證期間與最終掛單區間
- [`task_understandings/2026-06-25_ui_simplification_training_data.md`](./task_understandings/2026-06-25_ui_simplification_training_data.md)：研究與訓練資料中心；建立 daily training data、top correlated columns 與 UI 名詞簡化紀錄

## GitHub 文件入口
- `README.md`：預設英文 GitHub landing page
- `README-en.md`：英文獨立入口
- `README-zh.md`：繁體中文入口
- `docs/images/*.png`：README UI 預覽截圖

## 原始專案參考邏輯
1. `set_combine()`：組合手動清單 + 持股 + 權值股
2. `char_generator()`：技術特徵生成
3. `save_char()`：產生監督式資料集與歷史波動
4. `save_model()`：1D XGB / 2D GRU 雙軌訓練
5. `predict_result()`：風險調整排序與建議價位

## 新版切分策略
- `src/ai_stock/universe.py`
  - 專責候選股池
- `src/ai_stock/features.py`
  - 保留舊中文欄位技術特徵工程
- `src/ai_stock/selection.py`
  - 保留原始選股分數、建議價位、建議動作精神
- `src/ai_stock/data_sources.py`
  - OHLCV schema normalization、yfinance fallback、Futu OpenD adapter boundary；Docker 版 yfinance 會使用 `docker_runtime/market_cache` persistent disk cache，Docker 重啟後可沿用
- `src/ai_stock/analytics.py`
  - 技術 snapshot、股票間報酬相關性表格、正/負相關 peer pressure
- `src/ai_stock/attribution.py`
  - SHAP TreeExplainer / permutation fallback 歸因分析；Streamlit 端以按鈕觸發並保存在 session state，避免 sidebar 變動自動重算
- `src/ai_stock/factor_research.py`
  - sliding-window supervised factor research：過去 N 天技術因子 → 未來 1/3/5/10 天漲跌；輸出單一 horizon report 與多 horizon comparison，包括模型 metrics、horizon 勝率/AUC 趨勢、ticker × horizon heatmap matrix、SHAP/fallback importance、相關係數、分組勝率與 y heatmap
- `src/ai_stock/forecasting.py`
  - ARIMA / sklearn fallback 走勢估計、Kelly sizing、買賣停損參考、回撤風險欄位
- `src/ai_stock/pipeline.py`
  - 資料 → 技術分析 → 相關性 → 決策報表的程式化 pipeline
- `src/ai_stock/portfolio.py`
  - 本機私有持倉讀取與停損、停利、加碼限價、減碼 / 出清檢查規劃；支援 `my_stocks.json` 與既有拼字相容檔 `my_sotcks.json`，不會自動下單
- `src/ai_stock/order_planner.py`
  - 隔日掛單研究規劃：用持倉、決策報表與最近 20 日日內波動估算可成交買賣區、戰術停損、硬停損、觸及機率與建議單型；同時整合 15m / 1h / 1d SMC 訊號，輸出 SMC 信心分數、買進急迫度、賣出急迫度與優先處理分數；可合併隔日策略工作台結果，回寫最終來源/方向/策略/買賣停損停利區間；優先處理熱力表以 pandas Styler / `st.dataframe` 渲染避免 HTML row 原始碼外露；不連券商、不自動下單
- `src/ai_stock/order_strategy_workbench.py`
  - 隔日策略工作台：按鈕觸發比較布林、SMC、UKF 動能、KD/MACD、SHAP 因子代理策略；依選定股票、持有天數、風險耐受度與回測期間輸出策略勝率、Profit Factor、回撤、適配分數、BUY/SELL/WAIT 迫切度與最終買賣停損區間；並產生策略買賣點視覺化 payload，包含價格 K 線、非重疊交易狀態機買賣點、每筆交易垂直進出場線、綠/紅 PnL 連線與盈虧區塊、策略買賣區、可選 SMC overlay、權益曲線、回撤曲線與策略績效摘要；結果可回寫到隔日掛單計畫成為最終人工掛單區間；不連券商、不自動下單
- `src/ai_stock/training_data.py`
  - 分析結果數據 / Training Data：把每日 OHLCV、技術指標、SMC flags、UKF 動能、K 線型態與未來 N 天 target 合併成 model-ready DataFrame，並用相關性排序最有用欄位；作為未來三天趨勢 AI model 的資料基礎，不直接訓練模型
- `src/ai_stock/swing_order_chart.py`
  - 隔日掛單計畫下方 row 聯動技術圖：K 線、布林、RSI、MACD、成交量、K 線型態、FVG/IFVG 失衡區、Order Block、Liquidity、Swing High/Low、SFP 假突破、BOS/ChoCH、市場結構、掛單區、戰術/硬停損與 UKF-style 去噪動能
- `src/ai_stock/smc_adapter.py`
  - smartmoneyconcepts optional adapter；統一第三方 FVG、Order Block、Liquidity、Swing、BOS/CHoCH 輸出 schema，套件不可用或資料不足時 fallback 到內建市場結構 engine
- `src/ai_stock/visual_insights.py`
  - 今日機會雷達、Watchlist mini sparkline、市場熱力圖、Smart Tuning Lite、策略健檢卡、K 線買進 / 賣出 / 停損參考線與回測 B/S marker 疊圖
- `src/ai_stock/trade_vision.py`
  - 智能交易視覺中心核心：swing/BOS/ChoCH 市場結構、支撐壓力與供需區、premium/discount/equilibrium、Entry/SL/TP 交易計畫、MTF Matrix、Signal Score、AI Trade Narrative、進階 K 線圖與 Risk/Reward box
- `src/ai_stock/app.py`
  - Streamlit 互動 UI 與報表下載；yfinance 行情資料快取 1 小時，按「重新抓資料 / 更新分析」才清除記憶體、磁碟行情與下游分析快取；右上角語言選擇可切換繁中 / English / 日本語 / 한국어
- `src/ai_stock/i18n.py`
  - UI 多語言字典與 dataframe 欄位翻譯 helper
- `Dockerfile` / `docker-compose.yml` / `run.sh`
  - 容器化 Streamlit dashboard；`run.sh` 提供 up/down/down_up/restart/log/status/url/test 等快捷指令，並自動輸出 Local/LAN/Tailscale URL

## 目前決策
- 優先做「決策輔助 / 研究報表」，不是交易引擎
- 先用 portable API（yfinance / CSV）打通資料與 UI；Futu Python package 已納入 optional dependency
- 預測先用可解釋數學模型，不做深度學習或 LLM 直接預測
- 報表輸出需包含 actionable levels：buy / sell / stop-loss / Kelly fraction / action
