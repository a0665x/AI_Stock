# project_herness

## 專案名稱
AI_Stock

## 現況
已建立第一版可跑的股票決策輔助骨架：
- 可用 yfinance / CSV 取得或匯入歷史 OHLCV
- 可在 Streamlit 看到 K 線、SMA、技術 snapshot
- 可產出多股票報酬相關性表格
- 可產出 ARIMA / sklearn fallback 的簡單走勢估計與 Kelly sizing，並在決策報表解釋 Kelly 0.0% / 等待確認原因
- 可輸出買價 / 賣價 / 停損 / action 決策報表
- 可在 Streamlit 回測頁籤看到 walk-forward 勝率、最大回撤、停損命中率、累積報酬、逐筆交易與累積報酬曲線
- 可在 Streamlit 因子研究頁籤比較未來 1/3/5/10 天漲跌模型，並查看 horizon 趨勢與每檔股票 × horizon 表現熱力圖
- Web UI 右上角語言切換支援繁中 / English / 日本語 / 한국어

## 近期任務重點
1. 先用 yfinance/CSV 驗證整體資料 → UI → 報表閉環
2. 若要 Futu 即時行情，需決定 OpenD 要跑在哪台非 ARM 或遠端主機
3. 擴充台股資料來源與更完整的技術指標 / 回測統計
4. 補更完整的 UI 篩選、報表匯出與 watchlist 管理

## 風險
- ARM 主機可安裝 Python `futu-api`，但不能直接執行 OpenD
- yfinance 對台股/即時性與穩定性有限，只適合第一版打通架構
- ARIMA / sklearn fallback 是 explainable baseline，不應被包裝成保證預測
- 自動下單與資產帳務仍不在目前邊界
