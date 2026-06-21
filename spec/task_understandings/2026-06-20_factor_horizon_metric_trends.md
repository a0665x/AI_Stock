# 2026-06-20 Factor horizon metric trends

## 需求
使用者希望在因子研究頁籤中加入不同 horizon 的勝率與 AUC 趨勢圖，方便比較未來 1/3/5/10 天哪個預測視窗比較有研究價值。

## 實作
- `src/ai_stock/factor_research.py`
  - 新增 `build_horizon_metric_trends(summary)`。
  - 將 multi-horizon summary 依 `horizon` 聚合，輸出平均 `accuracy`、平均 `auc`、平均 `baseline_up_rate`、總樣本數與股票數。
- `src/ai_stock/app.py`
  - 新增 `_build_factor_horizon_trend_chart(summary)`。
  - 因子研究跑完後，在「多 horizon 模型表現比較」前顯示「多 horizon 勝率與 AUC 趨勢」。
  - 趨勢圖同時顯示：測試勝率 / Accuracy、AUC、歷史上漲率 baseline，並加 50% 參考線。
  - 下方同步顯示聚合後的趨勢表。
- `tests/test_factor_research.py`
  - 新增 horizon metric trends 聚合測試。
  - 更新 Streamlit source test，確認頁籤包含趨勢圖文案與 helper。

## 驗證
- 本機：`pytest -q` → 16 passed。
- 本機 compile：`python -m compileall src` → passed。
- 本機 smoke：AAPL/MSFT/NVDA、1y、horizons 1/3/5/10，trend rows = 4。
- Docker：`./run.sh rebuild && ./run.sh test` → 16 passed。
- Docker UI：`./run.sh down_up` 後 health check 回 `ok`。
- Docker container smoke：`build_horizon_metric_trends()` 回傳 horizons `[1, 3, 5, 10]` 與欄位 `horizon/accuracy/auc/baseline_up_rate/sample_count/ticker_count`。

## 注意
因子研究仍然按鈕觸發，不在頁面載入時自動訓練多 horizon SHAP，以避免 ARM 主機 UI 卡住。
