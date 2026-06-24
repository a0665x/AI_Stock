# 2026-06-24 Next-Day Order Planner

## 背景
使用者觀察到既有 `suggested_buy_price` / `suggested_sell_price` / `stop_loss_price` 多半是策略級價位，距離現價常常超過最近日內波動，隔日限價單不一定有機會成交。

## 決策
新增「隔日掛單計畫 / Next-Day Order Planner」頁籤，保留既有「持倉下單計畫」作為中期/策略級控風險頁面。新頁籤只做研究輔助，不連接券商、不自動下單。

## 核心模組
新增 `src/ai_stock/order_planner.py`：

- `estimate_touch_probability_label(...)`：用目標價距離現價相對於最近 20 日日內波動與 80 分位日內波動，輸出 HIGH / MEDIUM / LOW_MEDIUM / LOW_STRATEGY_LEVEL。
- `build_next_day_order_plan(...)`：從 OHLCV、決策報表、持倉資料產生隔日買進區、隔日賣出區、戰術停損、硬停損、觸及機率、建議單型與原因。

## 頁面行為
頁籤放在「持倉下單計畫」後面。顯示：

- 可規劃標的數
- 高/中買進成交機率數
- 高/中賣出成交機率數
- 保護性停損單數
- 隔日掛單計畫表格
- CSV download button
- 使用說明 expander

## 價位邏輯

- 隔日買進區：`current_price * (1 - median_intraday_range_20d * 0.35~0.65)`，並用策略級買進價做邊界參考。
- 隔日賣出區：`current_price * (1 + median_intraday_range_20d * 0.35~0.65)`，並用策略級賣出價做邊界參考。
- 戰術停損：取有效前低與 `current_price - 0.7 * median_intraday_range_20d` 中較保守者；若前低高於現價則忽略，避免停損跑到現價上方。
- 硬停損：沿用決策報表 stop loss；若資料異常高於現價，改用波動度回推並壓在現價下方。

## 驗證

- 新增 `tests/test_order_planner.py`
- 新增 `tests/test_next_day_order_ui_source.py`
- 本機：`51 passed`
- Docker：`51 passed`
- 實際持倉 smoke：12 檔產生計畫，戰術停損皆低於現價
- Streamlit health：`ok`
- 瀏覽器 DOM 確認：頁簽「隔日掛單計畫」、隔日買進區、戰術停損、下載隔日掛單計畫 CSV 均出現
