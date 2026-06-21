# 2026-06-20 tutor_guide 與決策解釋

## 任務
使用者希望為初級使用者新增 `./tutor_guide.md`，說明：
- UI 操作步驟
- 技術名詞與指標
- 因子多寡的意義
- 回測、勝率、AUC、baseline、SHAP/y heat 的解讀
- 如何把 UI 趨勢轉成買賣觀察
- 確認 Kelly 常為 0.0% 與決策常為「等待確認」是否正常

## 實際確認
以 Docker 服務內目前 AAPL / MSFT / NVDA、1y 日 K、決策 horizon=5 實跑 `build_decision_report()`：
- 三檔皆為 `HOLD_WAIT`
- Kelly fraction 皆為 0.0
- 預估報酬約 -0.13% 到 +0.23%，但 risk unit 約 3.3% 到 5.8%

結論：Kelly 0.0% 與「等待確認」是目前公式下的正常保守結果。原因是預估報酬遠小於近期風險單位與回撤調整門檻。

## 文件新增
新增：
- `tutor_guide.md`

內容包含：
- 新手操作流程
- 決策報表欄位解讀
- Kelly 0.0% 與 HOLD_WAIT 原因
- K 線、SMA/EMA、RSI、MACD、KD、布林、ATR、MFI、OBV、回撤、支撐壓力
- 因子研究、horizon、因子多寡、SHAP、分組勝率、y heat
- 回測勝率、最大回撤、停損命中率、累積報酬
- 股票關係與正/負相關
- 新手買賣觀察流程與案例

## 文件索引更新
同步更新：
- `README.md`
- `spec/PROJECT_MAP.md`
- `spec/map.md`
- `spec/agent.md`
