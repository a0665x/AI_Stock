# 2026-05-25 AI_Stock Bootstrap

## 任務
使用者希望參考舊版 `v1_0_5` 交易引擎代碼，重新建立一個新的 `AI_Stock` 專案，先聚焦在「選股機制」。

## 已完成
- 讀取 notebook 流程與 `cstock.py` 關鍵函式
- 確認最可重用的內容是：
  - `set_combine()` 候選股池組合
  - `char_generator()` 特徵工程思想
  - `predict_result()` 的風險調整排序與建議價位公式
- 建立新專案骨架與 spec 文件
- 以 pandas 重寫第一版模組：`universe.py`、`features.py`、`selection.py`

## 目前結論
這個新專案應該先定義成 **stock selection engine**，而不是完整 trading engine。

## 建議下一步
1. 定義輸入資料 schema
2. 決定第一版是否先不用模型，只用規則與因子排序驗證
3. 補 `pipeline.py` 與測試
