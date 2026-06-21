# 2026-06-20 因子研究：每檔股票 × horizon 表現熱力圖

## 需求
在既有多 horizon 因子研究頁籤中，新增一張熱力圖，讓使用者能一眼比較每檔股票在未來 1/3/5/10 天 horizon 下的表現。

## 實作
- `src/ai_stock/factor_research.py`
  - 新增 `build_ticker_horizon_metric_matrix(summary, metric)`。
  - 將 multi-horizon summary pivot 成 ticker × horizon matrix。
  - 支援 `accuracy`、`auc`、`baseline_up_rate` 等 numeric metric。
- `src/ai_stock/app.py`
  - 新增 `_build_factor_ticker_horizon_heatmap()`。
  - 在「因子研究」頁籤中，於整體「多 horizon 勝率與 AUC 趨勢」後新增「每檔股票 × horizon 表現熱力圖」。
  - 使用 `selectbox` 讓使用者切換熱力圖指標：測試勝率 / Accuracy、AUC、歷史上漲率 baseline。

## 驗證
- TDD 新增 `test_ticker_horizon_metric_matrix_pivots_each_stock_by_future_window_for_heatmaps`。
- 本機：`pytest tests/test_factor_research.py -q` → 6 passed。
- 本機：`python -m compileall src` → pass。
- 本機全測：`pytest -q` → 17 passed。
- Docker rebuild + container test：`./run.sh rebuild && ./run.sh test` → 17 passed。
- Docker UI health：`http://127.0.0.1:8507/_stcore/health` → ok。
- Docker container smoke：AAPL/MSFT/NVDA、1y、horizons 1/3/5/10 可產出 Accuracy/AUC matrix。

## 注意
熱力圖資料來自「執行多 horizon 因子研究」按鈕後保存的 session state；沒有按下前不會自動訓練模型，以避免 ARM 主機 UI 初始載入過慢。
