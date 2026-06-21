# 2026-06-19 技術指標、SHAP 歸因與回撤/關係壓力改版

## 使用者回饋
使用者指出目前報表缺少更完整的 RSI 等技術指標，也沒有看到 SHAP / 歸因分析圖表；同時希望回撤與決策可以參照正相關、負相關標的的影響。

## 本次改動
- `src/ai_stock/analytics.py`
  - 擴充技術指標：EMA20/60、布林通道位置、ATR%、KD、MFI、OBV、距60日高點回撤、60日最大回撤、20日支撐/壓力。
  - 新增 `compute_relationship_pressure()`，將股票間正/負相關與近5日 peer return 合成輔助壓力訊號。
- `src/ai_stock/attribution.py`
  - 新增未來報酬歸因模型。
  - 優先使用 `shap.TreeExplainer`；若環境或套件失敗，自動 fallback 到 signed permutation importance。
- `src/ai_stock/forecasting.py`
  - 決策報表納入 risk unit、ATR%、最大回撤、距高點回撤、關係壓力、RSI/MFI/布林位置。
  - 額外輸出 `relationship_adjusted_return_pct`：模型預估報酬 + 25% 關係壓力，排序採用這個保守調整後欄位。
  - 買賣停損價改用 ATR/波動與支撐壓力做更保守的 risk unit。
- `src/ai_stock/pipeline.py`
  - 輸出 `relationship_pressure` 與 `attribution_report`。
- `src/ai_stock/app.py`
  - 新增「歸因分析」頁籤，顯示 SHAP / fallback 歸因水平長條圖與表格。
  - 決策報表與資料明細加入新增風險/技術欄位。
- `pyproject.toml`
  - 新增 `shap>=0.45` dependency。

## 驗證
- `uv pip install -e '.[dev,futu]'` 成功。
- `pytest -q`：6 passed。
- `python -m compileall src`：通過。
- pipeline smoke test：
  - prices `(753, 7)`
  - technical_snapshot `(3, 23)`
  - correlations `(3, 4)`
  - relationship_pressure `(3, 5)`
  - decision_report `(3, 21)`
  - attribution_report `(24, 7)`
  - 歸因方法實測為 `shap_tree_explainer`。
- Streamlit：`http://127.0.0.1:8507/_stcore/health` 回傳 `200 ok`。
- 瀏覽器實際打開「歸因分析」頁籤，確認顯示 SHAP 長條圖與表格。

## 注意
- SHAP / permutation importance 都是統計模型歸因，不是單一因果證明。
- 關係壓力是用相關性與近5日 peer return 估計的輔助訊號，適合做風險提示，不應單獨當買賣依據。
