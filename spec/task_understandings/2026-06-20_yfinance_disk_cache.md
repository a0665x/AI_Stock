# 2026-06-20 yfinance persistent disk cache

## 背景
使用者希望 Docker 重啟後也不要立刻重新抓 yfinance。先前只有 Streamlit `st.cache_data` 記憶體快取，容器重啟會失效。

## 實作
- `src/ai_stock/data_sources.py`
  - 新增 `YFINANCE_DISK_CACHE_TTL_SECONDS = 3600`
  - 新增 `_download_yfinance_history()`，負責真正打 yfinance
  - `fetch_yfinance_history()` 改為先查 persistent disk cache，miss 或過期才下載
  - cache key 由 provider / tickers / period / interval / schema 產生 sha256 digest
  - cache 檔格式為 pandas pickle：`yf_<tickers>_<period>_<interval>_<digest>.pkl`
  - 新增 `clear_yfinance_disk_cache()`，供 UI 手動刷新同步刪除磁碟快取
- `docker-compose.yml`
  - 設定 `AI_STOCK_MARKET_CACHE_DIR=/app/runtime/market_cache`
  - 既有 `./runtime:/app/runtime` volume 讓 cache 在容器重啟後保留
- `src/ai_stock/app.py`
  - `_clear_cached_market_data()` 現在同時清 `st.cache_data` 與 disk cache
  - sidebar 文案改成明確說明 Docker 重啟後仍會優先讀 `runtime/market_cache`

## 驗證
- 新增測試：`test_yfinance_history_uses_persistent_disk_cache`
  - 第一次 fetch 會呼叫 fake downloader
  - 第二次同 key fetch 直接讀 `.pkl`，downloader call count 不增加
  - `clear_yfinance_disk_cache()` 後再次 fetch 會重新呼叫 downloader
- 本機：`pytest -q` → 11 passed
- 本機：`python -m compileall src` → 通過
- Docker build → 成功
- Docker container pytest → 11 passed
- 實際容器 fetch AAPL/MSFT/NVDA 1y/1d：產生 `runtime/market_cache/yf_AAPL_MSFT_NVDA_1y_1d_94081d7253c06148def4.pkl`
- Docker restart 後 cache file 仍存在
- restart 後第二次 fetch elapsed_seconds 約 0.015 秒，代表命中磁碟快取而非重抓 yfinance
- Streamlit health → healthy
- 瀏覽器 UI 已顯示磁碟快取提示並正常載入

## 注意
- TTL 仍為 1 小時；超過 TTL 會重新抓 yfinance 並覆蓋 cache。
- 如果要強制更新行情，用 UI「重新抓資料 / 更新分析」，或刪除 `runtime/market_cache/yf_*.pkl`。
