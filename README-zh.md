# AI_Stock

<p align="center">
  <a href="README.md">English</a> |
  <a href="README-zh.md"><strong>繁體中文</strong></a>
</p>

AI_Stock 是一個股票研究與決策輔助儀表板。它不做自動下單，也不把模型輸出包裝成投資建議；目標是讓使用者用同一個 Web UI 觀察價格、技術指標、回測、因子研究、SHAP 歸因與股票間關係。

## 主要功能

- 多語言 Web UI：右上角可切換繁體中文 / English / 日本語 / 한국어
- 歷史價格與 K 線互動圖表，並疊加買進 / 賣出 / 停損參考線與回測 B/S 進出場標記
- 今日機會雷達：用卡片濃縮每檔股票的決策狀態、Kelly、回測勝率、報酬、買進價與停損價
- 左側 Watchlist + mini sparkline：每檔股票顯示最新收盤、1日漲跌、決策狀態與迷你走勢
- 市場熱力圖：用格子大小呈現活躍度、顏色呈現近期報酬，快速找出最熱或最弱的觀察標的
- Smart Tuning Lite：按鈕觸發掃描持有天數、出場規則與風險寬度，依報酬、勝率、Profit Factor、回撤與停損率排名
- 智能交易視覺中心 / Trade Vision Center：進階 K 線交易研究台，整合市場結構、BOS/ChoCH、支撐壓力與供需區、Entry/SL/TP、風險報酬區塊、MTF Matrix、Signal Score 與 AI Trade Narrative；只做研究輔助，不自動下單
- 隔日掛單計畫 / Next-Day Order Planner：把策略級買進 / 賣出 / 停損參考價轉成更接近隔日可成交波動範圍的買賣區、戰術停損、硬停損與觸及機率標籤；整合 15m / 1h / 1d SMC 訊號產生 SMC 信心分數、買進急迫度、賣出急迫度與綠/紅/藍優先處理熱力表；熱力表使用 pandas Styler / Streamlit dataframe 渲染，避免 `<tr>` / `<td>` 原始碼外露；並在表格下方提供 row 聯動的 swing trading 技術圖，含 K 線十字游標、布林、RSI、MACD、成交量、K 線型態、掛單區、smartmoneyconcepts 優先 / 內建 fallback 的 FVG/IFVG、Order Block、Liquidity、Swing High/Low、BOS/ChoCH、圖例 icon 說明與 UKF-style 去噪動能；只做研究輔助，不自動下單
- 策略健檢卡：把樣本數、最大回撤、Profit Factor、勝率、累積報酬與 Kelly 狀態轉成新手可讀警訊
- 技術指標 snapshot：SMA、EMA、RSI、MACD、KD、MFI、ATR、布林位置、量能比、波動度、回撤、支撐壓力
- 決策報表：模型預估報酬、關係調整後報酬、買進參考、賣出參考、停損參考、Kelly 倉位、決策原因、Kelly 0.0% 原因
- Walk-forward 回測：勝率、最大回撤、停損命中率、累積報酬、逐筆交易、不同持有天數與出場規則比較
- 因子研究：用 sliding window 將過去 N 天 K 線 / KD / MACD / RSI / 量能 / 回撤等因子作為 X，將未來 1/3/5/10 天漲跌作為 y，比較各 horizon 的 Accuracy、AUC、baseline、ticker × horizon 熱力圖、SHAP/fallback 重要度、相關係數、分組勝率與 y heatmap
- SHAP / fallback 歸因分析：按鈕觸發，避免頁面載入時自動重算
- 多股票報酬相關性與正 / 反相關壓力分析
- yfinance / CSV 資料來源；Docker 版會把 yfinance 快取保存在 docker_runtime/market_cache
- futu-api Python package 可安裝；但 Futu OpenD 需外部可執行 OpenD 的主機或遠端 OpenD 服務

## UI 預覽

下面截圖展示英文介面的決策報表、K 線圖、回測、股票關係與因子研究。這段使用 HTML + inline CSS 做橫向捲動；若某些平台過濾 CSS，圖片仍會正常顯示，只是可能退化成直向排列。

