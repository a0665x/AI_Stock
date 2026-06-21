# 2026-06-20 yfinance 快取與手動刷新

## 背景
使用者反映每次重整或 sidebar 變動時等待 yfinance 抓資料太久，希望行情資料也快取，避免不必要的網路等待。

## 變更
- `src/ai_stock/app.py`
  - 新增 `YFINANCE_CACHE_TTL_SECONDS = 60 * 60`。
  - `_load_yf()` 改為 `@st.cache_data(ttl=YFINANCE_CACHE_TTL_SECONDS, show_spinner=False)`。
  - 新增 `_clear_cached_market_data()`，會清除：
    - yfinance 行情快取
    - technical snapshot 快取
    - correlations 快取
    - decision report 快取
    - attribution 快取
    - backtest 快取
    - scenario comparison 快取
  - sidebar 顯示「行情資料已快取 1 小時；一般重新整理頁面不會重抓 yfinance」。
  - 「重新抓資料 / 更新分析」按鈕現在會真的清除行情與分析快取，並清除舊 SHAP session state。

## 驗證
- 本機 `.venv`：`pytest -q` → 10 passed
- 本機 compile：`python -m compileall src` → 通過
- Docker build：成功
- Docker container：`pytest -q` → 10 passed
- Docker Compose restart：成功
- health endpoint：`http://127.0.0.1:8507/_stcore/health` → ok
- 瀏覽器確認：sidebar 已出現 yfinance 快取提示。

## 注意
Streamlit cache 是程序內 cache；容器重啟後會重新抓資料。若未來需要跨重啟持久快取，可再加入磁碟層快取，例如 parquet/http cache volume。
