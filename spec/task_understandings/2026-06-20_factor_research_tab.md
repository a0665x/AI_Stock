# 2026-06-20 因子研究頁籤

## 需求
使用 sliding window 將過去 N 天 K 線、KD、MACD、RSI、量能、波動與回撤等技術因子作為 X，將未來 horizon 天漲跌作為 y，分析哪些因子對未來漲跌最有影響，並解釋相對貢獻。

## 實作
- 新增 `src/ai_stock/factor_research.py`
  - `build_sliding_window_dataset()`：以每檔股票逐日滑窗建樣本。
  - `build_factor_research_report()`：訓練 Logistic / RandomForest / GradientBoosting 分類模型。
  - 產出模型 summary、SHAP/fallback importance、Spearman/Pearson 相關係數、分組勝率、y heatmap。
- 新增 `tests/test_factor_research.py`
  - 驗證 sliding-window X/y 欄位、目標日、feature lag、模型輸出與 UI 按鈕觸發。
- 更新 `src/ai_stock/app.py`
  - 新增「因子研究」頁籤。
  - 側邊欄新增因子輸入天數、因子預測天數、漲跌分類門檻、因子模型。
  - 因子研究採按鈕觸發，避免 sidebar 變動就重算。
  - 顯示模型準確率/AUC、重要因子圖、相關係數、分組勝率 heatmap、y heatmap、CSV 下載。
- 更新 `src/ai_stock/pipeline.py`
  - 程式化 pipeline 增加 `factor_research_report`。
- Docker 調整
  - Compose 改用 host UID/GID 執行容器。
  - pytest cache 改至 `/tmp/pytest_cache`。
  - Docker persistent cache volume 改為 `./docker_runtime:/app/runtime`，避免舊版 root-owned `./runtime` 導致 permission denied。

## 驗證
- 本機 `.venv`：`pytest -q && python -m compileall src` 通過。
- Docker：`./run.sh test` 通過，結果 `14 passed`。
- Docker smoke：AAPL/MSFT/NVDA 一年資料實跑因子研究：
  - prices: `(753, 7)`
  - factor_summary: `(3, 12)`
  - factor_importance: `(30, 7)`
  - factor_correlations: `(30, 6)`
  - factor_grouped_win_rates: `(96, 7)`
  - factor_y_heatmap: `(732, 6)`
  - method: `shap_explainer`
- Docker Streamlit health endpoint：`ok`。
- Browser：已看到「因子研究」頁籤與「執行因子研究」按鈕；瀏覽器自動化工具 click 未能觸發 Streamlit button rerun，但容器內 smoke 已確認同一函式可正常完成。

## 注意
- SHAP/重要度解釋的是模型對歷史樣本的歸因，不代表因果證明。
- train/test 使用時間序切分，不使用 random split，以降低時間序列資料洩漏。
- 若某檔資料樣本不足或 target 只有單一類別，會輸出狀態而非硬訓練。