<div style="display:flex; overflow-x:auto; gap:16px; padding:8px 0 16px 0; scroll-snap-type:x mandatory;">
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-decision.png" alt="AI Stock decision report dashboard" width="760">
    <figcaption>決策報表：買進 / 賣出 / 停損參考、關係調整後報酬與 Kelly 倉位。</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-price.png" alt="AI Stock candlestick and price chart" width="760">
    <figcaption>價格圖表：K 線趨勢、移動平均與量能背景。</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-backtest.png" alt="AI Stock walk-forward backtest" width="760">
    <figcaption>Walk-forward 回測：勝率、回撤、停損命中率與累積報酬曲線。</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-relationships.png" alt="AI Stock stock relationship heatmap" width="760">
    <figcaption>股票關係：報酬相關性熱力圖與正 / 反相關壓力。</figcaption>
  </figure>
  <figure style="flex:0 0 760px; margin:0; scroll-snap-align:start;">
    <img src="docs/images/dashboard-factor.png" alt="AI Stock factor research dashboard" width="760">
    <figcaption>因子研究：多 horizon Accuracy/AUC、ticker × horizon 熱力圖與因子歸因。</figcaption>
  </figure>
</div>

## 專案結構

- src/ai_stock/：股票分析核心模組與 Streamlit app
- tests/：pytest 行為測試
- spec/：專案理解文件、任務紀錄與新手教學
- spec/tutor_guide.md：給初級使用者的完整教學，包含 UI 操作、技術名詞、Kelly、等待確認、回測、因子研究與買賣觀察案例
- Dockerfile / docker-compose.yml / run.sh：Docker Compose 一鍵啟動與管理入口

## 快速啟動：Docker Compose

建議一般使用者用 Docker 啟動。

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
./run.sh --help
./run.sh up
./run.sh status
```

啟動後打開 run.sh status 顯示的網址，例如：

```text
http://127.0.0.1:8507
```

如果主機已登入 Tailscale，run.sh status / run.sh url 也會自動列出 Tailscale MagicDNS 與 Tailscale IP URL。

常用快捷指令：

```bash
./run.sh up          # build + 背景啟動
./run.sh down        # 停止並移除 container
./run.sh down_up     # down 後重建啟動
./run.sh restart     # down_up alias
./run.sh log         # 追蹤 logs
./run.sh logs        # log alias
./run.sh status      # compose ps + Local/LAN/Tailscale URLs
./run.sh url         # 只列出 URLs
./run.sh test        # 在 container 內跑 pytest
./run.sh shell       # 進入 container shell
```

若尚未設定可執行權限，也可用：

```bash
bash run.sh up
```

## UI 基本操作

1. 右上角選擇語言：繁體中文 / English / 日本語 / 한국어
2. 左側選資料來源：yfinance 或 CSV
3. 輸入股票代號，例如 AAPL, MSFT, NVDA
4. 選歷史區間與 K 線週期；新手建議先用 1y + 1d
5. 先看「決策報表」：買進參考、賣出參考、停損參考、Kelly 倉位、等待確認原因
6. 打開「智能交易視覺中心」查看整合式 Advanced Trading Chart、市場結構、Entry/SL/TP、MTF Matrix、Signal Score 與 AI Trade Narrative。
7. 再看「價格圖表」確認價格位置與趨勢
8. 如果本機有 my_stocks.json / my_sotcks.json，打開「持倉下單計畫」檢查目前持倉的停損、停利、加碼限價與減碼 / 出清提醒。
9. 打開「隔日掛單計畫」查看隔日買進 / 賣出區、戰術停損、硬停損、觸及機率，並點選表格 row 或下拉股票，讓下方 swing trading 技術圖同步切換到對應標的。
10. 看「回測」確認勝率、最大回撤、停損命中率與累積報酬
11. 看「因子研究」比較 1/3/5/10 天 horizon 哪個比較有訊號
12. 需要更細原因時，再按「歸因分析」或「因子研究」中的執行按鈕
13. 用「股票關係」確認多檔股票是否集中在同一類風險

更完整的新手說明請讀：

```text
spec/tutor_guide.md
```

## Docker 快取說明

Docker Compose 會掛載：

```text
./docker_runtime:/app/runtime
```

yfinance 磁碟快取會放在：

```text
docker_runtime/market_cache/
```

容器重啟後，同一組股票 / 區間 / K 線週期會優先從磁碟快取讀取。若要強制更新行情，請在 UI 左側按「重新抓資料 / 更新分析」，或手動刪除 docker_runtime/market_cache/yf_*.pkl。

## 本機開發啟動

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
uv venv .venv
. .venv/bin/activate
uv pip install -e '.[dev,futu]'
pytest -q
streamlit run src/ai_stock/app.py --server.headless true --server.port 8507 --server.address 0.0.0.0
```

