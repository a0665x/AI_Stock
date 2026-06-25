# 2026-06-25 UI simplification and training data center

## User concern
- 「等待確認」看起來像沒有策略決策，和隔日策略工作台已有回測結果互相矛盾。
- `horizon` 這種術語不直覺。
- 回測、因子研究、歸因分析、原始資料分散，使用者希望更像單一研究中心。
- 使用者最終想要可供 AI model 訓練的完整 daily feature table，用來預估未來三天趨勢。

## Clarification
- 今日雷達 / 決策總覽的「等待確認」不是 Kelly，也不是沒有模型；它來自 forecasting decision report：預估報酬未大過近期波動、ATR、回撤風險門檻。
- 隔日策略工作台是按鈕觸發的策略適配回測，已可回寫隔日掛單計畫，但仍需要在 UI 上逐步統一語意。

## Implemented
- 新增 `src/ai_stock/training_data.py`。
- 新增 `build_training_dataset()`：每檔股票每日一列，包含 OHLCV、技術指標、UKF 動能、K 線型態、SMC FVG/OB/Liquidity/Swing/BOS/ChoCH flags，以及 `forward_return_3d` / `target_up_3d` / `target_close_3d` / `target_available_3d`。
- 新增 `compute_top_training_features()`：用 Pearson/Spearman 相關性排序最有關聯的欄位，SMC 欄位也會被納入排序。
- 將 `資料明細` 頁籤改成 `研究與訓練資料`，再整併到 `研究中心` 二級頁籤。
- 將 11 個主頁籤收斂為 5 個主流程：`今日決策`、`交易計畫`、`圖表分析`、`策略驗證`、`研究中心`。
- `研究中心` 內含 `回測 / Smart Tuning`、`因子研究`、`SHAP 歸因`、`股票關係`、`訓練資料` 二級頁籤。
- 每個主頁頂部新增「本頁回答」說明，讓使用者知道該頁目的與下一步。
- `今日決策` 新增 TradingView 式行動清單，顯示最終方向、優先分數、買賣區、最終策略與下一步。
- 新增顯示層 `STRATEGY_SIDE_LABELS_ZH`，把 `BUY` / `SELL` / `WAIT` / `HOLD_WAIT` 轉成「買進 / 加碼」、「賣出 / 減碼 / 保護」、「等待確認」。
- 頁面加入簡易名詞說明：等待確認、預測幾天後、Training Data。
- 頁面支援選擇未來 1/3/5/10 天 target，預設 3 天；按下 `產生 Training Data` 才開始計算，避免首頁載入變慢。
- 頁面顯示 top N relevant columns、完整 daily training data、Snapshot、原始價格資料與 CSV 下載。
- 新增欄位字典與提醒：這是資料集，不是已訓練模型；最後 N 天 `target_available=0` 不應拿來訓練 y。
- UI 文案開始將 `horizon` 替換成「預測幾天後 / 預測天數」。
- 新增 `spec/ui_simplification_training_data_goal.md` 作為 /goal 式持續優化目標。

## Tests
- `tests/test_training_data.py`
- `tests/test_training_data_ui_source.py`
- `tests/test_simplified_navigation_ui_source.py`
- `tests/test_dashboard_action_board_ui_source.py`

## Next steps
- 進一步把 `交易計畫` 內的持倉計畫與隔日掛單呈現成更像 Order Blotter 的單一流程。
- 在 `圖表分析` 補更完整的 TradingView-like 控制列（週期、指標組合、圖層 presets）。
- 用 subagent/browser user-view QA 持續檢查：哪檔股票、買賣方向、掛單區、為什麼、歷史證據是否一眼可懂。
