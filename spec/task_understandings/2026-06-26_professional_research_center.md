# 2026-06-26 Professional Research Center

## 背景
使用者希望「研究中心」更像 TradingView + 線上回測平台，而不是散落的報表頁籤。重點不是新增黑箱模型，而是讓研究流程更專業、可解釋、可下載、可作為未來 AI model 的資料基礎。

## 本次變更
- 將研究中心二級頁籤重構為：
  - `總覽`：Research Radar，快速掃描研究股票數、資料列、回測交易數與最佳 Profit Factor。
  - `策略實驗室`：Strategy Tester，承接 walk-forward 回測、策略比較與 Smart Tuning Lite。
  - `因子排行`：Factor Explorer + Factor Contribution，承接多預測天數因子研究與 SHAP/fallback 歸因。
  - `訓練資料`：Training Data Studio，產生每日 OHLCV、技術指標、SMC、信號與未來報酬 target。
  - `風險與關聯`：Risk & Correlation Monitor，檢查股票間報酬相關性與集中風險。
- 新增「研究中心怎麼使用？」expander，提供 TradingView / backtest platform 式操作流程。
- 新增顏色與指標解釋：
  - 綠色：表現或關聯較強。
  - 黃色：中性待確認。
  - 紅色：風險、回撤或負向壓力較高。
  - AUC 接近 50%：接近隨機。
  - Profit Factor > 1：獲利交易金額大於虧損交易金額。
  - 最大回撤：策略從高點跌下來的最大幅度。
- 將昂貴研究維持按鈕觸發：Research Radar、Smart Tuning、因子排行、Training Data 都不在頁面載入時自動重跑。

## 測試
新增：
- `tests/test_professional_research_center_ui_source.py`

本機驗證：
- `pytest -q` → 100 passed

## 後續建議
- 在 Research Radar 補更完整的視覺卡片：樣本不足、Profit Factor 過低、最大回撤過高、同向持倉過度集中。
- 將 Factor Explorer 的 top features 與 Training Data Studio 的欄位字典做更明確的互相跳轉。
- 未來訓練三日趨勢模型時，必須保留 `target_available_Nd`，避免最後 N 天未知 target 被誤用。
