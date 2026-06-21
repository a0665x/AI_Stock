# AI_Stock Project Map

## 專案定位
`AI_Stock` 是從 `CH4_CStock_v1_0_5` 提煉出來的新版股票決策輔助專案。

目前定位從「單純選股骨架」擴展為：
- 歷史價格 / K 線圖表與互動式 UI
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
