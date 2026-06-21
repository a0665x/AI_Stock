# 2026-06-19 Streamlit UI Readability Revamp

## 使用者需求
使用者希望檢視目前 Streamlit UI 哪些功能不夠直覺，並直接改版。

## 觀察到的不直覺點
- 首屏先顯示 K 線，使用者最關心的買進 / 賣出 / 停損 / Kelly 決策藏在下方。
- 表格欄位多為工程命名，例如 `expected_return_pct`、`suggested_buy_price`、`action`。
- action code 使用英文代碼，沒有中文解釋與決策語境。
- 側邊欄設定未明確引導「選資料 → 調參數 → 看結果」流程。
- 價格圖、相關性、技術指標與原始資料全部線性往下排，資訊層級不清楚。

## 本次修改
- 將 app 標題與說明中文化：`AI Stock 決策儀表板`。
- 首屏改為決策摘要：優先觀察標的、預估報酬、買進參考、停損參考、賣出參考、Kelly 倉位。
- 把 `BUY_WATCH` / `HOLD_WAIT` / `SELL_OR_AVOID` 轉成中文決策標籤與 emoji badge。
- 增加「怎麼讀這份報表？」展開說明，解釋買進價、賣出價、停損價、Kelly 的含意。
- 使用 tabs 重整資訊架構：
  - 決策報表
  - 價格圖表
  - 股票關係
  - 資料明細
- 側邊欄改為流程式設定文字，並支援 textarea 代號輸入。
- K 線圖加入成交量 toggle、hover unified、圖例水平排列。
- 股票相關性新增 heatmap，保留原 pairwise table。
- 技術 snapshot 與 decision report 中文欄位化並設定數字格式。

## 驗證
- `python -m compileall src` 通過。
- `pytest -q` 通過：4 passed。
- Streamlit health endpoint 回傳 200 OK。
- 瀏覽器載入 `http://127.0.0.1:8507` 成功顯示新版 UI。

## 後續可改進
- 針對不同市場（美股 / 台股）做預設代號與貨幣格式切換。
- 對 action 加上更細的原因欄位，例如趨勢、RSI、MACD、相關性風險。
- 增加簡單回測頁籤，讓「前幾天照報表買賣」的勝率與回撤一眼可見。
