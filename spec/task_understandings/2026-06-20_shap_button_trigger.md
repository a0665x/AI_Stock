# SHAP button-trigger interaction

## 背景
使用者發現 sidebar 啟用 SHAP 後，只要 sidebar 參數變動就會造成 Streamlit rerun 並可能重算 SHAP，導致等待感明顯。

## 變更
- 移除 sidebar 的「啟用 SHAP 歸因計算」toggle。
- 在 `歸因分析` tab 內新增「執行 SHAP 歸因分析」按鈕。
- 按下按鈕時才呼叫 `_cached_attribution(prices, horizon)`。
- 結果保存到 `st.session_state.shap_attribution`。
- 用 `st.session_state.shap_signature` 記錄當次資料 / horizon signature。
- 如果 sidebar 參數改變，不會自動重算；若仍顯示舊歸因，UI 會提示結果來自上一次，需要按鈕手動更新。

## 驗證
- 新增測試：`test_streamlit_shap_analysis_is_button_triggered_not_sidebar_toggle`
- 本機 `.venv`：`pytest -q` → 9 passed
- 本機 `.venv`：`python -m compileall src` → pass
- Docker image rebuild → pass
- Docker container pytest → 9 passed
- Docker Compose restart → healthy
- Health endpoint：`http://127.0.0.1:8507/_stcore/health` → ok
- Browser check：sidebar 已無 SHAP toggle；`歸因分析` tab 顯示「執行 SHAP 歸因分析」按鈕。