## 核心模組

- data_sources.py：OHLCV schema、yfinance fallback、Futu/OpenD adapter boundary、行情快取
- analytics.py：技術 snapshot、報酬相關性、正 / 反相關壓力
- forecasting.py：ARIMA / sklearn baseline、Kelly sizing、買賣停損價、決策原因
- backtesting.py：walk-forward 回測、持有天數與出場規則比較
- attribution.py：SHAP TreeExplainer / permutation importance fallback
- factor_research.py：sliding-window 技術因子資料集、多 horizon 漲跌分類、Accuracy/AUC 趨勢、ticker × horizon heatmap、SHAP/fallback 重要度、相關係數、分組勝率、y heatmap
- pipeline.py：資料 → 分析 → 報表 pipeline
- portfolio.py：本機私有持倉讀取與持倉停損、停利、加碼限價、減碼 / 出清檢查規劃；支援 my_stocks.json / my_sotcks.json，不自動下單
- order_planner.py：隔日掛單研究規劃器；從持倉、OHLCV 波動與決策報表估算隔日買賣區、戰術停損、硬停損、觸及機率、建議單型、15m/1h/1d SMC 信心分數、買賣急迫度與優先處理分數
- swing_order_chart.py：隔日掛單計畫的 row 聯動 swing trading 圖；顯示 K 線、布林、RSI、MACD、成交量、K 線型態、掛單區、FVG/IFVG、Order Block、Liquidity、Swing/SFP/BOS/ChoCH、圖例 icon 說明與 UKF-style 去噪動能
- smc_adapter.py：可選 smartmoneyconcepts adapter；第三方 FVG、Order Block、Liquidity、Swing、BOS/ChoCH 優先，失敗時 fallback 內建規則
- visual_insights.py：今日機會雷達、Watchlist mini sparkline、市場熱力圖、Smart Tuning Lite、策略健檢卡、K 線決策線與回測 B/S marker
- trade_vision.py：智能交易視覺中心核心，包含 swing/BOS/ChoCH 市場結構、支撐壓力與供需區、premium/discount/equilibrium、Entry/SL/TP 交易計畫、MTF Matrix、Signal Score、AI Trade Narrative，以及 Plotly 進階風險報酬 K 線圖
- app.py：Streamlit UI 與多語言顯示層
- i18n.py：中 / 英 / 日 / 韓 UI 語言包

## GitHub 上傳前注意

此 repo 已包含 .gitignore，會排除：

- .venv、pytest cache、Python cache
- runtime、docker_runtime、行情快取、log、sqlite、pkl/joblib/parquet 等本機資料
- .env、token、credential、secret、key 等敏感檔案
- .codex、.claude、.cursor、.hermes、AGENTS.md、CLAUDE.md、agent/codex log、session transcript 等 agent / coding-assistant 本機痕跡

建議上傳前先檢查：

```bash
git status --short
git status --ignored --short | head -80
```

## 推到既有 GitHub repo 的指令範例

你已建立 repo：https://github.com/a0665x/AI_Stock.git

若本地尚未初始化 git：

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
git init
git branch -M main
git remote add origin https://github.com/a0665x/AI_Stock.git
git status --short
git add .
git status --short
git commit -m "Initial AI Stock dashboard"
git push -u origin main
```

若本地已經有 git，只要確認 remote：

```bash
cd /home/a0665x/Desktop/AI_AGX_WS/ai_stock_project/AI_Stock
git remote -v
git remote add origin https://github.com/a0665x/AI_Stock.git  # 若尚未設定 origin 才需要
git add .
git commit -m "Add multilingual AI Stock dashboard"
git push -u origin main
```

如果 GitHub 要求 token，請在 Git 提示輸入密碼時貼上你的 develop token；不要把 token 寫進 repo 檔案。

## 注意事項

這是研究與決策輔助，不是投資建議，也不做自動下單。任何買賣都應再搭配你的風險承受度、資金控管、交易成本、流動性與外部市場資訊判斷。
