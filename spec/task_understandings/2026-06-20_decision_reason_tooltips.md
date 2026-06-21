# 2026-06-20 決策報表原因提示

## 使用者需求
使用者希望在決策報表旁邊直接看到 Kelly 0.0% 和「等待確認」的原因提示，避免新手只看到結果但不知道底層理由。

## 實作
- `src/ai_stock/forecasting.py`
  - 新增 `_kelly_reason()`：根據預估報酬、風險單位、半 Kelly 結果輸出中文原因。
  - 新增 `_action_reason()`：根據 BUY_WATCH / HOLD_WAIT / SELL_OR_AVOID 與決策門檻輸出中文原因。
  - `forecast_one_ticker()` 回傳 `kelly_reason`、`action_reason` 欄位。
- `src/ai_stock/app.py`
  - 決策報表新增中文欄位 `決策原因`、`Kelly 原因`。
  - 新增 `Kelly / 決策原因怎麼看？` 展開說明，解釋 Kelly 0.0% 與等待確認的常見原因。

## 解釋邏輯
- Kelly 0.0% 通常代表預估報酬相對於風險單位太小，保守勝率假設下沒有足夠下注優勢。
- 等待確認代表預估報酬仍在 ±決策門檻內，模型優勢尚未明顯大過近期波動與回撤風險。

## 驗證
- 本機：`pytest -q && python -m compileall src` → 19 passed。
- Docker：`./run.sh rebuild && ./run.sh test` → 19 passed。
- Docker UI：`./run.sh down_up` 後 health check `/_stcore/health` 回傳 ok。
- 瀏覽器實測：決策報表頁顯示 `Kelly / 決策原因怎麼看？` 展開區塊，內容含 Kelly 0.0% 說明。
